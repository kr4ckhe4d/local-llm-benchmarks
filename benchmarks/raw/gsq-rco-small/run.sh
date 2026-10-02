#!/usr/bin/env bash
# GSQ-RCO IQ3_XXS-mtp and IQ2_S-mtp against UD-Q3_K_XL-v3, all on a868c3e3c.
# Fidelity (KLD vs the Q8_0 base), speed with and without MTP, batched forward
# pass, and how far MTP reaches in context. Q3_K_XL-v3 is re-run alongside as
# the same-build control rather than borrowed from 7c35571e5 records.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; B="$HERE/../.."
BIN=$HOME/llama.cpp/build/bin
M=$HOME/llama.cpp/models
PORT=8099; H=http://127.0.0.1:$PORT
VRAM=/sys/class/drm/card1/device/mem_info_vram_used
mib() { echo $(( $(cat "$1") / 1048576 )); }
settle() { for _ in $(seq 60); do [ "$(mib $VRAM)" -lt 900 ] && return; sleep 1; done; }

declare -A F=(
  [q3kxl]=Qwen3.8-27B-UD-Q3_K_XL-v3.gguf
  [iq3xxs]=Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf
  [iq2s]=Qwen3.8-27B-GSQ-RCO-IQ2_S-mtp.gguf
)
ORDER="q3kxl iq3xxs iq2s"
MTPFLAGS="-c 32768 -ub 512 -b 2048 -fa on -ctk q4_0 -ctv q4_0"

echo "### 1. KLD vs Q8_0 base  $(date +%T)"
cd "$B"
for k in $ORDER; do
  BASE_FILE=$HOME/llama.cpp/kld/qwen3.8-27B-q8_0.kld \
    ./kld-test.sh score "raw/gsq-rco-small/kld-$k" "${F[$k]}" 200 "-ngl 99" >/dev/null 2>&1
  printf '%-7s ' "$k"; grep -E "^Mean +KLD|^Same top p|Median +KLD" "raw/gsq-rco-small/kld-$k/kld.txt" | tr -s ' ' | tr '\n' '|'; echo
done

echo "### 2. throughput, 32k-mtp flags, with and without MTP  $(date +%T)"
for k in $ORDER; do for spec in "" "--spec-type draft-mtp"; do
  tag=$k$([ -n "$spec" ] && echo .mtp || echo .nomtp); log="$HERE/tp-$tag.log"
  settle
  # shellcheck disable=SC2086
  "$BIN/llama-server" -m "$M/${F[$k]}" -ngl 99 -np 1 $MTPFLAGS $spec --host 127.0.0.1 --port $PORT >"$log" 2>&1 &
  pid=$!
  until grep -q "listening on" "$log"; do kill -0 $pid 2>/dev/null || { echo "$tag LOAD FAILED"; break; }; sleep 1; done
  if kill -0 $pid 2>/dev/null; then
    { echo "## $tag"; python3 "$B/throughput-test.py" --host $H --runs 3
      echo "## $tag depth"; python3 "$B/throughput-test.py" --host $H --runs 2 --depth 16384
      echo "VRAM $(mib $VRAM)"; } > "$HERE/tp-$tag.txt" 2>&1
    printf '%-14s ' "$tag"; grep -E "^(tg|draft) " "$HERE/tp-$tag.txt" | tr -s ' ' | tr '\n' '|'; echo
    kill $pid; wait $pid 2>/dev/null
  fi
done; done

echo "### 3. batched forward pass (where MTP verifies)  $(date +%T)"
for k in $ORDER; do
  settle
  "$BIN/llama-bench" -m "$M/${F[$k]}" -ngl 99 -fa 1 -p 1,2,4,8 -n 0 -r 3 -o md 2>/dev/null \
    | grep -E "pp[0-9]" | awk -v k=$k -F'|' '{printf "%s %s %s\n", k, $(NF-2), $(NF-1)}'
done | tee "$HERE/bench.txt"

echo "### 4. MTP context reach (fit.sh)  $(date +%T)"
for k in iq3xxs iq2s; do
  for c in 65536 131072; do for kv in q8_0 q4_0; do
    MODEL=${F[$k]} "$B/fit.sh" $c -ub 512 -b 2048 -fa on -ctk $kv -ctv $kv --spec-type draft-mtp 2>&1 \
      | grep -E "^(ctx|FAIL|SPILL|TIMEOUT|ABORT)" | sed "s/^/$k /"
  done; done
done | tee "$HERE/fit.txt"
echo "ALL DONE $(date +%T)"
