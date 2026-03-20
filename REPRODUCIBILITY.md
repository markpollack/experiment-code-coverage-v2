# Reproducibility Guide

This document gives step-by-step instructions to reproduce the results in this
experiment at three levels of depth. Each level builds on the previous.

---

## Prerequisites (all levels)

```bash
git clone https://github.com/markpollack/code-coverage-v2
cd code-coverage-v2

# Python environment
uv venv && source .venv/bin/activate
uv pip install -r scripts/requirements.txt
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

# Extract session results
mkdir -p results/code-coverage-v2/sessions
tar xzf v2.0.0-results.tar.gz -C results/code-coverage-v2/sessions/

# Extract curated parquet tables
tar xzf v2.0.0-parquet.tar.gz -C data/
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
| `analysis/markov-findings.md` | `hardened+skills` JAR\_INSPECT ≈ 1.0% |
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

- Claude API key: `export ANTHROPIC_API_KEY=sk-...`
- Java 21 + Maven wrapper (`./mvnw`)
- [spring-testing-skills](https://github.com/markpollack/spring-testing-skills)
  built and installed (Variants 4, 6, 7 only):
  ```bash
  # Clone and install
  git clone https://github.com/markpollack/spring-testing-skills
  cd spring-testing-skills && ./mvnw package
  # skills are installed automatically by the harness at run time
  ```

### 3a. Build the experiment harness

```bash
./mvnw compile
```

### 3b. Smoke test (no API calls)

```bash
COVERAGE_SMOKE_TEST=true ./mvnw test -Pintegration
```

**Expected**: all assertions pass, no API calls made.

### 3c. Run all variants

```bash
# Single item, single variant (development/validation)
./scripts/run-variant.sh "--variant hardened --item spring-petclinic"

# Full N=3 sweep (unattended, ~6–8 hrs, logs to logs/)
./scripts/run-n3-sweep.sh
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
- **Private dependency**: `ai.tuvium:experiment-core` is a private Maven artifact. The harness will not compile from scratch without it. Level 2 (analysis from parquet) does not require it.
- **Skills dependency**: Variants 4, 6, 7 require `spring-testing-skills` installed locally.
- **Model availability**: Results assume Claude Sonnet 4.6. A different model will produce different P-matrices.
