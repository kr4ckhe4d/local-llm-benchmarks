#!/usr/bin/env bash
# A/B: old build (7c35571e5) vs new (a868c3e3c), Qwen3.8 presets, ABBA order.
set -uo pipefail
OLD=$HOME/llama.cpp-7c35571e5/build/bin/llama-server
NEW=$HOME/llama.cpp/build/bin/llama-server
M=/mnt/fast/models
PROBE=$HOME/code/local-llm-benchmarks/benchmarks/throughput-test.py
OUT=${OUT:-$(dirname "$0")/ab}
VRAM=/sys/class/drm/card1/device/mem_info_vram_used
GTT=/sys/class/drm/card1/device/mem_info_gtt_used
PORT=8099; H=http://127.0.0.1:$PORT
mkdir -p "$OUT"
mib() { echo $(( $(cat "$1") / 1048576 )); }

declare -A CFG=(
  [32k]="-m $M/Qwen3.8-27B-UD-IQ4_XS-v3.gguf -c 32768 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  [32k-mtp]="-m $M/Qwen3.8-27B-UD-Q3_K_XL-v3.gguf -c 32768 -ub 512 -b 2048 -fa on -ctk q4_0 -ctv q4_0 --spec-type draft-mtp"
)

run() {  # $1 label, $2 build tag, $3 bin
  local cfg=$1 tag=$2 bin=$3 log="$OUT/$1.$2.server.log" res="$OUT/$1.$2.txt"
  for _ in $(seq 60); do [ "$(mib $VRAM)" -lt 900 ] && break; sleep 1; done
  echo "==> $cfg / $tag  $(date +%T)"
  # shellcheck disable=SC2086
  "$bin" ${CFG[$cfg]} -ngl 99 -np 1 --host 127.0.0.1 --port $PORT >"$log" 2>&1 &
  local pid=$!
  for _ in $(seq 600); do
    grep -q "listening on" "$log" && break
    kill -0 $pid 2>/dev/null || { echo "LOAD FAILED"; tail -3 "$log"; return 1; }
    sleep 1
  done
  { echo "## $cfg $tag $("$bin" --version 2>&1 | grep version) $(date -Is)"
    echo "## loaded: VRAM $(mib $VRAM) MiB, GTT $(mib $GTT) MiB"
    echo "### shallow"; python3 "$PROBE" --host $H --runs 3 --json "$OUT/$cfg.$tag.jsonl"
    echo "### depth 16384"; python3 "$PROBE" --host $H --runs 2 --depth 16384 --json "$OUT/$cfg.$tag.jsonl"
    echo "## peak-ish: VRAM $(mib $VRAM) MiB, GTT $(mib $GTT) MiB"
  } >> "$res" 2>&1
  kill $pid; wait $pid 2>/dev/null
  tail -n +1 "$res" | grep -E "^(prompt|tg|draft) " | tail -6 | sed 's/^/    /'
}

for cfg in 32k-mtp 32k; do
  run $cfg old $OLD; run $cfg new $NEW; run $cfg new $NEW; run $cfg old $OLD
done
echo "ALL DONE $(date +%T)"
