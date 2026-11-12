#!/usr/bin/env bash
# Trial of the -tensor presets (models-preset.ini, 2026-11-12) against today's preset, on the
# checks the seed runs did not cover: a long agent-shaped session (long-session-test.py) and two
# parallel slots.
#
#   layer        stock, UD-Q6_K, layer split            = qwen3.8-27B-q6-128k-nothink
#   q6-tensor    stock, UD-Q6_K, -sm tensor             = qwen3.8-27B-q6-128k-tensor-nothink
#   fork-tensor  RDNA fork r265, UD-Q4_K_XL v3.1, -sm tensor
#                                                       = qwen3.8-27B-q4xl-128k-tensor-nothink on ROUTER_BIN
#
#   ./tensor-trial.sh                    # writes tensor-trial/<name>.{txt,json}; done ones are skipped
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT=$HERE/tensor-trial; mkdir -p "$OUT"
MODELS=$HOME/llama.cpp/models
PORT=8099
BASE="-ngl 99 -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --temp 1.0 --top-p 0.95 --top-k 20
  --min-p 0.0 --reasoning-budget 0 --load-mode dio --ctx-checkpoints 4"
TENSOR="-sm tensor --device ROCm0,ROCm1"

serve() {  # <bin> <model> <ctx> <extra flags...>; sets PID
  local bin=$1 model=$2 ctx=$3; shift 3
  # shellcheck disable=SC2086
  "$bin" -m "$MODELS/$model" -c "$ctx" $BASE "$@" --chat-template-file "$HERE/../templates/qwen38-late-system.jinja" \
    --host 127.0.0.1 --port $PORT > "$OUT/server.log" 2>&1 &
  PID=$!
  until curl -sf http://127.0.0.1:$PORT/health > /dev/null; do
    kill -0 $PID 2>/dev/null || { echo "server failed to start: $OUT/server.log"; return 1; }
    sleep 1
  done
}
stop() { kill $PID 2>/dev/null; wait $PID 2>/dev/null; sleep 4; }

session() {  # <name> <bin> <model> <extra flags...>
  local name=$1 bin=$2 model=$3; shift 3
  [ -s "$OUT/$name.json" ] && return
  serve "$bin" "$model" 131072 "$@" || return
  "$HERE/long-session-test.py" --host http://127.0.0.1:$PORT --pid $PID --depth 122000 \
    --json "$OUT/$name.json" 2>&1 | tee "$OUT/$name.txt"
  cp "$OUT/server.log" "$OUT/$name.server.log"; stop
}

parallel() {  # <name> <bin> <model> <extra flags...>: two slots of 64K, two requests at once
  local name=$1 bin=$2 model=$3; shift 3
  [ -s "$OUT/$name.txt" ] && return
  serve "$bin" "$model" 131072 -np 2 "$@" || return
  python3 - "$PORT" > "$OUT/$name.txt" 2>&1 <<'EOF'
import json, sys, threading, urllib.request
host = f"http://127.0.0.1:{sys.argv[1]}"
P = ["Write a Python class for an LRU cache with get and put, with tests.",
     "Write a C function that parses an IPv4 address string into a uint32_t, with error handling."]
def go(i, out):
    req = urllib.request.Request(host + "/v1/chat/completions", headers={"Content-Type": "application/json"},
        data=json.dumps({"messages": [{"role": "user", "content": P[i]}], "max_tokens": 500, "temperature": 0}).encode())
    out[i] = json.loads(urllib.request.urlopen(req, timeout=900).read())
for label, idx in (("one request", [0]), ("two at once", [0, 1])):
    out = {}
    th = [threading.Thread(target=go, args=(i, out)) for i in idx]
    [t.start() for t in th]; [t.join() for t in th]
    for i in idx:
        t = out[i]["timings"]; text = out[i]["choices"][0]["message"]["content"]
        print(f"{label}: prompt {i}: {t['predicted_n']} tokens, {t['predicted_per_second']:.1f} tok/s, "
              f"draft {t.get('draft_n_accepted')}/{t.get('draft_n')}, text {'ok' if ('def ' in text or 'uint32_t' in text) else 'SUSPECT'}")
    if len(idx) == 2:
        print(f"two at once, total: {sum(out[i]['timings']['predicted_per_second'] for i in idx):.1f} tok/s")
EOF
  cat "$OUT/$name.txt"; stop
}

STOCK=$HOME/llama.cpp/build/bin/llama-server
FORK=$HOME/llama.cpp-rdna-fork/build/bin/llama-server
Q6=Qwen3.8-27B-UD-Q6_K.gguf
Q4=Qwen3.8-27B-UD-Q4_K_XL-v31.gguf
# shellcheck disable=SC2086
{
session  session-layer        "$STOCK" $Q6
session  session-q6-tensor    "$STOCK" $Q6 $TENSOR
session  session-fork-tensor  "$FORK"  $Q4 $TENSOR
parallel parallel-layer       "$STOCK" $Q6
parallel parallel-q6-tensor   "$STOCK" $Q6 $TENSOR
parallel parallel-fork-tensor "$FORK"  $Q4 $TENSOR
}
