#!/bin/bash
# run-n3-sweep.sh — Run 14 unattended petclinic variant runs (N=3 Markov sweep)
#
# Runs 2 sweeps × 7 variants = 14 runs against spring-petclinic.
# Intended for standalone execution from a terminal (NOT inside Claude Code).
# No systemd-run needed — the Java SDK spawns claude CLI directly.
#
# Logging structure:
#   logs/n3-sweep-<timestamp>.log         — sweep-level events (start/done/fail per run)
#   logs/n3-sweep-<timestamp>.summary     — cumulative run table, updated after each run
#   logs/runs/<variant>-s<N>-<ts>.log     — full Maven output per variant run
#   logs/runs/current -> <latest-run-log> — symlink for easy tail -f
#
# Usage:
#   cd /home/mark/projects/code-coverage-v2
#   bash scripts/run-n3-sweep.sh
#   bash scripts/run-n3-sweep.sh --dry-run           # print plan, no execution
#   bash scripts/run-n3-sweep.sh --start-at simple   # resume sweep 1 from 'simple'
#   bash scripts/run-n3-sweep.sh --start-at simple:2 # resume sweep 2 from 'simple'
#
# Monitor:
#   tail -f logs/n3-sweep-<timestamp>.log            # sweep-level events
#   tail -f $(readlink -f logs/runs/current)         # current variant's raw output
#   cat logs/n3-sweep-<timestamp>.summary            # cumulative status table

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ITEM="spring-petclinic"
SESSION_DIR="$PROJECT_DIR/results/code-coverage-v2/sessions"
LOG_DIR="$PROJECT_DIR/logs"
RUNS_DIR="$LOG_DIR/runs"
SWEEP_TS=$(date -u +%Y%m%d-%H%M%S)
SWEEP_LOG="$LOG_DIR/n3-sweep-${SWEEP_TS}.log"
SUMMARY_FILE="$LOG_DIR/n3-sweep-${SWEEP_TS}.summary"
SWEEP_START_EPOCH=$(date +%s)

# Variant order: cheapest/fastest first (from Stage 3 cost estimates)
VARIANTS=(
    "hardened"
    "hardened+skills+sae"
    "hardened+kb"
    "hardened+sae"
    "simple"
    "hardened+skills"
    "hardened+skills+sae+forge"
)
TOTAL_RUNS=$(( ${#VARIANTS[@]} * 2 ))

# ---- Parse args ----

DRY_RUN=false
RESUME_VARIANT=""
RESUME_SWEEP=1

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --start-at=*:*)
            RESUME_VARIANT="${arg#--start-at=}"
            RESUME_SWEEP="${RESUME_VARIANT#*:}"
            RESUME_VARIANT="${RESUME_VARIANT%:*}"
            ;;
        --start-at=*) RESUME_VARIANT="${arg#--start-at=}" ;;
        --start-at)   ;;  # handled below
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

