#!/usr/bin/env bash
# Is the fork + tensor split's 33 of 50 on the suite's code-quality run (2026-11-12) real?
# Repeats, on UD-Q4_K_XL v3.1, both cards, 128K, the 12-seed code-quality runs (preset sampler)
# and the suite's temperature-0 run, on a server started with --reasoning-budget 1024 as
# run-suite.sh starts it:
#
#   fork r265, tensor split    -> qwen3.8-27B-UD-Q4_K_XL-v31-rdna-fork-r265-tensor/seeds-repeat/
#   stock, layer split         -> qwen3.8-27B-UD-Q4_K_XL-v31/seeds-repeat/
#   fork r265, layer split     -> qwen3.8-27B-UD-Q4_K_XL-v31-rdna-fork-r265/seeds-repeat/   (draft 3)
#
# Written to test "thinking on", which it does not: code-quality-test.py sends
# enable_thinking false unless --thinking is given, so the server's budget is never used and
# the suite's code-quality score is a thinking-off score. What it shows instead: every seed
# reproduces its score exactly (all 36, and the 33 at temperature 0), under the tensor split
# and with a different drafter (fork layer: draft 3 here, adaptive in seeds/).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PORT=8099
SEEDS=${SEEDS:-12}
MODEL=$HOME/llama.cpp/models/Qwen3.8-27B-UD-Q4_K_XL-v31.gguf
STOCK=$HOME/llama.cpp/build/bin/llama-server
FORK=$HOME/llama.cpp-rdna-fork/build/bin/llama-server

run() {  # <label> <bin> [extra flags...]
  local label=$1 bin=$2; shift 2
  local out=$HERE/$label/seeds-repeat; mkdir -p "$out"
  "$bin" -m "$MODEL" -ngl 99 -c 131072 -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp "$@" \
    --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024 --load-mode dio \
    --host 127.0.0.1 --port $PORT > "$out/server.log" 2>&1 &
  local pid=$!
  until curl -sf http://127.0.0.1:$PORT/health > /dev/null; do
    kill -0 $pid 2>/dev/null || { echo "$label: server failed to start"; return 1; }
    sleep 1
  done
  if [[ $label == *-tensor && ! -s $out/t0-rerun.txt ]]; then
    "$HERE/code-quality-test.py" --host http://127.0.0.1:$PORT --label "$label-t0-rerun" --max-tokens 12288 > "$out/t0-rerun.txt" 2>&1
  fi
  for s in $(seq "$SEEDS"); do
    [ -s "$out/s$s.txt" ] && continue
    "$HERE/code-quality-test.py" --host http://127.0.0.1:$PORT --label "$label-repeat-s$s" --max-tokens 12288 \
      --temperature 1.0 --top-p 0.95 --extra "{\"top_k\": 20, \"min_p\": 0.0, \"seed\": $s}" > "$out/s$s.txt" 2>&1
  done
  kill $pid; wait $pid 2>/dev/null; sleep 4
  echo "$label: $(grep -h 'checks pass' "$out"/s*.txt | grep -o '[0-9]*/50' | tr '\n' ' ')"
}

run qwen3.8-27B-UD-Q4_K_XL-v31-rdna-fork-r265-tensor "$FORK"  -sm tensor --device ROCm0,ROCm1
run qwen3.8-27B-UD-Q4_K_XL-v31                       "$STOCK"
run qwen3.8-27B-UD-Q4_K_XL-v31-rdna-fork-r265        "$FORK"
