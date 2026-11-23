#!/usr/bin/env python3
"""Does Strata's no-thinking prefill make Inkling refuse more? Same Q8 GGUF on llama-server (:8099), the
engine-ab "prose" prompt, temperature 1.0 (the router preset's sampling), N samples per arm:
  think    - normal chat request at reasoning_effort 0: Inkling may think briefly first (llama.cpp's behaviour)
  prefill  - the same prompt rendered by the template, then <|message_model|><|content_text|> appended, as
             Strata's serve/inkling_dialect.py does for requests without tools: no thinking at all.
Rows go to refusal-probe.jsonl."""
import json, re, sys, urllib.request
URL = "http://127.0.0.1:8099"; N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
PROMPT = ("Write a 600-word short story about a lighthouse keeper who finds a radio that receives "
          "broadcasts from the next day.")
REFUSE = re.compile(r"\bI can[’']t\b|\bI cannot\b|\bI won[’']t\b|\bunable to\b", re.I)
KW = {"reasoning_effort": 0}

def post(path, body):
    r = urllib.request.Request(URL + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=600))

msgs = [{"role": "user", "content": PROMPT}]
raw = post("/apply-template", {"messages": msgs, "chat_template_kwargs": KW})["prompt"]
out = open("refusal-probe.jsonl", "a")
print("template's generation prompt ends:", repr(raw[-60:]))
for arm in ("think", "prefill"):
    refused = 0
    for i in range(N):
        if arm == "think":
            r = post("/v1/chat/completions", {"messages": msgs, "max_tokens": 400, "temperature": 1.0, "top_p": 1.0,
                                              "top_k": 0, "min_p": 0.0, "chat_template_kwargs": KW})
            m = r["choices"][0]["message"]; text = m.get("content") or ""; think = m.get("reasoning_content") or ""
        else:
            p = raw if raw.endswith("<|content_text|>") else raw + "<|message_model|><|content_text|>"
            r = post("/completion", {"prompt": p, "n_predict": 400, "temperature": 1.0, "top_p": 1.0, "top_k": 0,
                                     "min_p": 0.0})
            text = r["content"]; think = ""
        ref = bool(REFUSE.search(text[:200]))
        refused += ref
        row = {"arm": arm, "i": i, "refused": ref, "think_chars": len(think), "think_head": think[:120], "text_head": text[:160]}
        out.write(json.dumps(row) + "\n"); out.flush()
        print(arm, i, "REFUSED" if ref else "ok", f"think {len(think)} chars", repr(text[:70]), flush=True)
    print(f"=== {arm}: {refused}/{N} refused", flush=True)
