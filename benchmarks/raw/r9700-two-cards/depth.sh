#!/usr/bin/env bash
# Qwen3.8-27B at real 128K depth on two cards: prefill and generation with one
# ~128,000-token prompt, as llama-a868c3e3c.md did for the single-card preset.
# -ub 512 vs 1024 on the new preset, and the old preset as the before.
# Run 2026-10-05.
set -uo pipefail
B=/home/nipuna/code/local-llm-benchmarks/benchmarks
BIN=/home/nipuna/llama.cpp/build/bin/llama-server
M=/home/nipuna/llama.cpp/models
CORPUS=/home/nipuna/llama.cpp/kld/wikitext-2-raw/wiki.test.raw
TARGET=${TARGET:-128000}
. "$B/gpu-mem.sh"
Q="--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"

depth() {  # depth <label> <model> <flags...>
  local label=$1 model=$2; shift 2
  for _ in $(seq 90); do vram_idle 900 && break; sleep 1; done
  "$BIN" -m "$M/$model" -ngl 99 -np 1 -c 131072 --load-mode dio "$@" $Q \
    --host 127.0.0.1 --port 8099 > "/tmp/depth-$label.log" 2>&1 &
  local pid=$!
  for _ in $(seq 300); do curl -s localhost:8099/health 2>/dev/null | grep -q ok && break; sleep 1; done
  ( while kill -0 $pid 2>/dev/null; do vram_used >> "/tmp/depth-$label.vram"; sleep 1; done ) &
  local poll=$!
  python3 - "$label" "$TARGET" "$CORPUS" <<'PY'
import json, sys, urllib.request
label, target, corpus = sys.argv[1], int(sys.argv[2]), sys.argv[3]
def post(path, body):
    req = urllib.request.Request("http://127.0.0.1:8099" + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=3600))
text = open(corpus, encoding="utf-8").read()[:900_000]
toks = post("/tokenize", {"content": text})["tokens"][:target]
doc = post("/detokenize", {"tokens": toks})["content"]
q = "\n\nIn three sentences, summarise what the text above is about."
r = post("/v1/chat/completions", {
    "messages": [{"role": "user", "content": doc + q}], "max_tokens": 256, "temperature": 0.0,
    "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}})
t = r["timings"]; dn = t.get("draft_n", 0); da = t.get("draft_n_accepted", 0)
acc = f" | draft {100*da/dn:.1f}%" if dn else ""
print(f"{label:28} prompt {t['prompt_n']:6d} tok @ {t['prompt_per_second']:7.1f} tok/s | "
      f"tg {t['predicted_per_second']:6.2f} tok/s ({t['predicted_n']} tok){acc}")
PY
  kill $pid; wait $pid 2>/dev/null; kill $poll 2>/dev/null
  echo "    VRAM peak $(sort -n "/tmp/depth-$label.vram" | tail -1) MiB summed"
  rm -f "/tmp/depth-$label.vram"
}

depth new-ub512   Qwen3.8-27B-UD-IQ4_XS-v3.gguf  -ub 512  -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp
depth new-ub1024  Qwen3.8-27B-UD-IQ4_XS-v3.gguf  -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp
depth old-preset  Qwen3.8-27B-UD-Q3_K_XL-v3.gguf -ub 512  -b 2048 -fa on -ctk q4_0 -ctv q4_0
