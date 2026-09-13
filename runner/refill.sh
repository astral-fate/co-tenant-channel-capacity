#!/usr/bin/env bash
# Re-invoke a run until every episode is present, or the pass budget is exhausted.
#
# Safe because resume is idempotent: completed episodes are skipped, and episodes that ended in an
# API error are not marked done, so they are retried on the next pass.
#
# WHY THIS SCRIPT IS NOW GUARDED. Two defects in the original version combined badly enough to be
# worth recording, because both were silent.
#
#   1. `grep -c` over MULTIPLE files prints one count per file, so `n` became "0\n0" rather than a
#      number. Every arithmetic test on it then failed with "integer expected", the completion
#      check never fired, and the loop ran its full pass budget regardless of whether the target
#      had been met. Fixed by concatenating with `cat` and counting once.
#
#   2. Nothing stopped a second copy from starting. Two copies did start, and they relaunched the
#      run each time its python process was killed -- which is why runs appeared to resurrect
#      after being terminated, and why two processes ended up competing for a single per-minute
#      rate limit, each consuming the quota the other was waiting on. Fixed by a lockfile.
#
# The script is also no longer needed for its original purpose: inference now runs on a
# self-hosted ZeroGPU Space with no rate limit. It is kept because retry-through-attrition is
# still the right shape for a metered provider, and because deleting the evidence of a defect is
# worse than fixing it.
set -uo pipefail

CONDITIONS=${CONDITIONS:-open,wipe}
MODEL=${MODEL:-qwen-space}
SEEDS=${SEEDS:-0}
TARGET=${TARGET:-12}
MAX_PASSES=${MAX_PASSES:-25}
PACE=${PACE:-0}
EXTRA=${EXTRA:-}

LOCK="${TMPDIR:-/tmp}/ars-refill-${MODEL}.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "refill: another copy is already running for ${MODEL} (lock ${LOCK}); refusing to start." >&2
  echo "If that copy is gone, remove the lock directory and retry." >&2
  exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM

good_episodes() {
  # One count over the concatenation, never one count per file.
  local total=0 f
  for cond in ${CONDITIONS//,/ }; do
    for s in ${SEEDS//,/ }; do
      f="../results/runs/${cond}__${MODEL}__s${s}/episodes.jsonl"
      [ -f "$f" ] || continue
      total=$(( total + $(cat "$f" | grep -c '"api_error":""' || true) ))
    done
  done
  printf '%s' "$total"
}

for i in $(seq 1 "$MAX_PASSES"); do
  n=$(good_episodes)
  echo "=== pass $i : ${n}/${TARGET} good episodes ==="
  if [ "$n" -ge "$TARGET" ]; then
    echo "COMPLETE"
    exit 0
  fi
  ARS_PACE_SECONDS="$PACE" python -u run.py \
    --conditions "$CONDITIONS" --models "$MODEL" --seeds "$SEEDS" $EXTRA 2>&1 \
    | grep -E "^\s+\[|done:"
  sleep "${PASS_SLEEP:-10}"
done

echo "refill: pass budget exhausted at $(good_episodes)/${TARGET} good episodes" >&2
exit 1
