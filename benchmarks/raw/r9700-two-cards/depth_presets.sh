#!/usr/bin/env bash
# Prefill and generation at real 128K depth, for presets exactly as written.
# Same method as depth.sh (one ~128,000-token wikitext prompt, 256 tokens out,
# temperature 0, no prompt cache), but each preset's flags come from
# models-preset.ini through preset_probe.py, so what is measured is what the
# router serves. Added 2026-10-07: until then only Qwen3.8 IQ4_XS had a
# two-card prefill or real-depth figure; every MoE row was the 700-token probe
# in an empty context.
#
#   LOGDIR=logs ./depth_presets.sh <preset> [preset ...]
#
# The router must be down (fit.sh's rule; a resident model skews VRAM and
# competes for the cards).
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
B=/home/nipuna/code/local-llm-benchmarks/benchmarks
BIN=${BIN:-/home/nipuna/llama.cpp/build/bin/llama-server}
CORPUS=/home/nipuna/llama.cpp/kld/wikitext-2-raw/wiki.test.raw
TARGET=${TARGET:-128000}
LOGDIR=${LOGDIR:-/tmp}
. "$B/gpu-mem.sh"

pgrep -x llama-server >/dev/null && { echo "ABORT another llama-server is running" >&2; exit 2; }

preset() {  # preset <name> <field>: model, ctx, or flags (shell-quoted)
  ( cd "$HERE" && python3 - "$1" "$2" <<'PY'
import shlex, sys
name, field = sys.argv[1], sys.argv[2]
sys.argv = [sys.argv[0], "/dev/null"]          # moe_sweep reads OUT at import
import preset_probe as pp
allp = pp.sections(); glob = allp.pop("*", {"kv": []}); p = allp[name]
print({"model": p.get("model", ""), "ctx": p.get("ctx-size", "")}.get(field)
      or " ".join(shlex.quote(x) for x in pp.flags(p, glob)))
PY
  )
}

depth() {  # depth <preset>
  local name=$1 model ctx flags
  model=$(preset "$name" model); ctx=$(preset "$name" ctx); flags=$(preset "$name" flags)
  for _ in $(seq 30); do pgrep -x llama-server >/dev/null || break; sleep 1; done
  if pgrep -x llama-server >/dev/null; then echo "$name  SKIPPED: a llama-server is still running"; return; fi
  for _ in $(seq 90); do vram_idle 900 && break; sleep 1; done
  # exec, so $! is llama-server itself. The first version ran 'eval ... &'
  # without it: $! was the wrapper subshell, kill missed the server, and every
  # later preset failed to bind :8099 while its requests reached the first
  # server (logs/depth-presets-INVALID.txt).
  eval "exec \"$BIN\" -m \"$model\" -ngl 99 -np 1 -c $ctx $flags --host 127.0.0.1 --port 8099" \
    > "$LOGDIR/depthp-$name.log" 2>&1 &
  local pid=$!
  for _ in $(seq 300); do
    kill -0 $pid 2>/dev/null || break
    curl -s localhost:8099/health 2>/dev/null | grep -q ok && break; sleep 1
  done
  # The server answering must be this one, serving this model.
  if ! kill -0 $pid 2>/dev/null \
     || ! curl -s localhost:8099/props | grep -qF "\"model_path\":\"$model\""; then
    echo "$name  FAILED to start, see $LOGDIR/depthp-$name.log"
    kill $pid 2>/dev/null; wait $pid 2>/dev/null; return
  fi
  ( p=(); while kill -0 $pid 2>/dev/null; do
      for i in "${!GPU_DEVS[@]}"; do v=$(gpu_mib "$i" vram_used); [ "$v" -gt "${p[i]:-0}" ] && p[i]=$v; done
      echo "${p[*]}" > "$LOGDIR/depthp-$name.vram"; sleep 1
    done ) &
  local poll=$!
  python3 - "$name" "$TARGET" "$CORPUS" <<'PY'
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
print(f"{label:34} prompt {t['prompt_n']:6d} tok @ {t['prompt_per_second']:7.1f} tok/s | "
      f"tg {t['predicted_per_second']:6.2f} tok/s ({t['predicted_n']} tok){acc}", flush=True)
PY
  [ "${PIPESTATUS[0]}" -eq 0 ] || echo "$name  FAILED, see $LOGDIR/depthp-$name.log"
  kill $pid; wait $pid 2>/dev/null; kill $poll 2>/dev/null; wait $poll 2>/dev/null
  local line="    VRAM peak per card:"; read -r -a pk < "$LOGDIR/depthp-$name.vram"
  for i in "${!GPU_DEVS[@]}"; do
    line+="  $(gpu_name "$i") ${pk[i]}/$(gpu_mib "$i" vram_total)"
  done
  echo "$line MiB"; rm -f "$LOGDIR/depthp-$name.vram"
}

for n in "$@"; do depth "$n"; done
