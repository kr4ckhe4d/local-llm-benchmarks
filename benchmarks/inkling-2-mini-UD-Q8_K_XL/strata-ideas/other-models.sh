#!/usr/bin/env bash
# The router's other models on the branch: KLD against ~/llama.cpp (db75ce3dc, the branch start) and tg128.
set -uo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
BASE=$HOME/llama.cpp/build/bin
NEW=$HOME/llama.cpp-inkling/build/bin
TXT=$HOME/llama.cpp/kld/wikitext-2-raw/wiki.test.raw
KB=/mnt/fast/kld-inkling/strata-ideas
OUT=$D/other-models.txt
echo "# $(date +%F) branch $(git -C ~/llama.cpp-inkling rev-parse --short HEAD) vs ~/llama.cpp $(git -C ~/llama.cpp rev-parse --short HEAD)" > $OUT
run() {  # run <label> <gguf> <dev args...>
  local lab=$1 m=$2; shift 2
  for ub in 512 1; do
    local ch=8; [ $ub = 1 ] && ch=3
    $BASE/llama-perplexity -m $m -f $TXT -c 512 -b 512 -ub $ub --chunks $ch -fa on -lm dio "$@" --kl-divergence-base $KB/$lab-ub$ub.kld > /dev/null 2>&1
    echo "$lab ub=$ub $($NEW/llama-perplexity -m $m -f $TXT -c 512 -b 512 -ub $ub --chunks $ch -fa on -lm dio "$@" --kl-divergence-base $KB/$lab-ub$ub.kld --kl-divergence 2>&1 | grep -E '^Mean +KLD|^Same top' | tr -s ' ' | paste -sd' ')" >> $OUT
  done
  echo "$lab tg128 base $($BASE/llama-bench -m $m -fa 1 -lm dio -p 0 -n 128 -r 3 "${@/#-dev/-dev}" 2>&1 | awk -F'|' '/tg128/{gsub(/ /,"",$(NF-1)); print $(NF-1)}') branch $($NEW/llama-bench -m $m -fa 1 -lm dio -p 0 -n 128 -r 3 "$@" 2>&1 | awk -F'|' '/tg128/{gsub(/ /,"",$(NF-1)); print $(NF-1)}')" >> $OUT
}
run gemma4-bf16 /mnt/fast/models/gemma-4-12B-it-BF16.gguf -dev ROCm1
run qwen38-q6 /mnt/fast/models/Qwen3.8-27B-UD-Q6_K.gguf
echo "=== done" >> $OUT
