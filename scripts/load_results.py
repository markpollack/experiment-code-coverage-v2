"""
ETL: Load experiment result JSON files into DuckDB-queryable parquet.

Supports the session layout: results/{experiment}/sessions/{session}/{variant}.json

Multiple sessions can be combined — later sessions override earlier ones
per variant (last-write-wins), so you can assemble best-of results from
separate runs.

Usage:
    python scripts/load_results.py --experiment my-experiment
    python scripts/load_results.py --experiment my-experiment --session 20260304-042311
    python scripts/load_results.py --experiment my-experiment --session s1 --session s2
    python scripts/load_results.py --experiment my-experiment --output-dir /tmp/parquet
"""

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# CUSTOMIZE: update keys to match your judge class names, values to column names.
# Each key is the judge class name as it appears in results JSON "scores" map.
# Each value is the column name in the output parquet.
SCORE_MAP = {
    # "MyJudge": "t0_success",
    # "QualityJudge": "t1_quality",
    # "PracticeJudge": "t2_practice",
}


def find_latest_session(results_dir: Path) -> str:
    """Find the most recent session directory."""
    sessions_dir = results_dir / "sessions"
    if not sessions_dir.exists():
        raise FileNotFoundError(f"No sessions directory: {sessions_dir}")
    sessions = sorted(sessions_dir.iterdir(), reverse=True)
    if not sessions:
        raise FileNotFoundError("No sessions found")
    return sessions[0].name


def load_session_results(results_dir: Path, session_name: str) -> dict[str, dict]:
    """Load all variant results from a session directory."""
    session_dir = results_dir / "sessions" / session_name
    if not session_dir.exists():
        raise FileNotFoundError(f"Session not found: {session_dir}")

    results = {}
    for f in sorted(session_dir.glob("*.json")):
        if f.name in ("session.json", "sessions-index.json"):
            continue
        variant = f.stem
        with open(f) as fh:
            results[variant] = json.load(fh)
    return results


def parse_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def extract_runs(results: dict[str, dict], run_group: str, model: str) -> list[dict]:
    rows = []
    for variant, data in results.items():
        rows.append({
            "run_id": data["experimentId"],
            "variant": variant,
            "model": model,
            "timestamp": data["timestamp"],
            "pass_rate": data["passRate"],
            "total_cost_usd": data["totalCostUsd"],
            "total_duration_ms": data["totalDurationMs"],
            "total_tokens": data.get("totalTokens", 0),
            "item_count": len(data["items"]),
            "run_group": run_group,
        })
    return rows


def extract_item_results(results: dict[str, dict]) -> list[dict]:
    rows = []
    for variant, data in results.items():
        run_id = data["experimentId"]
        for item in data["items"]:
            inv_meta = item.get("invocationResult", {}).get("metadata", {})
            inv = item.get("invocationResult", {})
            scores = item.get("scores", {})
            metrics = item.get("metrics", {})

            row = {
                "run_id": run_id,
                "variant": variant,
                "item_id": item["itemSlug"],
                "passed": item["passed"],
                "cost_usd": item["costUsd"],
                "duration_ms": item.get("durationMs", 0),
                "total_tokens": item.get("totalTokens", 0),
                "input_tokens": metrics.get("input_tokens") or inv.get("inputTokens", 0),
                "output_tokens": metrics.get("output_tokens") or inv.get("outputTokens", 0),
                "thinking_tokens": metrics.get("thinking_tokens") or inv.get("thinkingTokens", 0),
                "phase_count": len(inv.get("phases", [])),
            }

            # Map scores to named columns (CUSTOMIZE: update SCORE_MAP above)
            for json_key, col_name in SCORE_MAP.items():
                row[col_name] = scores.get(json_key)

            rows.append(row)
    return rows


def extract_tool_uses(results: dict[str, dict]) -> list[dict]:
    """Extract per-tool-use rows from phase data for Markov analysis."""
    rows = []
    for variant, data in results.items():
        run_id = data["experimentId"]
        for item in data["items"]:
            inv = item.get("invocationResult", {})
            global_seq = 0
            for phase in inv.get("phases", []):
                phase_name = phase.get("phaseName", "unknown")
                for i, tool in enumerate(phase.get("toolUses", [])):
                    tool_input = tool.get("input", {})
                    target = _tool_target(tool["name"], tool_input)
                    rows.append({
                        "run_id": run_id,
                        "variant": variant,
                        "item_id": item["itemSlug"],
                        "phase_name": phase_name,
                        "phase_seq": i,
                        "global_seq": global_seq,
                        "tool_name": tool["name"],
                        "tool_target": target,
                    })
                    global_seq += 1
    return rows


def _tool_target(tool_name: str, tool_input: dict) -> str:
    """Extract a short human-readable target from tool input."""
    if tool_name in ("Read", "Write", "Edit", "Glob"):
        path = tool_input.get("file_path", tool_input.get("path", ""))
        parts = path.rstrip("/").split("/")
        return "/".join(parts[-2:]) if len(parts) > 1 else path
    if tool_name == "Agent":
        subagent_type = tool_input.get("subagent_type", "")
        description = tool_input.get("description", "")
        return f"{subagent_type}:{description}"[:80]
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        return cmd[:80]
    if tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        return f"/{pattern}/"[:60]
    if tool_name == "TodoWrite":
        return "todos"
    return ""


