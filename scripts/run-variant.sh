#!/bin/bash
# run-variant.sh — Run a coverage experiment variant with live-monitorable output.
#
# Uses systemd-run (same as claude-run.sh) to escape Claude Code's process tree,
# but writes to a FIXED log path so monitoring is always the same command.
#
# Usage:
#   ./scripts/run-variant.sh "--variant simple --item gs-rest-service"
#   ./scripts/run-variant.sh "--variant hardened+skills --item gs-rest-service"
#   ./scripts/run-variant.sh "--run-all-variants"
#
# Monitor from another terminal:
#   tail -f /tmp/coverage-v2-run.log

ARGS="${1:-}"
if [ -z "$ARGS" ]; then
    echo "Usage: $0 \"--variant <name> [--item <slug>] | --run-all-variants\"" >&2
    exit 1
fi

LOG=/tmp/coverage-v2-run.log
echo "Starting experiment. Log: $LOG"
echo "Monitor: tail -f $LOG"
echo ""

# Unset so Claude Code's ANTHROPIC_API_KEY doesn't bleed into sub-agent invocations
unset ANTHROPIC_API_KEY

systemd-run --user --wait --collect \
    -p Environment="HOME=$HOME" \
    -p Environment="PATH=$PATH" \
    -p Environment="SHELL=${SHELL:-/bin/bash}" \
    -p Environment="JAVA_HOME=${JAVA_HOME:-}" \
    -p Environment="MAVEN_HOME=${MAVEN_HOME:-}" \
    -p Environment="SDKMAN_DIR=${SDKMAN_DIR:-}" \
    -p StandardOutput="file:${LOG}" \
    -p StandardError="file:${LOG}" \
    -p WorkingDirectory="$(pwd)" \
    /bin/bash -c "./mvnw compile exec:java -Dexec.args='${ARGS}'" 2>/dev/null

echo ""
echo "Done. Full log at: $LOG"
