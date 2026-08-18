#!/usr/bin/env bash
# Measure whether a model+context+flags combination actually fits in VRAM.
#
# Recreated 2026-08-18 (the original lived in a session scratchpad and was
# lost). This is the tool behind every "VRAM used / Free" row in README.md:
# launch llama-server, wait for it to listen, read VRAM while the model is
# resident, send a real generation probe so the compute buffers are actually
# allocated, then kill it.
#
#   MODEL=Qwen3.8-27B-UD-Q3_K_XL.gguf ./fit.sh 32768 -ub 1024 -b 2048 -fa on
#
# The generation probe matters. Reading VRAM straight after "listening on"
# undercounts: llama-server allocates lazily, so a config can look like it fits
# and then fail on the first request. A row is only real if the probe returns.
set -uo pipefail

LLAMA_DIR="$HOME/llama.cpp"
BIN="$LLAMA_DIR/build/bin/llama-server"          # ROCm; the only build now
MODEL_DIR="$LLAMA_DIR/models"
VRAM_USED=/sys/class/drm/card1/device/mem_info_vram_used
VRAM_TOTAL=/sys/class/drm/card1/device/mem_info_vram_total
PORT="${PORT:-8099}"                             # not 8090 — don't fight the router
LOG="$(mktemp /tmp/fit-XXXXXX.log)"
TIMEOUT="${TIMEOUT:-300}"

[ $# -ge 1 ] || { echo "usage: MODEL=<file.gguf> $0 <ctx-tokens> [extra flags...]" >&2; exit 2; }
CTX="$1"; shift
MODEL="${MODEL:?set MODEL=<file.gguf> (relative to $MODEL_DIR)}"
[ -f "$MODEL_DIR/$MODEL" ] || { echo "no such model: $MODEL_DIR/$MODEL" >&2; exit 2; }

mib() { echo $(( $(cat "$1") / 1024 / 1024 )); }
TOTAL=$(mib $VRAM_TOTAL)
BASE=$(mib $VRAM_USED)

cleanup() { [ -n "${PID:-}" ] && kill "$PID" 2>/dev/null; wait "$PID" 2>/dev/null; }
trap cleanup EXIT

"$BIN" -m "$MODEL_DIR/$MODEL" -ngl 99 -c "$CTX" --host 127.0.0.1 --port "$PORT" \
       "$@" >"$LOG" 2>&1 &
PID=$!

# Wait for listen, but give up if the process dies (OOM shows up as a dead
# process plus a "failed to allocate" line, which is worth reporting verbatim).
for _ in $(seq "$TIMEOUT"); do
  grep -q "listening on" "$LOG" && break
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "FAIL  ctx=$CTX  $*"
    grep -iE "failed to allocate|error|unable" "$LOG" | tail -3
    exit 1
  fi
  sleep 1
done
grep -q "listening on" "$LOG" || { echo "TIMEOUT after ${TIMEOUT}s  ctx=$CTX  $*"; exit 1; }

LOADED=$(mib $VRAM_USED)

# Generation probe — forces the compute buffers to allocate for real.
PROBE=$(curl -sS --max-time 120 "http://127.0.0.1:$PORT/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Reply with the single word: ok"}],"max_tokens":16}' \
  2>&1)

if ! grep -q '"content"' <<<"$PROBE"; then
  echo "FAIL(probe)  ctx=$CTX  $*"
  grep -iE "failed to allocate|error" "$LOG" | tail -3
  exit 1
fi

PEAK=$(mib $VRAM_USED)
# 'model' is peak minus the desktop's own VRAM. Report it as the primary figure:
# raw peak includes whatever the compositor happens to be holding, which drifts
# between sessions. Calibrating against README's Qwen3.8-27B 32K row showed the
# raw numbers differ by 440 MiB purely from baseline drift, while the
# baseline-subtracted figure reproduced to within 1 MiB.
echo "ctx=$CTX  model=$(( PEAK - BASE ))  peak=${PEAK}  free=$(( TOTAL - PEAK ))  (total=${TOTAL}, base=${BASE}, loaded=${LOADED})  flags: $*"
