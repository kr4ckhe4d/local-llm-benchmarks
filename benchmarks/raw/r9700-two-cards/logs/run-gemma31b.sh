#!/usr/bin/env bash
# Gemma 4 31B (dense) Q6_K + MTP on two cards, 2026-10-07, b11434.
# 1. fit.sh + 700-token probe (dense.sh's run()). The 26B-A4B presets' flags
#    as written (MTP drafter, reasoning-budget, repeat-penalty, no -fa/-ctk)
#    first, then -fa on with q8_0 KV: 31B is dense with 16 KV heads of 256,
#    so its KV is far larger than the MoE's. The 26B-A4B Q4 128k preset is
#    rerun as the same-build before. Vision (mmproj) fit-checked at 128K.
# 2. depth_sweep.sh at 32K and 128K for the 128K config that fits.
#
#   ./logs/run-gemma31b.sh 2>&1 | tee logs/gemma31b.txt
set -uo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
B=/home/nipuna/code/local-llm-benchmarks/benchmarks
BIN=/home/nipuna/llama.cpp/build/bin/llama-server
M=/home/nipuna/llama.cpp/models
LOGDIR=${LOGDIR:-$HERE/logs}
. "$B/gpu-mem.sh"
PROMPT='{"messages":[{"role":"user","content":"Write a complete Python implementation of a thread-safe LRU cache class with get, put, and delete methods, full docstrings, and type hints. Then write pytest unit tests for it. Output only code."}],"max_tokens":700,"temperature":0.0,"chat_template_kwargs":{"enable_thinking":false}}'

run() {  # run <label> <model> <ctx> <flags...>   (dense.sh's, log name aside)
  local label=$1 model=$2 ctx=$3; shift 3
  echo "######## $label  ($model, ctx $ctx, $*)"
  MODEL=$model "$B/fit.sh" "$ctx" --load-mode dio "$@" 2>&1 | sed -E 's/flags:.*//; s/^/  /'
  [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "  -> does not fit, no probe"; return 1; }
  for _ in $(seq 90); do vram_idle 900 && break; sleep 1; done
  "$BIN" -m "$M/$model" -ngl 99 -np 1 -c "$ctx" --load-mode dio "$@" --host 127.0.0.1 --port 8099 \
    > "$LOGDIR/gemma31b-$label.log" 2>&1 &
  local pid=$!
  for _ in $(seq 300); do curl -s localhost:8099/health 2>/dev/null | grep -q ok && break; sleep 1; done
  for i in 1 2 3; do
    curl -sS --max-time 900 localhost:8099/v1/chat/completions -H 'Content-Type: application/json' -d "$PROMPT" \
    | python3 -c "
import sys,json
t=json.load(sys.stdin)['timings']; dn=t.get('draft_n',0); da=t.get('draft_n_accepted',0)
acc=f' | draft {100*da/dn:.1f}%' if dn else ''
print(f\"  run$i tg {t['predicted_per_second']:6.2f} tok/s{acc}\")"
  done
  kill $pid; wait $pid 2>/dev/null
}

G26=gemma-4-26B-A4B-it-UD-Q4_K_M.gguf
G31=gemma-4-31B-it-Q6_K.gguf
P26="--model-draft $M/mtp-gemma-4-26B-A4B-it.gguf --spec-type draft-mtp --reasoning-budget 1024 --repeat-penalty 1.05"
P31="--model-draft $M/mtp-gemma-4-31B-it.gguf --spec-type draft-mtp --reasoning-budget 1024 --repeat-penalty 1.05"
KV="-fa on -ctk q8_0 -ctv q8_0"

run g26-q4-128k      $G26 131072 $P26
run g31-q6-32k       $G31 32768  $P31
run g31-q6-128k      $G31 131072 $P31
run g31-q6-32k-q8kv  $G31 32768  $P31 $KV
run g31-q6-128k-q8kv $G31 131072 $P31 $KV
run g31-q6-256k-q8kv $G31 262144 $P31 $KV
run g31-q6-128k-q8kv-nomtp $G31 131072 --reasoning-budget 1024 --repeat-penalty 1.05 $KV
echo "######## vision fit only"
MODEL=$G31 "$B/fit.sh" 131072 --load-mode dio $P31 $KV --mmproj "$M/mmproj-gemma-4-31B-F16.gguf" 2>&1 | sed -E 's/flags:.*//; s/^/  /'

export LOGDIR
if grep -q "g31-q6-128k  " "$LOGDIR/gemma31b.txt" 2>/dev/null && ! sed -n '/g31-q6-128k  /,/########/p' "$LOGDIR/gemma31b.txt" | grep -q "does not fit"; then
  "$HERE/depth_sweep.sh" g31-q6-depth-f16kv $G31 "32000 128000" $P31
fi
"$HERE/depth_sweep.sh" g31-q6-depth-q8kv $G31 "32000 128000" $P31 $KV
