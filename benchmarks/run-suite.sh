#!/usr/bin/env bash
# Run the probe suite against one model and write every output into that
# model's folder. The point is that the folders are *generated*, not
# hand-assembled -- a result you cannot regenerate is a claim, not a
# measurement.
#
#   ./run-suite.sh qwen3.8-27B-UD-IQ3_XXS-v3 Qwen3.8-27B-UD-IQ3_XXS-v3.gguf \
#       196608 "-ub 512 -b 2048 -fa on -ctk q4_0 -ctv q4_0"
#
# Probes that need a specific depth (deep needle/semantic at 190K) are not run
# here -- they cost ~12 minutes of prefill each and are driven by hand. Their
# captured output lives in the model folder alongside these.
set -uo pipefail

LLAMA_DIR="$HOME/llama.cpp"
# Overridable so a side build (e.g. the DFlash2 worktree at ~/llama.cpp-dflash2)
# can be measured without disturbing the production build. The header written
# into each output file records the build actually used.
BIN="${BIN:-$LLAMA_DIR/build/bin/llama-server}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8099}"
VRAM=/sys/class/drm/card1/device/mem_info_vram_used
GTT=/sys/class/drm/card1/device/mem_info_gtt_used

[ $# -ge 4 ] || { echo "usage: $0 <out-dir> <model.gguf> <ctx> \"<flags>\" [extra-server-flags]" >&2; exit 2; }
LABEL="$1"; OUTDIR="$HERE/$1"; MODEL="$2"; CTX="$3"; FLAGS="$4"; shift 4
EXTRA=("$@")
mkdir -p "$OUTDIR"

mib() { echo $(( $(cat "$1") / 1048576 )); }
settle() { for _ in $(seq 60); do [ "$(mib $VRAM)" -lt 900 ] && return 0; sleep 1; done; return 1; }

hdr() {
  printf '# %s\n# model : %s\n# ctx   : %s\n# flags : %s %s\n# host  : %s, llama.cpp %s\n# date  : %s\n\n' \
    "$1" "$MODEL" "$CTX" "$FLAGS" "${EXTRA[*]}" \
    "$(uname -sr)" "$("$BIN" --version 2>&1 | head -1)" "$(date -Is)"
}

settle
echo "==> starting $MODEL @ $CTX"
LOG=$(mktemp /tmp/suite-XXXXXX.log)
# shellcheck disable=SC2086
"$BIN" -m "$LLAMA_DIR/models/$MODEL" -ngl 99 -c "$CTX" $FLAGS "${EXTRA[@]}" \
  --host 127.0.0.1 --port "$PORT" \
  --reasoning-budget 1024 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 >"$LOG" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null; wait $PID 2>/dev/null' EXIT

for _ in $(seq 600); do
  grep -q "listening on" "$LOG" && break
  kill -0 $PID 2>/dev/null || { echo "LOAD FAILED"; grep -iE "failed|error" "$LOG" | tail -3; exit 1; }
  sleep 1
done
echo "    up. VRAM $(mib $VRAM) MiB, GTT $(mib $GTT) MiB"

H="http://127.0.0.1:$PORT"

# --- throughput, n=3 ---------------------------------------------------------
# max_tokens stays 700 here on purpose: this measures tok/s over a FIXED
# generation length, so 700 is the unit every throughput number in the
# README was measured at. Raising it would redefine the benchmark, not fix
# it -- truncation cannot bias a timing measurement. The quality harnesses
# below use 12288 for the opposite reason; see needle-test.py.
{ hdr "throughput -- 700-token code-generation prompt, temperature 0.0, n=3"
  for i in 1 2 3; do
    curl -sS --max-time 900 "$H/v1/chat/completions" -H 'Content-Type: application/json' \
      -d '{"messages":[{"role":"user","content":"Write a complete Python implementation of a thread-safe LRU cache class with get, put, and delete methods, full docstrings, and type hints. Then write pytest unit tests for it. Output only code."}],"max_tokens":700,"temperature":0.0,"chat_template_kwargs":{"enable_thinking":false}}' \
    | python3 -c "
import sys,json
t=json.load(sys.stdin)['timings']
print(f\"run$i  pp {t['prompt_per_second']:8.1f} tok/s | tg {t['predicted_per_second']:6.2f} tok/s | {t['predicted_n']:4d} tok in {t['predicted_ms']/1000:6.2f}s\")"
  done
  printf '\nVRAM %s MiB | GTT %s MiB\n' "$(mib $VRAM)" "$(mib $GTT)"
} > "$OUTDIR/throughput.txt" 2>&1
echo "    throughput.txt"

# --- tool calling ------------------------------------------------------------
{ hdr "native tool calling -- single and parallel"
  python3 "$HERE/tool-calling-test.py" "$H"
} > "$OUTDIR/tool-calling.txt" 2>&1
echo "    tool-calling.txt"

# --- coding quality ----------------------------------------------------------
{ hdr "code quality -- differential vs stdlib, 50 checks, temperature 0.0"
  "$HERE/code-quality-test.py" --host "$H" --label "$LABEL" --max-tokens 12288
} > "$OUTDIR/code-quality.txt" 2>&1
echo "    code-quality.txt"

# --- CDN / library freshness -------------------------------------------------
{ hdr "library freshness -- 3 prompts x 3 runs, HEAD every emitted URL"
  "$HERE/cdn-freshness-test.py" --host "$H" --runs 3 --label "$LABEL"
} > "$OUTDIR/cdn-freshness.txt" 2>&1
echo "    cdn-freshness.txt"

echo "==> done: $OUTDIR"
