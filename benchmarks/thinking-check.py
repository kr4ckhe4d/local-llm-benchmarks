#!/usr/bin/env python3
"""Per-request thinking check for the router after a llama.cpp update (the local thinking patch,
patches/llama-per-request-thinking.patch). The router runs in nothink mode; each client switches thinking per request.

  python3 thinking-check.py [--url http://127.0.0.1:8090] [--model qwen3.8-27B-q6-32k]

Seven requests: OpenAI with no reasoning_effort / none / minimal / high, Anthropic with no thinking / enabled /
adaptive. The off rows (no field, none, Anthropic without thinking) must return no thinking, the others some.
Exit code 1 on any mismatch.
"""
import argparse, json, sys, urllib.request

PROMPT = "What is 17 * 23? Answer with just the number."


def post(url, path, body, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url + path, data=json.dumps(body).encode(), headers=h)
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8090")
    ap.add_argument("--model", default="qwen3.8-27B-q6-32k")
    a = ap.parse_args()

    msgs = [{"role": "user", "content": PROMPT}]
    rows = []
    for effort, want in ((None, False), ("none", False), ("minimal", True), ("high", True)):
        body = {"model": a.model, "messages": msgs, "max_tokens": 12000, "temperature": 0}
        if effort is not None:
            body["reasoning_effort"] = effort
        m = post(a.url, "/v1/chat/completions", body)["choices"][0]["message"]
        think = m.get("reasoning_content") or ""
        rows.append((f"openai reasoning_effort={effort}", want, len(think), (m.get("content") or "").strip()[:40]))
    for thinking, want in ((None, False), ({"type": "enabled", "budget_tokens": 2048}, True), ({"type": "adaptive"}, True)):
        body = {"model": a.model, "messages": msgs, "max_tokens": 12000, "temperature": 0}
        if thinking is not None:
            body["thinking"] = thinking
        r = post(a.url, "/v1/messages", body, {"anthropic-version": "2023-06-01"})
        think = "".join(b.get("thinking", "") for b in r.get("content", []) if b.get("type") == "thinking")
        text = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        rows.append((f"anthropic thinking={thinking and thinking['type']}", want, len(think), text.strip()[:40]))

    bad = 0
    for name, want, n, text in rows:
        ok = (n > 0) == want
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {name:38s} thinking {n:6d} chars  answer {text!r}")
    print("all rows as expected" if not bad else f"{bad} row(s) wrong")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
