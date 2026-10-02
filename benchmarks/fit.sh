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
# ROCm; the only production build. BIN is overridable so a side build (e.g. the
# DFlash2 worktree at ~/llama.cpp-dflash2) can be measured without disturbing it.
BIN="${BIN:-$LLAMA_DIR/build/bin/llama-server}"
MODEL_DIR="$LLAMA_DIR/models"
VRAM_USED=/sys/class/drm/card1/device/mem_info_vram_used
VRAM_TOTAL=/sys/class/drm/card1/device/mem_info_vram_total
GTT_USED=/sys/class/drm/card1/device/mem_info_gtt_used
# How far GTT may drift before a row is treated as spilled. Desktop GTT moved
# <10 MiB across a whole session of measurements; a real spill moved it 150.
GTT_TOLERANCE="${GTT_TOLERANCE:-48}"
PORT="${PORT:-8099}"                             # not 8090 — don't fight the router
LOG="$(mktemp /tmp/fit-XXXXXX.log)"
TIMEOUT="${TIMEOUT:-300}"

[ $# -ge 1 ] || { echo "usage: MODEL=<file.gguf> $0 <ctx-tokens> [extra flags...]" >&2; exit 2; }
CTX="$1"; shift
MODEL="${MODEL:?set MODEL=<file.gguf> (relative to $MODEL_DIR)}"
[ -f "$MODEL_DIR/$MODEL" ] || { echo "no such model: $MODEL_DIR/$MODEL" >&2; exit 2; }

mib() { echo $(( $(cat "$1") / 1024 / 1024 )); }
TOTAL=$(mib $VRAM_TOTAL)

# Settle before reading BASE, added 2026-08-31. A killed llama-server does not
# release VRAM instantly, so back-to-back runs used to sample BASE while the
# previous model was still resident. That inflates BASE (making 'model' nonsense)
# and, worse, leaves the new run genuinely short of VRAM -- a sweep of the
# Qwen3.8 + DFlash2 drafter reported four "failed to allocate buffer for rs
# cache" failures that were pure contention: the same configs load fine on a
# quiesced card. Wait for two consecutive identical readings.
SETTLE_MAX="${SETTLE_MAX:-60}"
prev=-1
for _ in $(seq "$SETTLE_MAX"); do
  cur=$(mib $VRAM_USED)
  [ "$cur" -eq "$prev" ] && break
  prev=$cur
  sleep 1
done
[ "$cur" -eq "$prev" ] || echo "WARN  VRAM did not settle in ${SETTLE_MAX}s (last ${cur} MiB); BASE is suspect" >&2

# Refuse to measure next to another llama-server, added 2026-10-02. PORT keeps
# us off the router's socket, but not off its VRAM: a resident router model is
# silently counted as BASE, and a request that wakes it mid-run makes the fit
# number fiction. Override with ALLOW_OTHERS=1 if you mean it.
if [ -z "${ALLOW_OTHERS:-}" ] && pgrep -x llama-server >/dev/null; then
  echo "ABORT another llama-server is running (switch-model.sh stop, or ALLOW_OTHERS=1)" >&2
  pgrep -a -x llama-server | cut -c1-120 >&2
  exit 2
fi

BASE=$(mib $VRAM_USED)
GTT_BASE=$(mib $GTT_USED)

cleanup() {
  [ -n "${PID:-}" ] && kill "$PID" 2>/dev/null; wait "$PID" 2>/dev/null
  [ -n "${POLL:-}" ] && kill "$POLL" 2>/dev/null
}
trap cleanup EXIT

# -np 1 to match production, added 2026-08-31. models-preset.ini sets
# `parallel = 1` in its [*] section, so every router preset runs one slot.
# fit.sh did not, so llama.cpp auto-selected four and every row here measured a
# configuration nothing actually serves. It costs ~450 MiB at 32K even with a
# unified KV, and far more with a drafter attached: the DFlash2 drafter carries
# a recurrent-state cache that scales per slot (~630 MiB each), which is why
# four slots wanted 2,394 MiB of it. This is why the README concluded MTP caps
# at 32K on Qwen3.8 -- at the preset's own -np 1 it fits 64K with 888 MiB free.
# Override with NP= to measure a multi-slot configuration deliberately.
"$BIN" -m "$MODEL_DIR/$MODEL" -ngl 99 -c "$CTX" -np "${NP:-1}" --host 127.0.0.1 --port "$PORT" \
       "$@" >"$LOG" 2>&1 &
PID=$!

# Poll VRAM for the whole run, added 2026-10-02. PEAK used to be one sample
# taken after the probe, which misses anything transient. Measured against a
# real 128K-token prompt on the qwen3.8-128k preset, the old single sample read
# 15,763 MiB and the true peak was 15,784.
PEAKF="$LOG.peak"; echo 0 >"$PEAKF"
( p=0; while kill -0 "$PID" 2>/dev/null; do
    v=$(mib $VRAM_USED); [ "$v" -gt "$p" ] && p=$v && echo "$p" >"$PEAKF"
    sleep 0.2
  done ) &
POLL=$!

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
GTT_LOADED=$(mib $GTT_USED)

# Generation probe — forces the compute buffers to allocate for real.
# The prompt is ~PROBE_TOKENS long, added 2026-10-02: a one-line prompt never
# runs a full batch, so lazily allocated GEMM workspace (rocBLAS/hipBLASLt) was
# never touched. Default 2560 clears the presets' -b 2048.
PROBE_TOKENS="${PROBE_TOKENS:-2560}"
PROBE=$(python3 -c '
import json,sys
n=int(sys.argv[1])
print(json.dumps({"messages":[{"role":"user","content":"ok "*n+"\nReply with the single word: ok"}],
  "max_tokens":16,"cache_prompt":False,"chat_template_kwargs":{"enable_thinking":False}}))' "$PROBE_TOKENS" \
  | curl -sS --max-time 300 "http://127.0.0.1:$PORT/v1/chat/completions" \
      -H 'Content-Type: application/json' -d @- 2>&1)

if ! grep -q '"content"' <<<"$PROBE"; then
  echo "FAIL(probe)  ctx=$CTX  $*"
  grep -iE "failed to allocate|error" "$LOG" | tail -3
  exit 1
fi

POST=$(mib $VRAM_USED)
sleep 0.4  # one more poller tick
PEAK=$(cat "$PEAKF")
GTT_PEAK=$(mib $GTT_USED)
GTT_DELTA=$(( GTT_PEAK - GTT_BASE ))
# printf %+d so a negative drift reads "gtt-24", not "gtt+-24"
[ "$GTT_LOADED" -gt "$GTT_PEAK" ] && GTT_DELTA=$(( GTT_LOADED - GTT_BASE ))

# --- spill guard, added 2026-08-21 -------------------------------------------
# A config that oversubscribes VRAM does not always fail. The ROCm allocator can
# migrate buffers to host memory (GTT), after which the probe still returns and
# VRAM reads *lower* than it did at load. Sampled after the probe, the naive
# 'model=PEAK-BASE' then described the post-migration state and reported a
# comfortable fit that did not exist. (PEAK is now a polled max, so the check
# below uses POST, the post-probe sample, for this signature.)
#
# Measured case: Qwen3.8-27B v3 at 160K reported model=13313 / free=2707 while
# actually loading at 16,275 MiB (29 free) with GTT up 275 -> 425 MiB.
# Reproduced twice. Two independent signatures catch it:
#   1. POST < LOADED  -- VRAM fell after load, i.e. something moved out
#   2. GTT rose beyond tolerance -- we can see where it moved to
if [ "$POST" -lt "$LOADED" ] || [ "$GTT_DELTA" -gt "$GTT_TOLERANCE" ]; then
  echo "SPILL ctx=$CTX  loaded=${LOADED}  post=${POST}  free_at_load=$(( TOTAL - LOADED ))  gtt$(printf %+d "$GTT_DELTA")  (total=${TOTAL}, base=${BASE})  flags: $*"
  echo "      -> host-memory spill, NOT a fit. Judge by free_at_load=$(( TOTAL - LOADED )), not by peak."
  exit 1
fi

# 'model' is peak minus the desktop's own VRAM. Report it as the primary figure:
# raw peak includes whatever the compositor happens to be holding, which drifts
# between sessions. Calibrating against README's Qwen3.8-27B 32K row showed the
# raw numbers differ by 440 MiB purely from baseline drift, while the
# baseline-subtracted figure reproduced to within 1 MiB.
echo "ctx=$CTX  model=$(( PEAK - BASE ))  peak=${PEAK}  free=$(( TOTAL - PEAK ))  (total=${TOTAL}, base=${BASE}, loaded=${LOADED}, gtt$(printf %+d "$GTT_DELTA"))  flags: $*"
rm -f "$LOG" "$PEAKF"  # success only; every failure path above keeps the log
