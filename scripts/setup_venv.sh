#!/usr/bin/env bash
# Set up the Python virtual environment for analysis scripts.
#
# Usage:
#   ./scripts/setup_venv.sh
#   ./scripts/setup_venv.sh /path/to/markov-agent-analysis
#
# After running, activate with: source scripts/.venv/bin/activate

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "Creating venv at $VENV_DIR..."
python3 -m venv "$VENV_DIR"

echo "Installing requirements..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q

# Install markov-agent-analysis if path provided
MARKOV_LIB="${1:-}"
if [ -n "$MARKOV_LIB" ]; then
    echo "Installing markov-agent-analysis from $MARKOV_LIB..."
    "$VENV_DIR/bin/pip" install -e "$MARKOV_LIB[all]" -q
else
    echo "NOTE: markov-agent-analysis not installed."
    echo "  Run: $VENV_DIR/bin/pip install -e /path/to/markov-agent-analysis[all]"
    echo "  Or:  uv pip install -e /path/to/markov-agent-analysis[all]"
fi

echo ""
echo "Done. Activate with:"
echo "  source $VENV_DIR/bin/activate"
