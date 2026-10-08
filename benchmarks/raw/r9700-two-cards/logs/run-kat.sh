#!/usr/bin/env bash
# KAT-Coder-V2.5-Dev Q6_K (bartowski, 30.05 GB) on two cards, 2026-10-08, b11434.
# A Qwen3.6-35B-A3B-architecture fine-tune (qwen35moe, 40 layers, 256 experts,
# 8 active, 256K native), so the Qwen3.6 presets' flags apply, plus the
# late-system template fix (its embedded template raises on a late system
# message, as Qwen3.8's did). Qwen3.6 UD-Q6_K 128k is the same-session before.
# 1. fit.sh + 700-token probe (dense.sh's run()) at 32K/128K/256K.
# 2. depth_sweep.sh at 32K and 128K.
#
#   ./logs/run-kat.sh 2>&1 | tee logs/kat.txt
set -uo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
B=/home/nipuna/code/local-llm-benchmarks/benchmarks
BIN=/home/nipuna/llama.cpp/build/bin/llama-server
M=/home/nipuna/llama.cpp/models
T=/home/nipuna/code/local-llm-benchmarks/templates
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
    > "$LOGDIR/kat-$label.log" 2>&1 &
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
KAT=Kwaipilot_KAT-Coder-V2.5-Dev-Q6_K.gguf
Q36=Qwen3.6-35B-A3B-UD-Q6_K.gguf
TK="--chat-template-file $T/kat-coder-late-system.jinja"

run qwen36-q6-128k $Q36 131072 $P
run kat-q6-32k     $KAT 32768  $P $TK
run kat-q6-128k    $KAT 131072 $P $TK
run kat-q6-256k    $KAT 262144 $P $TK

export LOGDIR
"$HERE/depth_sweep.sh" kat-q6-depth $KAT "32000 128000" $P $TK
