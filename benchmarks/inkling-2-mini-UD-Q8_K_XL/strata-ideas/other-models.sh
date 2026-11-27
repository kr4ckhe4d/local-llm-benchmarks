#!/usr/bin/env bash
# The router's other on-disk models across three builds, to separate what the branch does from what
# upstream did. Generation only: the saved KLD bases under /mnt/fast/kld-inkling/strata-ideas/ were
# captured on db75ce3dc, so they no longer isolate anything once the branch has been rebased.
#
#   PRE=<worktree>  UPS=<worktree>  BR=<worktree>  ./other-models.sh
#
# Defaults are the worktrees left from the 2026-11-27 rebase. The old two-way form compared
# ~/llama.cpp against ~/llama.cpp-inkling; those are the same commit whenever the router is current,
# which made it compare a build against itself.
set -uo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
PRE=${PRE:-$HOME/llama.cpp-prerebase}
UPS=${UPS:-$HOME/llama.cpp-upstream}
BR=${BR:-$HOME/llama.cpp-inkling}
OUT=$D/other-models.txt

declare -A B=( [pre-rebase]=$PRE [upstream]=$UPS [branch]=$BR )
ORDER=(pre-rebase upstream branch)

{
  echo "# $(date +%F) tg128, -fa 1 -lm dio -p 0 -n 128 -r 3"
  for k in "${ORDER[@]}"; do
    printf "#   %-11s %s %s\n" "$k" "$(git -C "${B[$k]}" rev-parse --short HEAD)" "${B[$k]}"
  done
} > "$OUT"

bench() {  # bench <label> <gguf> <extra args...>
  local lab=$1 m=$2; shift 2
  [ -f "$m" ] || { echo "$lab MISSING $m" >> "$OUT"; return; }
  for k in "${ORDER[@]}"; do
    local t
    t=$("${B[$k]}/build/bin/llama-bench" -m "$m" -fa 1 -lm dio -p 0 -n 128 -r 3 "$@" 2>&1 \
        | awk -F'|' '/tg128/{gsub(/ /,"",$(NF-1)); print $(NF-1)}')
    printf "%-14s %-11s %s\n" "$lab" "$k" "${t:-FAILED}" >> "$OUT"
  done
}

bench gemma4-bf16 /mnt/fast/models/gemma-4-12B-it-BF16.gguf -dev ROCm1
bench qwen38-q6   /mnt/fast/models/Qwen3.8-27B-UD-Q6_K.gguf
echo "=== done" >> "$OUT"
