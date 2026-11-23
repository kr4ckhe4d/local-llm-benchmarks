#!/usr/bin/env bash
# Build ~/llama.cpp-inkling and check one step of the inkling2-strata-ideas branch (see TODO.md):
#   check.sh base         save the KLD base logits from the current build (run once, on the branch start)
#   check.sh <label>      tg128 + KLD (ub 512, 16 chunks; ub 1, 4 chunks) against those logits
# R9700 only (ROCm1). Results append to results.txt next to this script.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
WT="$HOME/llama.cpp-inkling"
M=/mnt/fast/models/Inkling-2-Mini/Inkling-2-Mini-UD-Q8_K_XL.gguf
TXT="$HOME/llama.cpp/kld/wikitext-2-raw/wiki.test.raw"
KB=/mnt/fast/kld-inkling/strata-ideas
mkdir -p "$KB"
label=${1:?label or base}

cmake --build "$WT/build" -j"$(nproc)" --target llama-bench llama-perplexity test-backend-ops > "$D/last-build.log" 2>&1 \
  || { tail -20 "$D/last-build.log"; exit 1; }

kld() {  # kld <ub> <chunks> <extra args...>
  local ub=$1 ch=$2; shift 2
  "$WT/build/bin/llama-perplexity" -m "$M" -f "$TXT" -c 512 -b 512 -ub "$ub" --chunks "$ch" -fa on -lm dio \
    -dev ROCm1 "$@" 2>&1
}

if [[ $label == base ]]; then
  kld 512 16 --kl-divergence-base "$KB/base-ub512.kld" | grep -E 'Final estimate' || true
  kld 1 4 --kl-divergence-base "$KB/base-ub1.kld" | grep -E 'Final estimate' || true
  exit 0
fi

tg=$("$WT/build/bin/llama-bench" -m "$M" -dev ROCm1 -fa 1 -lm dio -p 0 -n 128 -r 3 2>&1 | awk -F'|' '/tg128/ {gsub(/ /,"",$(NF-1)); print $(NF-1)}')
k512=$(kld 512 16 --kl-divergence-base "$KB/base-ub512.kld" --kl-divergence | grep -E '^Mean +KLD|^Same top p' | tr -s ' ' | paste -sd' ')
k1=$(kld 1 4 --kl-divergence-base "$KB/base-ub1.kld" --kl-divergence | grep -E '^Mean +KLD|^Same top p' | tr -s ' ' | paste -sd' ')
line="$(date +%F' '%T) $label | $(git -C "$WT" rev-parse --short HEAD)$(git -C "$WT" diff --quiet -- ggml src || echo +dirty) | tg128 $tg | ub512: $k512 | ub1: $k1"
echo "$line" | tee -a "$D/results.txt"
