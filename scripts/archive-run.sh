#!/usr/bin/env bash
#
# Archive an experiment sweep as dated tarballs on a GitHub release.
#
# Usage:
#   ./scripts/archive-run.sh <sweep-name> [--session <name>]... [--draft]
#
# Example:
#   ./scripts/archive-run.sh stage4-n3-sweep \
#       --session 20260314-010341 --session 20260314-013345
#
#   ./scripts/archive-run.sh stage4-n3-sweep --draft   # archives all sessions
#
# Creates:
#   {sweep}-results.tar.gz    — session result JSONs (variant results + session metadata)
#   {sweep}-analysis.tar.gz   — analysis artifacts (tables, figures, sweep report)
#   {sweep}-logs.tar.gz       — execution logs (if any exist)
#
# Publishes as GitHub release tagged {sweep-name}.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS_DIR="$PROJECT_ROOT/results/code-coverage-v2"
SESSIONS_DIR="$RESULTS_DIR/sessions"
STAGING_DIR="$PROJECT_ROOT/.archive-staging"

# Parse arguments
SWEEP_NAME=""
SESSIONS=()
DRAFT_FLAG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --session)
            SESSIONS+=("$2")
            shift 2
            ;;
        --draft)
            DRAFT_FLAG="--draft"
            shift
            ;;
        -*)
            echo "Unknown flag: $1" >&2
            exit 1
            ;;
        *)
            if [[ -z "$SWEEP_NAME" ]]; then
                SWEEP_NAME="$1"
            else
                echo "Unexpected argument: $1" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$SWEEP_NAME" ]]; then
    echo "Usage: $0 <sweep-name> [--session <name>]... [--draft]"
    echo ""
    echo "Examples:"
    echo "  $0 stage4-n3-sweep --session 20260314-010341 --session 20260314-013345"
    echo "  $0 stage4-n3-sweep   # archives all sessions"
    echo ""
    echo "Available sessions:"
    ls "$SESSIONS_DIR" 2>/dev/null | sort
    exit 1
fi

