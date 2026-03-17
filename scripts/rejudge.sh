#!/usr/bin/env bash
# Re-run T1/T2/T3 judges against preserved workspaces (no agent re-invocation).
#
# Usage:
#   scripts/rejudge.sh                          # All 20 valid sessions, T1+T2+T3
#   scripts/rejudge.sh --tiers 1,2              # Coverage judges only (fast)
#   scripts/rejudge.sh --session 20260312-181643 --dry-run
#   scripts/rejudge.sh --tiers 1,2 --regenerate-jacoco   # Regenerate XML from .exec first
#
# Adds --regenerate-jacoco by default — safe to skip if jacoco.xml already exists.

set -euo pipefail
cd "$(dirname "$0")/.."

# Unset API key so all Claude calls go through the CLI (Claude Max plan),
# not the Anthropic API (which would charge per-token).
unset ANTHROPIC_API_KEY

exec ./mvnw exec:java \
  -Dexec.mainClass=io.github.markpollack.lab.experiment.coverage.RejudgeApp \
  "-Dexec.args=$*"
