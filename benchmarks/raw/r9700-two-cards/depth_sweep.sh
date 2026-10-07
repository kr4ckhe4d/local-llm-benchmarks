#!/usr/bin/env bash
# Prefill and generation across prompt depths, one server per config.
# Added 2026-10-07 to locate GLM-4.7-Flash's collapse at 128K (154.5 tok/s
# prefill against ~3,000 for the other MoE presets, logs/depth-presets.txt).
# Same prompt as depth_presets.sh (wikitext, cut to N tokens, 256 out, temp 0,
# no prompt cache), but several depths per server so the curve shows where
# it bends.
#
#   LOGDIR=logs ./depth_sweep.sh <label> <model.gguf> "<depths>" <flags...>
#   e.g. ./depth_sweep.sh glm-q8-fa-q8kv GLM-4.7-Flash-Q8_0.gguf "8000 32000 64000" -fa on -ctk q8_0 -ctv q8_0
#
# The router must be down.
set -uo pipefail
B=/home/nipuna/code/local-llm-benchmarks/benchmarks
BIN=${BIN:-/home/nipuna/llama.cpp/build/bin/llama-server}
M=/home/nipuna/llama.cpp/models
CORPUS=/home/nipuna/llama.cpp/kld/wikitext-2-raw/wiki.test.raw
LOGDIR=${LOGDIR:-/tmp}
CTX=${CTX:-131072}
. "$B/gpu-mem.sh"

label=$1 model=$2 depths=$3; shift 3
for _ in $(seq 30); do pgrep -x llama-server >/dev/null || break; sleep 1; done
pgrep -x llama-server >/dev/null && { echo "$label  SKIPPED: a llama-server is still running"; exit 2; }
for _ in $(seq 90); do vram_idle 900 && break; sleep 1; done

# Launched directly, so $! is llama-server (see depth_presets.sh for why it matters).
"$BIN" -m "$M/$model" -ngl 99 -np 1 -c "$CTX" --load-mode dio "$@" \
  --host 127.0.0.1 --port 8099 > "$LOGDIR/sweep-$label.log" 2>&1 &
pid=$!
for _ in $(seq 300); do
  kill -0 $pid 2>/dev/null || break
  curl -s localhost:8099/health 2>/dev/null | grep -q ok && break; sleep 1
done
if ! kill -0 $pid 2>/dev/null || ! curl -s localhost:8099/props | grep -qF "\"model_path\":\"$M/$model\""; then
  echo "$label  FAILED to start, see $LOGDIR/sweep-$label.log"; kill $pid 2>/dev/null; exit 1
fi
( p=(); while kill -0 $pid 2>/dev/null; do
    for i in "${!GPU_DEVS[@]}"; do v=$(gpu_mib "$i" vram_used); [ "$v" -gt "${p[i]:-0}" ] && p[i]=$v; done
    echo "${p[*]}" > "$LOGDIR/sweep-$label.vram"; sleep 1
  done ) &
poll=$!

echo "######## $label  ($model, ctx $CTX, $*)"
python3 - "$label" "$CORPUS" $depths <<'PY'
import json, sys, time, urllib.request
label, corpus, depths = sys.argv[1], sys.argv[2], [int(d) for d in sys.argv[3:]]
def post(path, body, timeout=3600):
    req = urllib.request.Request("http://127.0.0.1:8099" + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))
text = open(corpus, encoding="utf-8").read()[:900_000]
all_toks = post("/tokenize", {"content": text})["tokens"]
q = "\n\nIn three sentences, summarise what the text above is about."
for d in depths:
    doc = post("/detokenize", {"tokens": all_toks[:d]})["content"]
    t0 = time.time()
    try:
        r = post("/v1/chat/completions", {
            "messages": [{"role": "user", "content": doc + q}], "max_tokens": 256, "temperature": 0.0,
            "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}, timeout=2400)
    except Exception as e:
        print(f"  depth {d:6d}  FAILED after {time.time()-t0:.0f}s: {e}", flush=True); break
    t = r["timings"]
    print(f"  depth {t['prompt_n']:6d} tok | prefill {t['prompt_per_second']:7.1f} tok/s "
          f"({t['prompt_ms']/1000:6.1f} s) | tg {t['predicted_per_second']:6.2f} tok/s", flush=True)
PY
kill $pid; wait $pid 2>/dev/null; kill $poll 2>/dev/null; wait $poll 2>/dev/null
line="  VRAM peak per card:"; read -r -a pk < "$LOGDIR/sweep-$label.vram"
for i in "${!GPU_DEVS[@]}"; do line+="  $(gpu_name "$i") ${pk[i]}/$(gpu_mib "$i" vram_total)"; done
echo "$line MiB"; rm -f "$LOGDIR/sweep-$label.vram"
