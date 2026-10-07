#!/usr/bin/env bash
# GLM-4.7-Flash Q8_0 vs the UD-Q4_K_XL the presets run, 2026-10-07, b11434.
# 1. fit.sh + 700-token probe (dense.sh's run(), unchanged): Q4 128K as the
#    before, Q8 at the three preset contexts, preset flags as written.
# 2. depth_sweep.sh on Q8, to locate the 128K collapse in
#    depth-presets.txt: (a) preset flags, (b) -fa on with f16 KV, (c) -fa off
#    with f16 KV (llama.cpp needs flash attention for a quantized V cache, so
#    (b) is what separates the -fa effect from the KV type), and Qwen3.6 at
#    the same depths as a non-MLA control.
#
#   ./logs/run-glm-q8.sh 2>&1 | tee logs/glm-q8.txt
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
  [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "  -> does not fit, no probe"; return; }
  for _ in $(seq 90); do vram_idle 900 && break; sleep 1; done
  "$BIN" -m "$M/$model" -ngl 99 -np 1 -c "$ctx" --load-mode dio "$@" --host 127.0.0.1 --port 8099 \
    > "$LOGDIR/glmq8-$label.log" 2>&1 &
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

S="--temp 1.0 --top-p 0.95 --min-p 0.01 --repeat-penalty 1.0 --reasoning-budget 1024"
P="-ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 $S"
Q4=GLM-4.7-Flash-UD-Q4_K_XL.gguf
Q8=GLM-4.7-Flash-Q8_0.gguf

run q4-128k $Q4 131072 $P
run q8-32k  $Q8 32768  $P
run q8-128k $Q8 131072 $P
run q8-200k $Q8 202752 -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0 $S

W="$HERE/depth_sweep.sh"
export LOGDIR
"$W" glm-q8-a-fa-q8kv   $Q8 "8000 32000 64000 128000" -ub 1024 -b 2048 -fa on  -ctk q8_0 -ctv q8_0 $S
"$W" glm-q8-b-fa-f16kv  $Q8 "8000 32000 64000"        -ub 1024 -b 2048 -fa on  $S
"$W" glm-q8-c-nofa-f16  $Q8 "8000 32000 64000"        -ub 1024 -b 2048 -fa off $S
"$W" qwen36-control     Qwen3.6-35B-A3B-UD-Q4_K_M.gguf "8000 32000 64000 128000" \
     -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 1.5 --reasoning-budget 4096
