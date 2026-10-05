#!/usr/bin/env bash
# Gemma 4 Q8_0 follow-ups, 2026-10-05, router down:
#   1. Q8 vision fit at 32K/128K/256K (mmproj + MTP drafter, no offload), then
#      the probe image end to end at 128K with per-card VRAM after the image turn
#   2. KLD of UD-Q4_K_M against Q8_0 as the reference (Q8 base, then Q4 score)
D=/home/nipuna/code/local-llm-benchmarks/benchmarks
M=/home/nipuna/llama.cpp/models
BIN=/home/nipuna/llama.cpp/build/bin/llama-server
. "$D/gpu-mem.sh"
Q8=gemma-4-26B-A4B-it-Q8_0.gguf
V=(--mmproj "$M/mmproj-F16.gguf" --model-draft "$M/mtp-gemma-4-26B-A4B-it.gguf" --spec-type draft-mtp
   --reasoning-budget 1024 --repeat-penalty 1.05 --load-mode dio)

echo "=== $(date -Is) 1. Q8 vision fit"
for ctx in 32768 131072 262144; do
  echo "######## q8 vision ctx $ctx"
  MODEL=$Q8 "$D/fit.sh" "$ctx" "${V[@]}" 2>&1 | sed -E 's/flags:.*//; s/^/  /'
done

echo "=== $(date -Is) 1b. Q8 vision 128K, probe image end to end"
for _ in $(seq 90); do vram_idle 900 && break; sleep 1; done
"$BIN" -m "$M/$Q8" -ngl 99 -np 1 -c 131072 "${V[@]}" --host 127.0.0.1 --port 8099 \
  > "$D/raw/r9700-two-cards/logs/gemma-q8-vision-128k.log" 2>&1 &
pid=$!
for _ in $(seq 300); do curl -s localhost:8099/health 2>/dev/null | grep -q ok && break; sleep 1; done
python3 - "$D/vision-probe.png" <<'PY'
import base64, json, sys, urllib.request
img = base64.b64encode(open(sys.argv[1], "rb").read()).decode()
q = ("Read the text in the image exactly. Then name each shape and its colour, say how many "
     "shapes there are, and solve the arithmetic shown.")
body = {"messages": [{"role": "user", "content": [
          {"type": "image_url", "image_url": {"url": "data:image/png;base64," + img}},
          {"type": "text", "text": q}]}],
        "max_tokens": 400, "temperature": 0.0, "chat_template_kwargs": {"enable_thinking": False}}
req = urllib.request.Request("http://127.0.0.1:8099/v1/chat/completions", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
r = json.load(urllib.request.urlopen(req, timeout=600))
c = r["choices"][0]["message"]["content"]; t = r["timings"]
low = c.lower()
checks = {"PROBE-770487": "PROBE-770487" in c, "red circle": "red circle" in low,
          "blue square": "blue square" in low, "green triangle": "green triangle" in low,
          "three": "three" in low or " 3 " in c, "42": "42" in c}
dn, da = t.get("draft_n", 0), t.get("draft_n_accepted", 0)
print("  answer:", c.replace("\n", " ")[:600])
print(f"  checks: {sum(checks.values())}/{len(checks)} {checks}")
print(f"  prompt {t['prompt_n']} tok | tg {t['predicted_per_second']:.2f} tok/s"
      + (f" | draft {100*da/dn:.1f}%" if dn else ""))
PY
echo "  after image turn: $(vram_report), GTT $(gtt_used) MiB"
kill $pid; wait $pid 2>/dev/null

echo "=== $(date -Is) 2. KLD base: Q8_0, 200 chunks"
export BASE_FILE=/home/nipuna/llama.cpp/kld/gemma-4-26B-A4B-q8_0.kld
"$D/kld-test.sh" base "$Q8" 200 "-ngl 99"
echo "=== $(date -Is) 2b. KLD score: UD-Q4_K_M vs Q8_0"
"$D/kld-test.sh" score q8ref/gemma-4-26B-A4B-UD-Q4_K_M gemma-4-26B-A4B-it-UD-Q4_K_M.gguf 200 "-ngl 99"
echo "=== $(date -Is) done"
