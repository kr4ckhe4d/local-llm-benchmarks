#!/usr/bin/env bash
# Qwen3.6-35B-A3B: UD-Q4_K_M (the presets) vs UD-Q6_K vs Q8_0, 2026-10-07, b11434.
# 1. fit.sh + 700-token probe (dense.sh's run()), the presets' flags as
#    written: Q4 128K as the before, Q6 and Q8 at 32K/128K/256K.
# 2. depth_sweep.sh at 32K and 128K for Q6 and Q8 (Q4 at the same depths is
#    in glm-q8.txt, qwen36-control, same build and flags).
# 3. KLD with Q8_0 as the reference (kld-test.sh's q8ref convention, which
#    reproduced BF16-referenced numbers within 1.5% for Qwen3.8): Q4 and Q6.
#
#   ./logs/run-qwen36-quants.sh 2>&1 | tee logs/qwen36-quants.txt
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
    > "$LOGDIR/qwen36q-$label.log" 2>&1 &
  local pid=$!
  for _ in $(seq 300); do curl -s localhost:8099/health 2>/dev/null | grep -q ok && break; sleep 1; done
  for i in 1 2 3; do
    curl -sS --max-time 900 localhost:8099/v1/chat/completions -H 'Content-Type: application/json' -d "$PROMPT" \
    | python3 -c "
import sys,json
t=json.load(sys.stdin)['timings']
print(f\"  run$i tg {t['predicted_per_second']:6.2f} tok/s\")"
  done
  kill $pid; wait $pid 2>/dev/null
}

P="-ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 1.5 --reasoning-budget 4096"
Q4=Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
Q6=Qwen3.6-35B-A3B-UD-Q6_K.gguf
Q8=Qwen3.6-35B-A3B-Q8_0.gguf

run q4-128k $Q4 131072 $P
for q in q6:$Q6 q8:$Q8; do
  tag=${q%%:*}; f=${q#*:}
  run $tag-32k  $f 32768  $P
  run $tag-128k $f 131072 $P
  run $tag-256k $f 262144 $P
done

export LOGDIR
"$HERE/depth_sweep.sh" qwen36-q6-depth $Q6 "32000 128000" $P
"$HERE/depth_sweep.sh" qwen36-q8-depth $Q8 "32000 128000" $P

# -lm dio: llama-perplexity loads with mmap by default, and the 36.9 GB Q8 file
# on 32 GB of RAM thrashed the page cache (first attempt: 14 min, GPUs idle,
# no output; the r9700 doc's Laguna Q8 mmap timeout, again).
echo "######## KLD, Q8_0 reference, 200 chunks at -c 512"
export BASE_FILE=/home/nipuna/llama.cpp/kld/qwen3.6-35B-A3B-q8_0.kld
"$B/kld-test.sh" base  $Q8 200 "-ngl 99 -lm dio"
"$B/kld-test.sh" score q8ref/qwen3.6-35B-A3B-UD-Q4_K_M $Q4 200 "-ngl 99 -lm dio"
"$B/kld-test.sh" score q8ref/qwen3.6-35B-A3B-UD-Q6_K   $Q6 200 "-ngl 99 -lm dio"
for l in UD-Q4_K_M UD-Q6_K; do
  echo "== $l"; grep -E "Mean +KLD|Same top p|Median +KLD|99\.0%" "$B/q8ref/qwen3.6-35B-A3B-$l/kld.txt"
done