def extract_judge_details(results: dict[str, dict]) -> list[dict]:
    rows = []
    for variant, data in results.items():
        run_id = data["experimentId"]
        for item in data["items"]:
            verdict = item.get("verdict")
            if not verdict:
                continue
            _extract_checks(rows, run_id, item["itemSlug"], verdict)
    return rows


def _extract_checks(rows: list[dict], run_id: str, item_id: str, verdict: dict,
                    seen: set | None = None):
    """Recursively extract checks from verdict and subVerdicts."""
    if seen is None:
        seen = set()

    for individual in verdict.get("individual", []):
        judge_name = individual.get("reasoning", "unknown")
        for check in individual.get("checks", []):
            msg = check.get("message", "")
            criterion = check.get("name", "unknown")

            key = (item_id, criterion, msg[:100])
            if key in seen:
                continue
            seen.add(key)

            score = None
            if msg and msg[0].isdigit():
                try:
                    score = float(msg.split(" ")[0])
                except ValueError:
                    pass
            rows.append({
                "run_id": run_id,
                "item_id": item_id,
                "judge_name": judge_name[:100],
                "criterion_name": criterion,
                "score": score,
                "passed": check.get("passed", False),
                "evidence": msg[:500] if msg else None,
            })

    for sub in verdict.get("subVerdicts", []):
        _extract_checks(rows, run_id, item_id, sub, seen)


def write_parquet(rows: list[dict], table_name: str, output_path: Path):
    if not rows:
        print(f"  {table_name}: no rows, skipping")
        return

    df = pd.DataFrame(rows)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
    con.execute(f"COPY {table_name} TO '{output_path}' (FORMAT PARQUET)")
    count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
    print(f"  {table_name}: {count} rows -> {output_path.name}")
    con.close()


def merge_variant(results: dict, variant: str, data: dict, source: str):
    """Merge variant data at the item level — later items override by slug."""
    if variant not in results:
        results[variant] = data
        print(f"  {variant}: {len(data['items'])} items ({source})")
        return
    existing = results[variant]
    item_map = {item["itemSlug"]: item for item in existing["items"]}
    new_slugs = []
    for item in data["items"]:
        slug = item["itemSlug"]
        if slug not in item_map:
            new_slugs.append(slug)
        item_map[slug] = item
    existing["items"] = list(item_map.values())
    items = existing["items"]
    existing["passRate"] = sum(1 for i in items if i["passed"]) / len(items) if items else 0
    existing["totalCostUsd"] = sum(i["costUsd"] for i in items)
    existing["totalDurationMs"] = sum(i.get("durationMs", 0) for i in items)
    print(f"  {variant}: +{len(data['items'])} items ({source}) → {len(items)} total"
          + (f" (new: {new_slugs})" if new_slugs else ""))


def main():
    parser = argparse.ArgumentParser(description="Load experiment results into parquet")
    parser.add_argument("--experiment", required=True,
                        help="Experiment name (subdirectory of results/, or use --results-dir)")
    parser.add_argument("--results-dir", type=Path, default=None,
                        help="Override results directory (default: {project-root}/results/{experiment})")
    parser.add_argument("--session", action="append", dest="sessions",
                        help="Session name(s). Repeatable. Later sessions override earlier per variant.")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory for parquet files (default: data/curated/)")
    parser.add_argument("--model", default="claude-sonnet-4-6",
                        help="Model name to record in runs table")
    args = parser.parse_args()

    results_dir = args.results_dir or (PROJECT_ROOT / "results" / args.experiment)
    output_dir = args.output_dir or (PROJECT_ROOT / "data" / "curated")
    output_dir.mkdir(parents=True, exist_ok=True)

    merged: dict[str, dict] = {}

    if args.sessions:
        for session_name in args.sessions:
            print(f"Loading session: {session_name}")
            session_results = load_session_results(results_dir, session_name)
            for variant, data in session_results.items():
                merge_variant(merged, variant, data, session_name)
    else:
        session_name = find_latest_session(results_dir)
        print(f"Loading session: {session_name} (latest)")
        merged = load_session_results(results_dir, session_name)

    run_group = args.sessions[-1] if args.sessions else "latest"
    variants = sorted(merged.keys())
    print(f"Variants: {variants}")

    print("\nWriting parquet files:")
    write_parquet(extract_runs(merged, run_group, args.model), "runs", output_dir / "runs.parquet")
    write_parquet(extract_item_results(merged), "item_results", output_dir / "item_results.parquet")
    write_parquet(extract_tool_uses(merged), "tool_uses", output_dir / "tool_uses.parquet")
    write_parquet(extract_judge_details(merged), "judge_details", output_dir / "judge_details.parquet")

    print("\nVerification:")
    con = duckdb.connect()
    result = con.execute(f"""
        SELECT variant, count(*) as items,
               round(avg(CAST(passed AS INTEGER)), 3) as pass_rate,
               round(sum(cost_usd), 4) as total_cost
        FROM '{output_dir}/item_results.parquet'
        GROUP BY variant ORDER BY variant
    """).fetchall()
    print(f"\n{'Variant':20s} | {'Items':>5s} | {'PassRate':>8s} | {'Cost':>8s}")
    print("-" * 50)
    for row in result:
        print(f"{row[0]:20s} | {row[1]:5d} | {row[2]:8.3f} | {row[3]:8.4f}")


if __name__ == "__main__":
    main()
