# Code Coverage Experiment v2: Agent Knowledge Packaging

**Question**: Does agent-structured knowledge (SkillsJars) outperform flat file injection
for AI-generated Spring test quality — and why?

**Short answer**: SkillsJars nearly eliminates redundant API lookups (JAR\_INSPECT: 1.0% vs
11.0%), but structured pre-analysis (SAE) independently drives the largest efficiency gain.
The combination achieves 25% fewer expected steps than the hardened baseline (224 vs 301).

Direct sequel to [code-coverage-experiment](https://github.com/markpollack/code-coverage-experiment)
(v1), which established the baseline variants. This experiment adds SkillsJars (Variants 4–6)
and uses Markov chain analysis to characterize *how* each variant works, not just whether it
passes.

---

## Key Results (spring-petclinic, N≤3)

| Variant | Exp. Steps | JAR\_INSPECT % | FIX\_LOOP % | Line Cov | Cost (N=1) |
|---------|-----------|---------------|------------|----------|------------|
| simple | 214 | 7.9% | 16.4% | 93.2% | $4.03 |
| hardened | 301 | 11.0% | 18.3% | 92.6% | $2.53 |
| hardened+kb | 247 | 10.1% | 19.0% | 93.9% | $2.99 |
| **hardened+skills** | 297 | **1.0%** | 11.1% | 93.6% | $4.22 |
| hardened+sae | 238 | 7.1% | 21.4% | 93.2% | $3.39 |
| **hardened+skills+sae** | **224** | 7.1% | 19.2% | 92.9% | $2.84 |
| hardened+skills+sae+forge | 279 | 2.1% | 24.9% | 92.6% | $5.67 |

*Expected steps = mean absorbing steps under first-order Markov model. See
`analysis/markov-findings.md` for full P-matrix comparison.*

**Benchmark**: [spring-petclinic](https://github.com/spring-projects/spring-petclinic) —
50+ classes, multiple Spring layers (MVC, JPA, validation). Agent: Claude Sonnet 4.6.

---

## Reproduce

See [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for full instructions. Three levels:

**Level 1 — Figures and tables** (no code, ~5 min):
```bash
gh release download <release-tag>
tar xzf <release-tag>-analysis.tar.gz -C .
# analysis/ contains all figures and tables
```

**Level 2 — Re-run analysis from curated data** (no API key, ~10 min):
```bash
gh release download <release-tag>
tar xzf <release-tag>-results.tar.gz -C results/code-coverage-v2/sessions/
tar xzf <release-tag>-parquet.tar.gz -C data/

uv venv && source .venv/bin/activate
uv pip install -r scripts/requirements.txt
python scripts/make_markov_analysis.py
python scripts/make_figures.py
```

**Level 3 — Full re-run** (~$50 API cost, Claude API key required):
```bash
# See REPRODUCIBILITY.md §3
```

---

## Repository Structure

```
.
├── README.md
├── REPRODUCIBILITY.md     # step-by-step with expected outputs
├── CITATION.cff           # machine-readable citation
├── EXTRACTING.md          # how to download and extract release assets
├── experiment-config.yaml # variant definitions (prompts, KB, skills flags)
├── pom.xml                # Java experiment harness
├── scripts/
│   ├── run-variant.sh     # run one variant (wraps systemd-run for isolation)
│   ├── run-n3-sweep.sh    # unattended N=3 sweep across all variants
│   ├── archive-run.sh     # package results → GitHub release
│   ├── load_results.py    # ETL: session JSON → parquet
│   ├── make_markov_analysis.py  # Markov chain P-matrix + expected steps
│   ├── make_figures.py    # pass rate bars, cost/quality scatter
│   ├── validate_markov.py # first-order validity tests (KL, LR, Frobenius)
│   └── requirements.txt
├── src/                   # Java experiment harness (agent invoker, judges, dataset)
│   └── main/java/io/github/markpollack/lab/experiment/coverage/
├── datasets/              # dataset manifest + benchmark items
├── plans/prompts/         # externalized agent prompts (one file per variant)
├── docs/latex/            # LaTeX writeup and compiled PDFs
├── analysis/              # generated outputs (gitignored — download from release)
├── data/                  # parquet ETL output (gitignored — download from release)
└── results/               # raw session JSON (gitignored — download from release)
```

---

## Variants

| # | Name | Prompt | KB | Skills | Pre-analysis |
|---|------|--------|-----|--------|-------------|
| 1 | simple | minimal | — | — | — |
| 2 | hardened | structured + stopping condition | — | — | — |
| 3 | hardened+kb | hardened | flat file injection | — | — |
| 4 | hardened+skills | hardened | SkillsJars | ✓ | — |
| 5 | hardened+sae | hardened | — | — | ✓ |
| 6 | hardened+skills+sae | hardened | SkillsJars | ✓ | ✓ |
| 7 | hardened+skills+sae+forge | two-phase explore→act | SkillsJars | ✓ | ✓ |

**Pre-analysis script** (`ProjectAnalyzer`): a regex-based structural scan run before the
agent starts. Generates `PROJECT-ANALYSIS.md` in the workspace with a component inventory,
dependency versions, and recommended test patterns — replacing cold exploratory reads with a
pre-computed summary. Note: this is a lightweight approximation; it does not use SCIP or ASM
bytecode analysis.

**SkillsJars**: JIT context delivery via Claude Code's Skill tool — the agent invokes
a skill to retrieve Spring testing knowledge on demand, rather than reading files.

---

## Markov Analysis

Agent tool-call traces are modeled as absorbing Markov chains. States:

| State | Description |
|-------|-------------|
| EXPLORE | Reading project source files |
| READ\_KB | Reading injected knowledge files |
| READ\_SKILL | Invoking a SkillsJar skill |
| JAR\_INSPECT | Decompiling / reading compiled artifacts to infer APIs |
| WRITE | Writing test code |
| BUILD | Compiling |
| VERIFY | Running tests / checking coverage |
| FIX | Fixing compilation or test failures |

The P-matrix fingerprint for each variant reveals *mechanism*, not just outcome.
`hardened+skills` achieves near-zero JAR\_INSPECT by replacing API spelunking with
skill invocations. `hardened+sae` reduces expected steps by front-loading exploration.

---

## Requirements

- Java 21, Maven (wrapper included: `./mvnw`)
- Python 3.10+, [uv](https://github.com/astral-sh/uv)
- Claude API key (Level 3 reproduction only)
- [spring-testing-skills](https://github.com/markpollack/spring-testing-skills)
  installed to `~/.claude/skills/` (Variants 4, 6, 7 only)

---

## Related

- [code-coverage-experiment](https://github.com/markpollack/code-coverage-experiment) — v1 (Variants 1–4, 5 Spring guides)
- [markov-agent-analysis](https://github.com/markpollack/markov-agent-analysis) — Markov analysis library

---

## Citation

```bibtex
@misc{pollack2026coverage,
  author  = {Pollack, Mark},
  title   = {Code Coverage Experiment v2: Agent Knowledge Packaging},
  year    = {2026},
  url     = {https://github.com/markpollack/code-coverage-v2}
}
```
