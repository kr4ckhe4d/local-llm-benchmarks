#!/usr/bin/env bash
# Inkling-2-Mini UD-Q8_K_XL: llama.cpp (router build db75ce3dc = upstream + inkling2-speedups, the
# inkling-2-mini-q8-128k preset's flags) against Strata 0.2.20 (engine 0.1.66, its own strata-inkling engine),
# the SAME GGUF, R9700 alone, 128K context. Strata with and without its DSpark drafter (llama.cpp's presets do
# not draft). Client: ../../engine-ab.py. Arms run one at a time; every server is started and killed here.
set -uo pipefail
B=/home/nipuna/code/local-llm-benchmarks/benchmarks
D=$B/raw/engine-ab-inkling
OUT=$D/results.jsonl
LLAMA=/home/nipuna/llama.cpp/build/bin/llama-server
ST=/home/nipuna/code/Strata/terminal
Q8=/mnt/fast/models/Inkling-2-Mini/Inkling-2-Mini-UD-Q8_K_XL.gguf
DOCS=$B/raw/engine-ab-qwen36/docs
# Inkling's thinking switch: effort 0, as the router preset sets it (Strata forces "none" = 0 whatever is sent)
EXTRA='{"chat_template_kwargs": {"reasoning_effort": 0}}'
ARMS=${ARMS:-llama-q8 strata-q8-nodraft strata-q8-dspark}
# SUFFIX=-rebased: the rows and logs of a re-run land under their own labels (results.jsonl is append-only and
# site/build.py takes the median over every row of a label, so a re-run under the same label would blend)
SUFFIX=${SUFFIX:-}
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

bench() {  # bench <label> <url>
  echo "=== $1 bench $(date +%T)"
  python3 "$B/engine-ab.py" --url "$2" --label "$1" --out "$OUT" --gguf "$Q8" --body-extra "$EXTRA" \
    --docs "$DOCS" --gen-reps 3 --depths 32000,120000 --depth-reps 2
  echo "=== $1 done $(date +%T)  peak: $(cat "$D/logs/vram-$1.txt")"
}

llama_arm() {  # llama_arm <label> [server binary] [ubatch]
  local label=$1$SUFFIX bin=${2:-$LLAMA} ub=${3:-128}
  vram_idle 900 || { echo "=== $label SKIPPED: GPUs not idle: $(vram_report)"; return; }
  setsid "$bin" -m "$Q8" --device ROCm1 -ngl 99 -np 1 -c 131072 -fa on -ub $ub -b 2048 --reasoning-budget 1024 \
    --jinja --host 127.0.0.1 --port 8099 > "$D/logs/$label.log" 2>&1 &
  PGID=$!
  for _ in $(seq 300); do
    kill -0 "$PGID" 2>/dev/null || break
    curl -s localhost:8099/health | grep -q ok && break; sleep 1
  done
  if ! curl -s localhost:8099/health | grep -q ok; then echo "=== $label FAILED to start (logs/$label.log)"; stop; return; fi
  sample "$label" & SAMPLER=$!
  bench "$label" http://127.0.0.1:8099
  stop
}

strata_arm() {  # strata_arm <label> <config>
  local label=$1$SUFFIX cfg=$2
  vram_idle 900 || { echo "=== $label SKIPPED: GPUs not idle: $(vram_report)"; return; }
  ( cd "$ST" && exec setsid "$ST/.venv/bin/python" serve/server.py --engine strata --config "$cfg" \
      --port 8097 ) > "$D/logs/$label.log" 2>&1 &
  PGID=$!
  local ok=""
  for _ in $(seq 120); do
    kill -0 "$PGID" 2>/dev/null || break
    if curl -s --max-time 600 localhost:8097/v1/chat/completions -H 'Content-Type: application/json' \
         -d '{"messages":[{"role":"user","content":"Hi"}],"max_tokens":4}' | grep -q '"choices"'; then ok=1; break; fi
    sleep 5
  done
  if [ -z "$ok" ]; then echo "=== $label FAILED to start (logs/$label.log)"; stop; return; fi
  sample "$label" & SAMPLER=$!
  bench "$label" http://127.0.0.1:8097
  stop
}

for arm in $ARMS; do
  case $arm in
    llama-q8)          llama_arm llama-q8 ;;
    # 2026-11-23: branch inkling2-strata-ideas (~/llama.cpp-inkling), which lets 128K take -ub 512
    llama-q8-branch)   llama_arm llama-q8-branch "$HOME/llama.cpp-inkling/build/bin/llama-server" 512 ;;
    strata-q8-nodraft) strata_arm strata-q8-nodraft "$ST/strata-inkling-2-mini-ud-q8_k_xl-nodraft.json" ;;
    strata-q8-dspark)  strata_arm strata-q8-dspark "$ST/strata-inkling-2-mini-ud-q8_k_xl.json" ;;
    # Strata's own format (SF4+MX8, 19.3 GB, DSpark drafter inside the file); output tokens still counted with the Q8 GGUF's tokenizer
    strata-sq20-nodraft) strata_arm strata-sq20-nodraft "$ST/strata-inkling-2-mini-sq-20-nodraft.json" ;;
    strata-sq20-dspark)  strata_arm strata-sq20-dspark "$ST/strata-inkling-2-mini-sq-20.json" ;;
  esac
done
echo "=== ALL DONE $(date +%T)"