# Handle --start-at without = (next arg is value) — simplistic
for i in "$@"; do
    shift
    if [ "$i" = "--start-at" ] && [ $# -gt 0 ]; then
        val="$1"
        if [[ "$val" == *:* ]]; then
            RESUME_SWEEP="${val#*:}"
            RESUME_VARIANT="${val%:*}"
        else
            RESUME_VARIANT="$val"
        fi
        break
    fi
done

# ---- Tracking state (accumulated as plain strings in files, not arrays) ----

COMPLETED_FILE=$(mktemp /tmp/n3-completed-XXXXXX)
FAILED_FILE=$(mktemp /tmp/n3-failed-XXXXXX)
RUN_COUNT_FILE=$(mktemp /tmp/n3-count-XXXXXX)
echo "0" > "$RUN_COUNT_FILE"

cleanup() {
    rm -f "$COMPLETED_FILE" "$FAILED_FILE" "$RUN_COUNT_FILE"
}
trap cleanup EXIT

# ---- Logging helpers ----

mkdir -p "$LOG_DIR" "$RUNS_DIR"

log() {
    local ts
    ts=$(date -u +%H:%M:%S)
    printf "[%s] %s\n" "$ts" "$*" | tee -a "$SWEEP_LOG"
}

log_bare() {
    printf "%s\n" "$*" | tee -a "$SWEEP_LOG"
}

elapsed_since() {
    local start=$1
    local now
    now=$(date +%s)
    local secs=$(( now - start ))
    printf "%dm%ds" $(( secs / 60 )) $(( secs % 60 ))
}

update_summary() {
    local run_num
    run_num=$(cat "$RUN_COUNT_FILE")
    local total_elapsed
    total_elapsed=$(elapsed_since "$SWEEP_START_EPOCH")

    {
        printf "N=3 Sweep — %s\n" "$SWEEP_TS"
        printf "Progress: %d / %d runs | Elapsed: %s\n" "$run_num" "$TOTAL_RUNS" "$total_elapsed"
        printf "\n"
        printf "%-35s %-7s %-20s %-10s %s\n" "VARIANT" "SWEEP" "SESSION" "ELAPSED" "STATUS"
        printf "%s\n" "$(printf '%0.s-' {1..90})"
        if [ -s "$COMPLETED_FILE" ]; then
            cat "$COMPLETED_FILE"
        fi
        if [ -s "$FAILED_FILE" ]; then
            printf "\nFAILED:\n"
            cat "$FAILED_FILE"
        fi
    } > "$SUMMARY_FILE"
}

# ---- Single variant run ----

run_variant() {
    local variant="$1"
    local sweep="$2"
    local run_num
    run_num=$(cat "$RUN_COUNT_FILE")
    run_num=$(( run_num + 1 ))
    echo "$run_num" > "$RUN_COUNT_FILE"

    local run_ts
    run_ts=$(date -u +%Y%m%d-%H%M%S)
    local safe_variant="${variant//+/-}"
    local run_log="$RUNS_DIR/${safe_variant}-s${sweep}-${run_ts}.log"

    # Symlink "current" to this run's log for easy tail -f
    ln -sf "$run_log" "$RUNS_DIR/current"

    log "Run $run_num/$TOTAL_RUNS | $variant | sweep $sweep/2"
    log "  Run log: $run_log"

    # Snapshot sessions before run
    local before_sessions
    before_sessions=$(ls -1 "$SESSION_DIR" 2>/dev/null | sort || true)

    local run_start
    run_start=$(date +%s)

    if [ "$DRY_RUN" = true ]; then
        {
            printf "[DRY RUN] %s\n" "$(date -u)"
            printf "Would run: ./mvnw exec:java -Dexec.args=\"--variant %s --item %s\"\n" "$variant" "$ITEM"
        } > "$run_log"
        sleep 1
        local elapsed="0m1s"
        local new_session="dry-run-session"
        printf "%-35s %-7s %-20s %-10s %s\n" "$variant" "sweep$sweep" "$new_session" "$elapsed" "OK(dry)" >> "$COMPLETED_FILE"
        log "  DONE (dry run) — $elapsed — session: $new_session"
        update_summary
        log_bare ""
        return 0
    fi

    {
        printf "=== N=3 Sweep: %s sweep %s | %s ===\n" "$variant" "$sweep" "$(date -u)"
        printf "Command: ./mvnw exec:java -Dexec.args=\"--variant %s --item %s\"\n" "$variant" "$ITEM"
        printf "=%.0s" {1..70}
        printf "\n\n"
    } > "$run_log"

    if ./mvnw exec:java -Dexec.args="--variant $variant --item $ITEM" >> "$run_log" 2>&1; then
        local elapsed
        elapsed=$(elapsed_since "$run_start")

        # Detect new session
        local after_sessions
        after_sessions=$(ls -1 "$SESSION_DIR" 2>/dev/null | sort || true)
        local new_session
        new_session=$(comm -13 <(printf '%s\n' "$before_sessions") <(printf '%s\n' "$after_sessions") | tail -1 || true)
        new_session="${new_session:-unknown}"

        printf "%-35s %-7s %-20s %-10s %s\n" "$variant" "sweep$sweep" "$new_session" "$elapsed" "OK" >> "$COMPLETED_FILE"
        log "  DONE — $elapsed — session: $new_session"
    else
        local exit_code=$?
        local elapsed
        elapsed=$(elapsed_since "$run_start")
        printf "%-35s %-7s %-20s %-10s %s\n" "$variant" "sweep$sweep" "-" "$elapsed" "FAILED(exit=$exit_code)" >> "$FAILED_FILE"
        log "  FAILED (exit $exit_code) — $elapsed — run log: $run_log"
        log "  Continuing to next run..."
    fi

    update_summary
    log_bare ""
}

# ---- Main ----

log "============================================"
log "N=3 Markov Sweep — $SWEEP_TS"
log "============================================"
log "Project:  $PROJECT_DIR"
log "Item:     $ITEM"
log "Sweep log: $SWEEP_LOG"
log "Summary:   $SUMMARY_FILE (updated after each run)"
log "Run logs:  $RUNS_DIR/"
log "Variants: ${#VARIANTS[@]} × 2 sweeps = $TOTAL_RUNS runs"
log "Order: cheapest first within each sweep"
[ "$DRY_RUN" = true ] && log "DRY RUN MODE — no experiments will be executed"
[ -n "$RESUME_VARIANT" ] && log "Resuming from: $RESUME_VARIANT (sweep $RESUME_SWEEP)"
log_bare ""

# ---- Compile (once) ----

cd "$PROJECT_DIR" || exit 1

if [ "$DRY_RUN" = false ]; then
    local_compile_log="$LOG_DIR/compile-${SWEEP_TS}.log"
    log "Compiling..."
    if ! ./mvnw compile -q > "$local_compile_log" 2>&1; then
        log "FATAL: compile failed. See $local_compile_log"
        cat "$local_compile_log" >&2
        exit 1
    fi
    log "Compile OK. (log: $local_compile_log)"
    log_bare ""
fi

# Initialize summary
update_summary

# ---- Sweeps ----

SKIP_UNTIL_VARIANT="$RESUME_VARIANT"
SKIP_UNTIL_SWEEP="$RESUME_SWEEP"

for sweep in 1 2; do
    log "=========================================="
    log "Sweep $sweep / 2  |  $(date -u +'%Y-%m-%d %H:%M UTC')"
    log "=========================================="
    log_bare ""

    for variant in "${VARIANTS[@]}"; do
        # Resume logic: skip until we reach the resume point
        if [ -n "$SKIP_UNTIL_VARIANT" ]; then
            if [ "$sweep" -lt "$SKIP_UNTIL_SWEEP" ]; then
                log "SKIP $variant sweep $sweep (resuming from sweep $SKIP_UNTIL_SWEEP)"
                continue
            elif [ "$sweep" -eq "$SKIP_UNTIL_SWEEP" ] && [ "$variant" != "$SKIP_UNTIL_VARIANT" ]; then
                log "SKIP $variant sweep $sweep (resuming from $SKIP_UNTIL_VARIANT)"
                continue
            else
                SKIP_UNTIL_VARIANT=""  # reached resume point
            fi
        fi

        run_variant "$variant" "$sweep"
    done

    log "Sweep $sweep complete | Total elapsed: $(elapsed_since "$SWEEP_START_EPOCH")"
    log_bare ""
done

# ---- Final Summary ----

update_summary

COMPLETED_COUNT=$(wc -l < "$COMPLETED_FILE" 2>/dev/null || echo 0)
FAILED_COUNT=$(wc -l < "$FAILED_FILE" 2>/dev/null || echo 0)
TOTAL_ELAPSED=$(elapsed_since "$SWEEP_START_EPOCH")

log "============================================"
log "N=3 SWEEP COMPLETE"
log "============================================"
log "Finished: $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
log "Elapsed:  $TOTAL_ELAPSED"
log "Runs:     $COMPLETED_COUNT completed, $FAILED_COUNT failed"
log_bare ""
log "COMPLETED:"
if [ -s "$COMPLETED_FILE" ]; then
    while IFS= read -r line; do log "  $line"; done < "$COMPLETED_FILE"
fi
if [ -s "$FAILED_FILE" ]; then
    log_bare ""
    log "FAILED:"
    while IFS= read -r line; do log "  $line"; done < "$FAILED_FILE"
fi
log_bare ""
log "Sweep log: $SWEEP_LOG"
log "Summary:   $SUMMARY_FILE"
log "Run logs:  $RUNS_DIR/"
log_bare ""
log "Next step: load N=3 data (see ROADMAP.md Step 4.2)"
log "  Use session names above: r1=existing curated, r2=sweep1, r3=sweep2"
