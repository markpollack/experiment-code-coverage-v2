# Results — Extraction Guide

Raw session data is **not committed to git**. It is archived as GitHub release assets
after each sweep. This file explains how to restore it locally.

## Why GitHub Releases?

Session workspaces are large (agent-written test files, build outputs). We archive
result JSONs + analysis artifacts as tarballs on GitHub releases — one release per
sweep. This keeps the repo lean while preserving full reproducibility.

## Finding Releases

```bash
gh release list
gh release view <release-tag>
```

## Extracting a Release

```bash
# Download assets for a specific sweep
gh release download <release-tag>

# Extract session results
mkdir -p results/code-coverage-v2/sessions
tar xzf <release-tag>-results.tar.gz -C results/code-coverage-v2/sessions/

# Extract analysis (frozen snapshot — tables, figures, markov findings)
tar xzf <release-tag>-analysis.tar.gz -C .

# Extract logs (if present)
mkdir -p logs
tar xzf <release-tag>-logs.tar.gz -C logs/
```

## Regenerating Analysis

After extracting results, re-run the ETL and analysis pipeline:

```bash
uv venv && uv pip install -r scripts/requirements.txt
source .venv/bin/activate

# Load results into parquet (specify session IDs from release notes)
python scripts/load_results.py --experiment code-coverage-v2 \
    --session <session-id-1> --session <session-id-2> ...

# Regenerate Markov analysis
python scripts/make_markov_analysis.py
```

Session IDs for each release are listed in the release notes on GitHub.

## Creating a New Release

After completing a sweep:

```bash
# Archive specific sessions
./scripts/archive-run.sh <sweep-name> \
    --session <session-id-1> --session <session-id-2>

# Or draft first for review
./scripts/archive-run.sh <sweep-name> --draft
```

The script creates three tarballs (`results`, `analysis`, `logs`) and publishes them
as a GitHub release with auto-generated extraction instructions in the release notes.

Granularity: **one release per named sweep** (e.g., `stage4-n3-sweep`, `stage2-baseline`).
