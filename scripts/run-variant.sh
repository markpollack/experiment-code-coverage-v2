#!/bin/bash
# run-variant.sh — Run a coverage experiment variant.
#
# Delegates to ~/scripts/claude-run.sh which:
#   - Uses systemd-run to escape Claude Code's process tree detection
#   - Creates output file BEFORE starting (so tail -f works immediately)
#   - Writes current log path to /tmp/claude-run-current
#
# Usage:
#   ./scripts/run-variant.sh "--variant simple --item gs-rest-service"
#   ./scripts/run-variant.sh "--variant hardened+skills --item gs-rest-service"
#   ./scripts/run-variant.sh "--run-all-variants"
#
# Monitor from another terminal:
#   tail -f $(cat /tmp/claude-run-current)

ARGS="${1:-}"
if [ -z "$ARGS" ]; then
    echo "Usage: $0 \"--variant <name> [--item <slug>] | --run-all-variants\"" >&2
    exit 1
fi

echo "Monitor: tail -f \$(cat /tmp/claude-run-current)"
echo ""

# Unset so Claude Code's ANTHROPIC_API_KEY doesn't bleed into sub-agent invocations
unset ANTHROPIC_API_KEY

~/scripts/claude-run.sh "./mvnw compile exec:java -Dexec.args='${ARGS}'"
