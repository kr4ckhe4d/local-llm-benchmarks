#!/usr/bin/env bash
# Qwen3.8-27B, Qwen3.5-27B and Muse-Glimmer on two cards, run 2026-10-05.
# Each config: fit.sh first (per-card headroom), then the 700-token probe.
#
#   ./dense.sh qwen38      # Qwen3.8 IQ4_XS vs Q8_0: MTP at 32k/128k/256k, no drafter at 128k
#   ./dense.sh rest        # Qwen3.5-27B 64k, Muse 64k/128k
#
# Server logs go to $LOGDIR (default /tmp, which is a RAM disk on this box).
#
# The two halves were run as separate scripts on the day (dense.sh, dense2.sh);
# merged here with the configs unchanged.
set -uo pipefail
B=/home/nipuna/code/local-llm-benchmarks/benchmarks
BIN=/home/nipuna/llama.cpp/build/bin/llama-server
M=/home/nipuna/llama.cpp/models
LOGDIR=${LOGDIR:-/tmp}
. "$B/gpu-mem.sh"
PROMPT='{"messages":[{"role":"user","content":"Write a complete Python implementation of a thread-safe LRU cache class with get, put, and delete methods, full docstrings, and type hints. Then write pytest unit tests for it. Output only code."}],"max_tokens":700,"temperature":0.0,"chat_template_kwargs":{"enable_thinking":false}}'

run() {  # run <label> <model> <ctx> <flags...>
  local label=$1 model=$2 ctx=$3; shift 3
  echo "######## $label  ($model, ctx $ctx, $*)"
  MODEL=$model "$B/fit.sh" "$ctx" --load-mode dio "$@" 2>&1 | sed -E 's/flags:.*//; s/^/  /'
  [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "  -> does not fit, no probe"; return; }
  for _ in $(seq 90); do vram_idle 900 && break; sleep 1; done
  "$BIN" -m "$M/$model" -ngl 99 -np 1 -c "$ctx" --load-mode dio "$@" --host 127.0.0.1 --port 8099 \
    > "$LOGDIR/dense-$label.log" 2>&1 &
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

K="-ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
Q="--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"

if [ "${1:-qwen38}" = qwen38 ]; then
  for model in Qwen3.8-27B-UD-IQ4_XS-v3.gguf Qwen3.8-27B-Q8_0.gguf; do
    tag=${model#Qwen3.8-27B-}; tag=${tag%.gguf}
    run "$tag-128k-base" "$model" 131072 $K
    run "$tag-128k-mtp"  "$model" 131072 $K --spec-type draft-mtp
    run "$tag-256k-mtp"  "$model" 262144 $K --spec-type draft-mtp
  done
  run qwen38-iq4-32k-mtp  Qwen3.8-27B-UD-IQ4_XS-v3.gguf 32768 $K --spec-type draft-mtp $Q
  run qwen38-q8-32k-mtp   Qwen3.8-27B-Q8_0.gguf         32768 $K --spec-type draft-mtp $Q
else
  run qwen35-64k-old      Qwen3.5-27B-Uncensored-Q3_K_M.gguf 65536 -ub 512 -b 2048 -fa on -ctk q4_0 -ctv q4_0 $Q
  run qwen35-64k-new      Qwen3.5-27B-Uncensored-Q3_K_M.gguf 65536 $K $Q
  MU=(--temp 1.0 --top-p 0.95 --top-k 64 --chat-template-kwargs '{"reasoning_strength":"low"}')
  DF=(-md /home/nipuna/llama.cpp/models/dflash-kquant.gguf --spec-type draft-dflash)
  run muse-64k-old   Muse-Glimmer-30B-UD-Q3_K_XL.gguf 65536  "${DF[@]}" -ub 256 -fa on -ctk q8_0 -ctv q8_0 "${MU[@]}"
  run muse-64k-new   Muse-Glimmer-30B-UD-Q3_K_XL.gguf 65536  "${DF[@]}" -ub 512 -fa on -ctk q8_0 -ctv q8_0 "${MU[@]}"
  run muse-128k-old  Muse-Glimmer-30B-UD-Q3_K_XL.gguf 131072 -fa on -ctk q8_0 -ctv q8_0 "${MU[@]}"
  run muse-128k-new  Muse-Glimmer-30B-UD-Q3_K_XL.gguf 131072 "${DF[@]}" -ub 512 -fa on -ctk q8_0 -ctv q8_0 "${MU[@]}"
fi
