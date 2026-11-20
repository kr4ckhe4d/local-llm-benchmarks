#!/usr/bin/env python3
"""Engine A/B through the OpenAI chat API: llama-server against Strata (or any
other server), timed on the client so both engines are measured the same way.

  python3 engine-ab.py --url http://127.0.0.1:8099 --label NAME --out results.jsonl \
      [--key KEY] [--docs DIR] [--gen-reps 3] [--depths 32000,120000] [--depth-reps 2]

Per request: time to first streamed token (prefill), then decode rate over the
rest = (output tokens - 1) / (t_last - t_first). Output tokens are counted with
llama-tokenize on the same GGUF for every engine (--gguf), not from the
server's usage block, so MTP chunking or a missing usage field cannot skew it.
Greedy (temperature 0), thinking off. Depth prompts are wikitext cut to N
tokens; a nonce in the first line defeats every prefix cache.
"""
import argparse, json, os, subprocess, sys, time, urllib.request, uuid

GEN_PROMPTS = {
    "code": "Write a Python module implementing an LRU cache class with get, put, delete and resize, "
            "type hints and docstrings, followed by a pytest test suite covering eviction order, resize "
            "smaller and larger, and deleting missing keys.",
    "prose": "Write a 600-word short story about a lighthouse keeper who finds a radio that receives "
             "broadcasts from the next day.",
    "explain": "Explain in detail how TCP congestion control works: slow start, congestion avoidance, "
               "fast retransmit and fast recovery, CUBIC and BBR, with a worked numeric example.",
}
QUESTION = "\n\nIn three sentences, summarise what the text above is about."


def ntok(text, gguf):
    if not text:
        return 0
    r = subprocess.run([os.path.expanduser("~/llama.cpp/build/bin/llama-tokenize"), "-m", gguf,
                        "--stdin", "--ids", "--log-disable", "--no-bos"],
                       input=text, capture_output=True, text=True)
    line = [l for l in r.stdout.splitlines() if l.startswith("[")][-1]
    return len(json.loads(line))


def stream(url, key, messages, max_tokens):
    body = {"model": "x", "messages": messages, "max_tokens": max_tokens, "temperature": 0.0,
            # penalties sent as off: Strata fills what a request leaves out from the model card (Qwen3.6:
            # presence_penalty 1.5), and any penalty turns its MTP drafts off. llama-server's default is off.
            "presence_penalty": 0.0, "frequency_penalty": 0.0, "repetition_penalty": 1.0,
            "stream": True, "stream_options": {"include_usage": True}, "cache_prompt": False,
            "chat_template_kwargs": {"enable_thinking": False}}
    h = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url + "/v1/chat/completions", data=json.dumps(body).encode(), headers=h)
    t0 = time.perf_counter(); t_first = t_last = None; text = ""; reasoning = ""; usage = None
    with urllib.request.urlopen(req, timeout=7200) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            ev = json.loads(data)
            if ev.get("usage"):
                usage = ev["usage"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                piece = (d.get("content") or "") + (d.get("reasoning_content") or "")
                if piece:
                    now = time.perf_counter()
                    t_first = t_first or now
                    t_last = now
                    text += d.get("content") or ""
                    reasoning += d.get("reasoning_content") or ""
    return t0, t_first, t_last, text, reasoning, usage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True); ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--key", default="")
    ap.add_argument("--gguf", required=True); ap.add_argument("--docs", default="")
    ap.add_argument("--gen-reps", type=int, default=3); ap.add_argument("--gen-max", type=int, default=1024)
    ap.add_argument("--depths", default=""); ap.add_argument("--depth-reps", type=int, default=2)
    a = ap.parse_args()
    out = open(a.out, "a")

    def record(kind, name, rep, prompt_tokens, res):
        t0, tf, tl, text, reasoning, usage = res
        n = ntok(text + reasoning, a.gguf)
        row = {"label": a.label, "kind": kind, "name": name, "rep": rep, "prompt_tokens": prompt_tokens,
               "ttft_s": round(tf - t0, 3) if tf else None, "out_tokens": n,
               "decode_tps": round((n - 1) / (tl - tf), 2) if tf and tl and tl > tf and n > 1 else None,
               "server_usage": usage, "text_head": text[:160]}
        if prompt_tokens and tf:
            row["prefill_tps"] = round(prompt_tokens / (tf - t0), 1)
        out.write(json.dumps(row) + "\n"); out.flush()
        print(json.dumps({k: row[k] for k in row if k not in ("text_head", "server_usage")}), flush=True)

    # warm-up: first request pays graph capture / first-touch costs on both engines
    stream(a.url, a.key, [{"role": "user", "content": "Say hello."}], 32)
    for rep in range(a.gen_reps):
        for name, p in GEN_PROMPTS.items():
            record("gen", name, rep, None, stream(a.url, a.key, [{"role": "user", "content": p}], a.gen_max))
    for d in [int(x) for x in a.depths.split(",") if x]:
        doc = open(os.path.join(a.docs, f"wiki-{d}.txt"), encoding="utf-8").read()
        for rep in range(a.depth_reps):
            msg = f"Document {uuid.uuid4().hex}.\n\n" + doc + QUESTION
            pt = ntok(msg, a.gguf)
            record("depth", str(d), rep, pt, stream(a.url, a.key, [{"role": "user", "content": msg}], 256))


if __name__ == "__main__":
    main()
