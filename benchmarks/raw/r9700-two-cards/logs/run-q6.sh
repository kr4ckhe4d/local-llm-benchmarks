#!/usr/bin/env bash
# Qwen3.8-27B IQ4_XS vs UD-Q6_K vs Q8_0 at 128k, plus Q6_K at 256k: the 128k
# presets' flags + MTP, run back to back on one build. First run 2026-10-06
# from a session scratchpad (lost to a reboot, like the 10-05 logs); this is
# that script with LOGDIR pointed here, rerun 2026-10-07 for captured output.
# run() is dense.sh's, unchanged apart from the log name.
#
#   ./logs/run-q6.sh | tee logs/q6-vs-q8.txt
set -uo pipefail
B=/home/nipuna/code/local-llm-benchmarks/benchmarks
BIN=/home/nipuna/llama.cpp/build/bin/llama-server
M=/home/nipuna/llama.cpp/models
LOGDIR=${LOGDIR:-$(cd "$(dirname "$0")" && pwd)}
. "$B/gpu-mem.sh"
PROMPT='{"messages":[{"role":"user","content":"Write a complete Python implementation of a thread-safe LRU cache class with get, put, and delete methods, full docstrings, and type hints. Then write pytest unit tests for it. Output only code."}],"max_tokens":700,"temperature":0.0,"chat_template_kwargs":{"enable_thinking":false}}'

run() {  # run <label> <model> <ctx> <flags...>
  local label=$1 model=$2 ctx=$3; shift 3
  echo "######## $label  ($model, ctx $ctx, $*)"
  MODEL=$model "$B/fit.sh" "$ctx" --load-mode dio "$@" 2>&1 | sed -E 's/flags:.*//; s/^/  /'
  [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "  -> does not fit, no probe"; return; }
  for _ in $(seq 90); do vram_idle 900 && break; sleep 1; done
  "$BIN" -m "$M/$model" -ngl 99 -np 1 -c "$ctx" --load-mode dio "$@" --host 127.0.0.1 --port 8099 \
    > "$LOGDIR/dense-q6cmp-$label.log" 2>&1 &
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

K="-ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp"
run iq4xs-128k Qwen3.8-27B-UD-IQ4_XS-v3.gguf 131072 $K
run q6k-128k   Qwen3.8-27B-UD-Q6_K.gguf      131072 $K
run q8-128k    Qwen3.8-27B-Q8_0.gguf         131072 $K
run q6k-256k   Qwen3.8-27B-UD-Q6_K.gguf      262144 $K