# If no sessions specified, include all
if [[ ${#SESSIONS[@]} -eq 0 ]]; then
    echo "No --session flags provided, including all sessions"
    for d in "$SESSIONS_DIR"/*/; do
        SESSIONS+=("$(basename "$d")")
    done
fi

RESULTS_TARBALL="${SWEEP_NAME}-results.tar.gz"
PARQUET_TARBALL="${SWEEP_NAME}-parquet.tar.gz"
ANALYSIS_TARBALL="${SWEEP_NAME}-analysis.tar.gz"
LOGS_TARBALL="${SWEEP_NAME}-logs.tar.gz"

echo "=== Archiving sweep: $SWEEP_NAME ==="
echo "Sessions: ${SESSIONS[*]}"
echo ""

# Clean staging
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR/results" "$STAGING_DIR/logs"

# Package session results
echo "Packaging results..."
VARIANT_COUNT=0
for session in "${SESSIONS[@]}"; do
    session_dir="$SESSIONS_DIR/$session"
    if [[ ! -d "$session_dir" ]]; then
        echo "  WARNING: Session $session not found, skipping"
        continue
    fi
    # Copy session directory (JSONs + session metadata, skip workspaces to keep size down)
    mkdir -p "$STAGING_DIR/results/$session"
    for f in "$session_dir"/*.json; do
        [[ -f "$f" ]] && cp "$f" "$STAGING_DIR/results/$session/"
    done
    # Count variants (exclude session.json and sessions-index.json)
    for f in "$session_dir"/*.json; do
        name="$(basename "$f")"
        [[ "$name" == "session.json" || "$name" == "sessions-index.json" ]] && continue
        VARIANT_COUNT=$((VARIANT_COUNT + 1))
    done
    echo "  $session: $(ls "$STAGING_DIR/results/$session"/*.json 2>/dev/null | wc -l) files"
done
tar czf "$STAGING_DIR/$RESULTS_TARBALL" -C "$STAGING_DIR/results" .
RESULTS_SIZE="$(du -h "$STAGING_DIR/$RESULTS_TARBALL" | cut -f1)"
echo "  $RESULTS_TARBALL ($RESULTS_SIZE)"
echo ""

# Package curated parquet files
echo "Packaging parquet data..."
PARQUET_DIR="$PROJECT_ROOT/data/curated"
N3_PARQUET_DIR="$PROJECT_ROOT/data/n3-curated"
if [[ -d "$N3_PARQUET_DIR" ]]; then
    tar czf "$STAGING_DIR/$PARQUET_TARBALL" -C "$PROJECT_ROOT" data/n3-curated/
    PARQUET_SIZE="$(du -h "$STAGING_DIR/$PARQUET_TARBALL" | cut -f1)"
    echo "  $PARQUET_TARBALL ($PARQUET_SIZE, n3-curated)"
elif [[ -d "$PARQUET_DIR" ]]; then
    tar czf "$STAGING_DIR/$PARQUET_TARBALL" -C "$PROJECT_ROOT" data/curated/
    PARQUET_SIZE="$(du -h "$STAGING_DIR/$PARQUET_TARBALL" | cut -f1)"
    echo "  $PARQUET_TARBALL ($PARQUET_SIZE, curated)"
else
    echo "  WARNING: No parquet data found (data/curated/ or data/n3-curated/), skipping"
fi
echo ""

# Package analysis
echo "Packaging analysis..."
ANALYSIS_DIR="$PROJECT_ROOT/analysis"
if [[ -d "$ANALYSIS_DIR" ]]; then
    tar czf "$STAGING_DIR/$ANALYSIS_TARBALL" -C "$PROJECT_ROOT" analysis/
    ANALYSIS_SIZE="$(du -h "$STAGING_DIR/$ANALYSIS_TARBALL" | cut -f1)"
    echo "  $ANALYSIS_TARBALL ($ANALYSIS_SIZE)"
else
    echo "  WARNING: $ANALYSIS_DIR not found, skipping"
fi
echo ""

# Package logs
echo "Packaging logs..."
LOG_COUNT=0
for log in "$PROJECT_ROOT"/logs/*.log; do
    if [[ -f "$log" ]]; then
        cp "$log" "$STAGING_DIR/logs/"
        LOG_COUNT=$((LOG_COUNT + 1))
    fi
done
# Also check results/*.log for compatibility
for log in "$PROJECT_ROOT"/results/*.log; do
    if [[ -f "$log" ]]; then
        cp "$log" "$STAGING_DIR/logs/"
        LOG_COUNT=$((LOG_COUNT + 1))
    fi
done
if [[ $LOG_COUNT -gt 0 ]]; then
    tar czf "$STAGING_DIR/$LOGS_TARBALL" -C "$STAGING_DIR/logs" .
    LOGS_SIZE="$(du -h "$STAGING_DIR/$LOGS_TARBALL" | cut -f1)"
    echo "  $LOGS_TARBALL ($LOGS_SIZE, $LOG_COUNT log files)"
else
    echo "  No log files found, skipping"
fi
echo ""

# Generate release notes
echo "Generating release notes..."
NOTES_FILE="$STAGING_DIR/release-notes.md"
REPO_SHA="$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null || echo "unknown")"

cat > "$NOTES_FILE" << EOF
**Repo SHA (archival = experiment-time)**: $REPO_SHA

## Code Coverage Experiment v2 — $SWEEP_NAME

**Sessions**: ${SESSIONS[*]}
**Variant results**: $VARIANT_COUNT

EOF

# Pull summary from experiment-findings.md if it exists
FINDINGS_FILE="$ANALYSIS_DIR/experiment-findings.md"
if [[ -f "$FINDINGS_FILE" ]]; then
    echo "### Summary Results" >> "$NOTES_FILE"
    echo "" >> "$NOTES_FILE"
    sed -n '/^## Summary/,/^## /{/^## Summary/d;/^## /d;p}' "$FINDINGS_FILE" >> "$NOTES_FILE" 2>/dev/null || true
    echo "" >> "$NOTES_FILE"
fi

# Include markov findings if available
MARKOV_FINDINGS="$ANALYSIS_DIR/markov-findings.md"
if [[ -f "$MARKOV_FINDINGS" ]]; then
    echo "### Markov Findings" >> "$NOTES_FILE"
    echo "" >> "$NOTES_FILE"
    head -60 "$MARKOV_FINDINGS" >> "$NOTES_FILE"
    echo "" >> "$NOTES_FILE"
fi

cat >> "$NOTES_FILE" << EOF

### Archives

| Archive | Contents |
|---------|----------|
| \`$RESULTS_TARBALL\` | Session result JSONs ($VARIANT_COUNT variant results) |
| \`$PARQUET_TARBALL\` | Curated parquet tables (runs, item_results, tool_uses, judge_details) |
| \`$ANALYSIS_TARBALL\` | Analysis artifacts (tables, figures, Markov findings) |
| \`$LOGS_TARBALL\` | Execution logs |

### Extraction

\`\`\`bash
# Clone the repo first
git clone <repo-url> code-coverage-v2
cd code-coverage-v2

# Download release assets
gh release download $SWEEP_NAME

# Extract session results
mkdir -p results/code-coverage-v2/sessions
tar xzf ${RESULTS_TARBALL} -C results/code-coverage-v2/sessions/

# Extract analysis (frozen-in-time snapshot)
tar xzf ${ANALYSIS_TARBALL} -C .

# Extract logs (if downloaded)
mkdir -p logs
tar xzf ${LOGS_TARBALL} -C logs/
\`\`\`

To regenerate analysis from extracted results:

\`\`\`bash
cd code-coverage-v2
uv venv && uv pip install -r scripts/requirements.txt
source .venv/bin/activate
python scripts/load_results.py --experiment code-coverage-v2 $(printf -- '--session %s ' "${SESSIONS[@]}")
python scripts/make_markov_analysis.py
\`\`\`

See \`results/README.md\` in the repo for full extraction instructions.
EOF

# List assets to upload
ASSETS=("$STAGING_DIR/$RESULTS_TARBALL")
[[ -f "$STAGING_DIR/$PARQUET_TARBALL" ]] && ASSETS+=("$STAGING_DIR/$PARQUET_TARBALL")
[[ -f "$STAGING_DIR/$ANALYSIS_TARBALL" ]] && ASSETS+=("$STAGING_DIR/$ANALYSIS_TARBALL")
[[ -f "$STAGING_DIR/$LOGS_TARBALL" ]] && ASSETS+=("$STAGING_DIR/$LOGS_TARBALL")

echo "Ready to create release:"
echo "  Tag: $SWEEP_NAME"
echo "  Assets: ${#ASSETS[@]} files"
echo "  Draft: ${DRAFT_FLAG:-no}"
echo ""

# Create release
gh release create "$SWEEP_NAME" \
    --title "$SWEEP_NAME" \
    --notes-file "$NOTES_FILE" \
    $DRAFT_FLAG \
    "${ASSETS[@]}"

echo ""
echo "=== Release created: $SWEEP_NAME ==="
echo "View: gh release view $SWEEP_NAME"

# Clean up staging
rm -rf "$STAGING_DIR"
