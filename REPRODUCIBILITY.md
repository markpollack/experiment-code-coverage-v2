# Reproducibility Guide

This document gives step-by-step instructions to reproduce the results in this
experiment at three levels of depth. Each level builds on the previous.

---

## Prerequisites (all levels)

```bash
git clone https://github.com/markpollack/experiment-code-coverage-v2
cd experiment-code-coverage-v2

# Python environment
uv venv && source .venv/bin/activate
uv pip install -r scripts/requirements.txt

# Markov analysis library (required for Level 2)
git clone https://github.com/markpollack/markov-agent-analysis
uv pip install -e markov-agent-analysis[all]
```

---

## Level 1 — Figures and tables (no code, ~5 min)

Download the pre-built analysis snapshot from the GitHub release.

```bash
# List available releases
gh release list

# Download analysis tarball for a specific release
gh release download v2.0.0 --pattern "*-analysis.tar.gz"
tar xzf v2.0.0-analysis.tar.gz -C .
```

**Expected outputs in `analysis/`**:
- `markov-findings.md` — P-matrix summary table and loop amplification
- `markov-validation.md` — first-order validity tests (KL divergence, Frobenius drift)
- `figures/` — PNG figures (Markov heatmaps, cost/coverage scatter)

No code runs. All outputs are frozen at archival time.

---

## Level 2 — Re-run analysis from curated data (~10 min, no API key)

Download raw session results and curated parquet files, then re-run the analysis pipeline.

### 2a. Download release assets

```bash
gh release download v2.0.0

# Extract session results (extracts to sessions/)
tar xzf v2.0.0-results.tar.gz -C .

# Extract curated parquet tables (extracts to data/curated/)
tar xzf v2.0.0-parquet.tar.gz -C .
```

**Session IDs included** are listed in the release notes on GitHub.

### 2b. Verify parquet contents

```bash
python - << 'EOF'
import pandas as pd
ir = pd.read_parquet("data/curated/item_results.parquet")
tu = pd.read_parquet("data/curated/tool_uses.parquet")
print(f"item_results: {len(ir)} rows, variants: {ir['variant'].unique().tolist()}")
print(f"tool_uses:    {len(tu)} rows")
EOF
```

**Expected**: 7 variants in `item_results`, ~1800+ rows in `tool_uses`.

### 2c. Re-run ETL from session JSONs (optional — parquet already provided)

If you want to regenerate the parquet from raw JSONs:

```bash
python scripts/load_results.py --experiment code-coverage-v2 \
    --session <session-id-1> --session <session-id-2> ...
# Session IDs are listed in the release notes
```

**Expected**: `data/curated/` populated with 4 parquet files:
`runs.parquet`, `item_results.parquet`, `tool_uses.parquet`, `judge_details.parquet`.

### 2d. Re-run Markov analysis

```bash
python scripts/make_markov_analysis.py
```

**Expected outputs** (match Level 1 analysis snapshot):

| File | Key metric |
|------|-----------|
| `analysis/markov-findings.md` | `hardened+skills` JAR\_INSPECT ≈ 1.7% |
| `analysis/markov-findings.md` | `hardened+skills+preanalysis` exp. steps ≈ 224 |
| `analysis/markov-validation.md` | KL divergence < 0.50 bits |

```bash
python scripts/make_figures.py
python scripts/validate_markov.py --data-dir data/curated/
```

---

## Level 3 — Full re-run (~$50 API cost, ~6–8 hrs)

Runs all 7 variants × 2 additional sessions against spring-petclinic.

### Requirements

- Java 21
- Claude API key: `export ANTHROPIC_API_KEY=sk-...`
- [spring-testing-skills](https://github.com/spring-ai-community/spring-testing-skills)
  built and installed (Variants 4, 6, 7 only):
  ```bash
  git clone https://github.com/spring-ai-community/spring-testing-skills
  cd spring-testing-skills && ./mvnw package
  # skills are installed automatically by the harness at run time
  ```

### 3a. Download the agent jar

The v2.0.0 release includes a self-contained fat jar with all prompts, knowledge files,
and configuration bundled. No source checkout or Maven build required.

```bash
gh release download v2.0.0 --pattern "code-coverage-agent.jar"
```

### 3b. Verify the jar (no API calls)

```bash
java -jar code-coverage-agent.jar --run-all-variants --dry-run
```

**Expected**: loads config from classpath, loads all 7 variant prompts, exits
without making API calls.

### 3c. Run all variants

```bash
# Single item, single variant (development/validation)
java -jar code-coverage-agent.jar --variant hardened --item spring-petclinic

# Full N=3 sweep
java -jar code-coverage-agent.jar --run-all-variants --item spring-petclinic
```

**Monitor progress** from a second terminal:
```bash
tail -f $(cat /tmp/claude-run-current)
```

### 3d. Load and analyze results

After sessions complete, follow Level 2 steps (§2c, §2d) using the new session IDs
printed in the sweep log.

### Cost estimate

| Variant | Est. cost (N=2 new runs) | Est. time |
|---------|--------------------------|-----------|
| simple | ~$8.06 | ~54 min |
| hardened | ~$5.06 | ~34 min |
| hardened+kb | ~$6.00 | ~36 min |
| hardened+skills | ~$8.44 | ~54 min |
| hardened+preanalysis | ~$6.80 | ~50 min |
| hardened+skills+preanalysis | ~$5.68 | ~56 min |
| hardened+skills+preanalysis+plan-act | ~$9.50 | ~72 min |
| **Total** | **~$50–57** | **~6–7 hrs** |

---

## Validation Checklist

After Level 2 or Level 3, verify these numbers match published results:

- [ ] `hardened+skills` JAR\_INSPECT% ≤ 2.0%
- [ ] `hardened+skills+preanalysis` expected steps ≤ 230
- [ ] All 7 variants have P(success) = 1.0 on spring-petclinic
- [ ] `validate_markov.py` reports KL divergence < 0.50 bits
- [ ] `item_results.parquet` has 7 variants × N rows

Deviations > 10% in expected steps are expected due to model non-determinism.
Deviations > 25% suggest a configuration issue — check skill installation and prompt files.

---

## Known Limitations

- **Non-determinism**: Claude Sonnet 4.6 at temperature 1.0. Run-to-run std(E[steps]) ≈ 10–15 steps per variant.
- **Skills dependency**: Variants 4, 6, 7 require [spring-testing-skills](https://github.com/spring-ai-community/spring-testing-skills). Available from Maven Central: `org.springaicommunity:spring-testing-skills:0.1.0`.
- **Model availability**: Results assume Claude Sonnet 4.6. A different model will produce different behavioral signatures.
