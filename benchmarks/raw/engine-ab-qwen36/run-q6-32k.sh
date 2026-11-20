#!/usr/bin/env bash
# Qwen3.6-35B-A3B: llama.cpp (both cards, the old q6-128k preset's flags) against
# Strata (R9700 alone, its own qwen35 engine path), on the SAME Unsloth MTP GGUFs,
# 128K context. Client: ../../engine-ab.py. Arms run one at a time; every server is
# started here and killed here, so the GPUs end as they started (idle; the router
# was not running on 2026-11-15).
# Copy of run.sh for the Strata Q6 retry at 32K context (ARMS=strata-q6-32k).
set -uo pipefail
B=/home/nipuna/code/local-llm-benchmarks/benchmarks
D=$B/raw/engine-ab-qwen36
OUT=$D/results.jsonl
DL=${DL:-/tmp/claude-1000/-home-nipuna-code-local-llm-benchmarks/1a143942-35f7-4692-a04a-f4c97d6cc5c1/scratchpad/q36-download.log}
LLAMA=/home/nipuna/llama.cpp/build/bin/llama-server
STRATA=/home/nipuna/code/Strata
Q6=/mnt/fast/strata-data/models/qwen36-UD-Q6_K_XL/Qwen3.6-35B-A3B-UD-Q6_K_XL.gguf
Q4=/mnt/fast/strata-data/models/qwen36-UD-Q4_K_XL/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
ARMS=${ARMS:-llama-q6 llama-q6-mtp strata-q6 llama-q4-mtp strata-q4}
. "$B/gpu-mem.sh"
mkdir -p "$D/logs"

PGID=""; SAMPLER=""
stop() {
  [ -n "$SAMPLER" ] && kill "$SAMPLER" 2>/dev/null; SAMPLER=""
  if [ -n "$PGID" ]; then
    kill -TERM -- "-$PGID" 2>/dev/null
    for _ in $(seq 30); do kill -0 -- "-$PGID" 2>/dev/null || break; sleep 1; done
    kill -KILL -- "-$PGID" 2>/dev/null; PGID=""
  fi
  for _ in $(seq 90); do vram_idle 900 && break; sleep 1; done
}
trap stop EXIT

sample() {  # peak VRAM per card while the arm runs
  local label=$1; local -A peak=()
  while true; do
    local line="" i n v
    for i in "${!GPU_DEVS[@]}"; do
      n=$(gpu_name "$i"); v=$(gpu_mib "$i" vram_used)
      (( v > ${peak[$n]:-0} )) && peak[$n]=$v
      line+="$n ${peak[$n]} MiB  "
    done
    echo "$line" > "$D/logs/vram-$label.txt"; sleep 1
  done
}

bench() {  # bench <label> <url> <gguf>
  echo "=== $1 bench $(date +%T)"
  python3 "$B/engine-ab.py" --url "$2" --label "$1" --out "$OUT" --gguf "$3" \
    --docs "$D/docs" --gen-reps 3 --depths ${DEPTHS:-32000,120000} --depth-reps 2
  echo "=== $1 done $(date +%T)  peak: $(cat "$D/logs/vram-$1.txt")"
}

llama_arm() {  # llama_arm <label> <gguf> [extra flags]
  local label=$1 model=$2; shift 2
  vram_idle 900 || { echo "=== $label SKIPPED: GPUs not idle: $(vram_report)"; return; }
  setsid "$LLAMA" -m "$model" -ngl 99 -np 1 -c 131072 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 \
    -lm dio --jinja --host 127.0.0.1 --port 8099 "$@" > "$D/logs/$label.log" 2>&1 &
  PGID=$!
  for _ in $(seq 300); do
    kill -0 "$PGID" 2>/dev/null || break
    curl -s localhost:8099/health | grep -q ok && break; sleep 1
  done
  if ! curl -s localhost:8099/health | grep -q ok; then echo "=== $label FAILED to start (logs/$label.log)"; stop; return; fi
  sample "$label" & SAMPLER=$!
  bench "$label" http://127.0.0.1:8099 "$model"
  stop
}

strata_arm() {  # strata_arm <label> <config> <gguf>
  local label=$1 cfg=$2 model=$3
  vram_idle 900 || { echo "=== $label SKIPPED: GPUs not idle: $(vram_report)"; return; }
  ( cd "$STRATA" && exec setsid "$STRATA/.venv/bin/python" serve/server.py --engine strata --config "$cfg" \
      --port 8097 ) > "$D/logs/$label.log" 2>&1 &
  PGID=$!
  local ok="" swap0; swap0=$(free -m | awk '/Swap/{print $3}')
  for _ in $(seq 120); do
    kill -0 "$PGID" 2>/dev/null || break
    # 2026-11-15: Q6 at 128K paged 27 GB into swap and never finished loading. Abort on +6 GB.
    if (( $(free -m | awk '/Swap/{print $3}') - swap0 > 6144 )); then echo "=== $label ABORTED: swap grew past 6 GB while loading"; break; fi
    if curl -s --max-time 20 localhost:8097/v1/chat/completions -H 'Content-Type: application/json' \
         -d '{"messages":[{"role":"user","content":"Hi"}],"max_tokens":4,"chat_template_kwargs":{"enable_thinking":false}}' \
         | grep -q '"choices"'; then ok=1; break; fi
    sleep 5
  done
  if [ -z "$ok" ]; then echo "=== $label FAILED to start (logs/$label.log)"; stop; return; fi
  sample "$label" & SAMPLER=$!
  bench "$label" http://127.0.0.1:8097 "$model"
  stop
}

for arm in $ARMS; do
  case $arm in
    *q4*) until grep -q '=== UD-Q4_K_XL exit 0' "$DL" 2>/dev/null; do
            grep -q '=== UD-Q4_K_XL exit [1-9]' "$DL" 2>/dev/null && { echo "=== Q4 download failed"; break; }
            sleep 10; done ;;
  esac
  case $arm in
    llama-q6)     llama_arm llama-q6 "$Q6" ;;
    llama-q6-mtp) llama_arm llama-q6-mtp "$Q6" --spec-type draft-mtp ;;
    strata-q6-32k) DEPTHS=32000 strata_arm strata-q6-32k "$D/strata-q6-32k.json" "$Q6" ;;
    strata-q6)    strata_arm strata-q6 "$STRATA/strata-qwen36-ud-q6_k_xl.json" "$Q6" ;;
    llama-q4-mtp) [ -f "$Q4" ] && llama_arm llama-q4-mtp "$Q4" --spec-type draft-mtp ;;
    strata-q4)    [ -f "$STRATA/strata-qwen36-ud-q4_k_xl.json" ] && strata_arm strata-q4 "$STRATA/strata-qwen36-ud-q4_k_xl.json" "$Q4" ;;
  esac
done
echo "=== ALL DONE $(date +%T)"
