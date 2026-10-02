#!/usr/bin/env python3
"""Generation and prefill throughput against a running llama-server.

Replaces the inline curl loop run-suite.sh used until 2026-10-02. That loop
had five defects, all fixed here:

  1. Its "pp" column measured nothing. The prompt is ~50 tokens, and runs 2-3
     hit the prompt cache, so "pp 50.4 tok/s" was ONE re-processed token.
     Every request here sends cache_prompt=false and reports prompt_n.
  2. No warmup, so run 1 carried first-request costs (HIP graph capture,
     allocator growth). One discarded warmup run now precedes the timed ones.
  3. MTP draft acceptance was not recorded -- it was in `timings` all along
     (draft_n / draft_n_accepted) and copied into the README by hand.
  4. No mean/sd, and no check that every run generated the full 700 tokens.
     An early EOS would compare tok/s over different lengths.
  5. Shallow only. --depth N prefixes ~N tokens of code-shaped filler, which
     measures prefill at depth and generation against a deep KV cache.

The generation unit is unchanged -- same prompt, temperature 0.0, thinking
off, max_tokens 700 -- so `tg` stays comparable with every throughput number
already in the README.

    ./throughput-test.py --host http://127.0.0.1:8099 --runs 3 [--depth 16384]
"""
import argparse, json, statistics, sys, urllib.request

PROMPT = ("Write a complete Python implementation of a thread-safe LRU cache "
          "class with get, put, and delete methods, full docstrings, and type "
          "hints. Then write pytest unit tests for it. Output only code.")

# Same filler as needle-test.py, so depth means the same thing in both probes.
FILLER = """
def handler_{i}(request, context):
    \"\"\"Process inbound record batch {i} for the pipeline stage.\"\"\"
    payload = request.get("payload", {{}})
    if not payload:
        return {{"status": "empty", "stage": {i}}}
    records = payload.get("records", [])
    processed = []
    for record in records:
        if record.get("kind") == "metric":
            processed.append(normalize_metric(record, stage={i}))
        elif record.get("kind") == "event":
            processed.append(normalize_event(record, stage={i}))
    return {{"status": "ok", "count": len(processed), "stage": {i}}}
"""


def post(host, path, obj, timeout=1800):
    req = urllib.request.Request(
        host + path, data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def haystack(host, target):
    if target <= 0:
        return ""
    per = len(post(host, "/tokenize", {"content": FILLER.format(i=0)})["tokens"])
    body = "".join(FILLER.format(i=i) for i in range(max(1, target // per)))
    return ("Here is the module we are working in, for context:\n\n```python"
            + body + "```\n\n")


def one(host, content, max_tokens):
    r = post(host, "/v1/chat/completions", {
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens, "temperature": 0.0, "cache_prompt": False,
        "chat_template_kwargs": {"enable_thinking": False}})
    return r["timings"]


def fmt(xs):
    if len(xs) < 2:
        return f"{xs[0]:8.2f}"
    return f"{statistics.mean(xs):8.2f} +/- {statistics.stdev(xs):.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8099")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--depth", type=int, default=0,
                    help="approximate tokens of filler before the prompt")
    ap.add_argument("--max-tokens", type=int, default=700)
    ap.add_argument("--json", help="append per-run timings as JSON lines here")
    a = ap.parse_args()

    content = haystack(a.host, a.depth) + PROMPT
    one(a.host, content, 32)  # warmup, discarded

    pp, tg, acc, short = [], [], [], 0
    for i in range(1, a.runs + 1):
        t = one(a.host, content, a.max_tokens)
        pp.append(t["prompt_per_second"])
        tg.append(t["predicted_per_second"])
        line = (f"run{i}  prompt {t['prompt_n']:6d} tok @ {t['prompt_per_second']:8.1f} tok/s"
                f" | tg {t['predicted_per_second']:6.2f} tok/s, {t['predicted_n']:4d} tok")
        if t.get("draft_n"):
            acc.append(t["draft_n_accepted"] / t["draft_n"])
            line += f" | draft {t['draft_n_accepted']}/{t['draft_n']} = {acc[-1]:.1%}"
        if t["predicted_n"] < a.max_tokens:
            short += 1
            line += "  << SHORT: early EOS, tg not comparable"
        print(line, flush=True)
        if a.json:
            with open(a.json, "a") as f:
                f.write(json.dumps({"run": i, "depth": a.depth, **t}) + "\n")

    print(f"\nprompt  {fmt(pp)} tok/s   ({t['prompt_n']} tok, cache off)")
    print(f"tg      {fmt(tg)} tok/s   (n={len(tg)}, {a.max_tokens} tok)")
    if acc:
        print(f"draft   {statistics.mean(acc):8.1%} accepted")
    return 1 if short else 0


if __name__ == "__main__":
    sys.exit(main())
