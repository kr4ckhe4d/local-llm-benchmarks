#!/usr/bin/env bash
# Unsloth Dynamic v3.1 re-quants of Qwen3.8-27B (uploaded 2026-11-11, same file names as before)
# against the UD-Q6_K pulled 2026-10-06 that the daily presets run.
#
# Per file, on the daily preset (both cards, 128K, q8_0 KV, MTP, stock build):
#   1. KLD against the Q8_0 logits (kld-test.sh score, 200 chunks)  -> q8ref/<label>/kld.txt
#   2. the probe suite (run-suite.sh)                                -> <label>/
#   3. code quality over seeds 1..N at the preset sampler, thinking off, plus the
#      throughput probe on the same server                           -> <label>/seeds/
#
# The v3.1 files are saved as *-v31.gguf so the daily file is not replaced:
#   R=https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/main
#   curl -L -C - -o Qwen3.8-27B-UD-Q6_K-v31.gguf $R/Qwen3.8-27B-UD-Q6_K.gguf   (etc.)
# sha256 of the 2026-11-11 upload ("New UD3.1 quants"):
#   UD-Q6_K    6cac55f876015d6d4b94b1656d23f79f424ac9b583652aedf0633dba116576a8
#   UD-Q5_K_M  e2771d4c10c6b77141552ea7a21631067271f17baf918f46a3cba78495f92e1e
#   UD-Q4_K_XL 2a5f3565f39cf885103da591182c1266da64745737b42b452fd3e675369f1211
#   UD-IQ4_XS  4b194b34ecec99fdfb74caef84445ccd01c987de87d96ae8ca50dc434b4b0a38
#
#   ./ud31-test.sh                 # everything that is on disk and not yet done
#   STEPS="kld" ./ud31-test.sh     # only some steps (kld suite seeds)
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
MODELS=$HOME/llama.cpp/models
BIN=$HOME/llama.cpp/build/bin/llama-server
PORT=8099
SEEDS=${SEEDS:-12}
STEPS=${STEPS:-kld suite seeds}
FLAGS="-ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp"
CTX=131072

declare -A SHA=(
  [UD-Q6_K-v31]=6cac55f876015d6d4b94b1656d23f79f424ac9b583652aedf0633dba116576a8
  [UD-Q5_K_M-v31]=e2771d4c10c6b77141552ea7a21631067271f17baf918f46a3cba78495f92e1e
  [UD-Q4_K_XL-v31]=2a5f3565f39cf885103da591182c1266da64745737b42b452fd3e675369f1211
  [UD-IQ4_XS-v31]=4b194b34ecec99fdfb74caef84445ccd01c987de87d96ae8ca50dc434b4b0a38
)
# label suffix -> file; the first is the reference file the presets use today
ORDER=(UD-Q6_K-pulled-10-06 UD-Q6_K-v31 UD-Q5_K_M-v31 UD-Q4_K_XL-v31 UD-IQ4_XS-v31)
file_of() { case $1 in UD-Q6_K-pulled-10-06) echo Qwen3.8-27B-UD-Q6_K.gguf;; *) echo Qwen3.8-27B-$1.gguf;; esac; }

seeds() {  # <label> <model>
  local out=$HERE/$1/seeds; mkdir -p "$out"
  local todo=0; for s in $(seq $SEEDS); do [ -s "$out/s$s.txt" ] || todo=1; done
  [ -s "$out/throughput.txt" ] || todo=1
  [ $todo = 0 ] && return
  # shellcheck disable=SC2086
  "$BIN" -m "$MODELS/$2" -ngl 99 -c $CTX $FLAGS \
    --chat-template-file "$HERE/../templates/qwen38-late-system.jinja" \
    --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 0 --load-mode dio \
    --ctx-checkpoints 4 --host 127.0.0.1 --port $PORT > "$out/server.log" 2>&1 &
  local pid=$!
  until curl -sf http://127.0.0.1:$PORT/health > /dev/null; do
    kill -0 $pid 2>/dev/null || { echo "$1: server failed to start"; return 1; }
    sleep 1
  done
  [ -s "$out/throughput.txt" ] || "$HERE/throughput-test.py" --host http://127.0.0.1:$PORT --runs 3 > "$out/throughput.txt" 2>&1
  for s in $(seq $SEEDS); do
    [ -s "$out/s$s.txt" ] && continue
    "$HERE/code-quality-test.py" --host http://127.0.0.1:$PORT --label "$1-s$s" --temperature 1.0 \
      --top-p 0.95 --extra "{\"top_k\": 20, \"min_p\": 0.0, \"seed\": $s}" > "$out/s$s.txt" 2>&1
  done
  kill $pid; wait $pid 2>/dev/null; sleep 3
}

for q in "${ORDER[@]}"; do
  f=$(file_of "$q"); label=qwen3.8-27B-$q
  [ -f "$MODELS/$f" ] || { echo "skip $q: $f not on disk"; continue; }
  if [ -n "${SHA[$q]:-}" ] && [ ! -f "$HERE/$label/sha256.txt" ]; then
    got=$(sha256sum "$MODELS/$f" | cut -d' ' -f1)
    [ "$got" = "${SHA[$q]}" ] || { echo "skip $q: sha256 $got does not match the 2026-11-11 upload"; continue; }
    mkdir -p "$HERE/$label"; echo "$got" > "$HERE/$label/sha256.txt"
  fi
  echo "=== $q"
  case " $STEPS " in *" kld "*)
    [ -s "q8ref/$label/kld.txt" ] && grep -q "Same top p" "q8ref/$label/kld.txt" || \
      BASE_FILE=$HOME/llama.cpp/kld/qwen3.8-27B-q8_0.kld ./kld-test.sh score "q8ref/$label" "$f" 200 "-ngl 99" ;;
  esac
  [ "$q" = UD-IQ4_XS-v31 ] && continue   # KLD only: it has a v3 number to compare with, and is not a preset candidate
  case " $STEPS " in *" suite "*)
    [ -s "$label/cdn-freshness.txt" ] || ./run-suite.sh "$label" "$f" $CTX "$FLAGS" ;;
  esac
  case " $STEPS " in *" seeds "*) seeds "$label" "$f" ;; esac
done
echo "=== summary"
grep -H -E "Mean    KLD|Same top p" q8ref/qwen3.8-27B-UD-*/kld.txt | sed 's|q8ref/qwen3.8-27B-||'
for d in qwen3.8-27B-UD-*/seeds; do echo "$d: $(grep -h 'checks pass' "$d"/s*.txt 2>/dev/null | tr '\n' ' ')"; done
