#!/usr/bin/env python3
"""Measure long-context recall decay on a running llama-server.

Builds one large haystack with several distinct facts ("needles") planted at
known depths, then asks about each one in a separate request. Because every
request shares the identical haystack prefix and differs only in the trailing
question, llama-server's prompt cache makes requests 2..N nearly free — the
full prefill is paid once.

  ./needle-test.py --depth 128000
  ./needle-test.py --depth 32000 --host http://127.0.0.1:8090
  ./needle-test.py --depth 119000 --no-think        # thinking models
"""
import argparse, json, re, sys, time, urllib.request

# Distinct, specific, and not inferable from context — so a hit is real recall
# rather than a plausible guess.
NEEDLES = [
    ("the retry budget for the billing reconciler", "47 milliseconds", "47"),
    ("the shard count for the sessions table",      "312 shards",      "312"),
    ("the cutover date for the legacy auth path",   "March 14th",      "march 14"),
    ("the max payload size for the ingest queue",   "8193 kilobytes",  "8193"),
    ("the on-call rotation length for platform",    "9 days",          "9"),
]

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


def ntokens(host, text):
    return len(post(host, "/tokenize", {"content": text})["tokens"])


def build(host, target):
    """Assemble a haystack of ~target tokens with needles at even depths."""
    unit = FILLER.format(i=0)
    per = ntokens(host, unit)
    total_units = max(len(NEEDLES) + 1, target // per)
    print(f"  filler unit ~{per} tok, using ~{total_units} units", file=sys.stderr)

    # Depths chosen to probe both edges and the middle, where decay is worst.
    depths = [0.05, 0.25, 0.50, 0.75, 0.95]
    planted = {int(d * total_units): n for d, n in zip(depths, NEEDLES)}

    parts, placed = [], []
    for i in range(total_units):
        if i in planted:
            subject, fact, _ = planted[i]
            parts.append(f"\n# NOTE: {subject} is {fact}.\n")
            placed.append((planted[i], i / total_units))
        parts.append(FILLER.format(i=i))
    return "".join(parts), placed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8090")
    ap.add_argument("--depth", type=int, default=128000)
    # Thinking models spend the whole max_tokens budget on reasoning_content
    # before writing a single character of content, so every needle reads as a
    # FAIL no matter how good the recall actually is. Turning thinking off is
    # also the fairer comparison: the numbers already in the README were
    # measured on Qwen3-Coder-Next, which does not think at all.
    ap.add_argument("--no-think", action="store_true",
                    help="disable reasoning (Qwen3.8, Gemma 4, Muse Glimmer)")
    a = ap.parse_args()

    print(f"Building haystack (~{a.depth} tokens)...", file=sys.stderr)
    hay, placed = build(a.host, a.depth)
    actual = ntokens(a.host, hay)
    print(f"  haystack = {actual} tokens\n", file=sys.stderr)

    print(f"{'depth':>7}  {'needle':<42} {'result':<6}  {'s':>6}")
    print("-" * 68)
    hits = 0
    for (subject, fact, key), frac in placed:
        q = (hay + f"\n\n---\n\nUsing only the notes above, answer in one short "
                   f"sentence: what is {subject}?")
        t0 = time.time()
        body = {
            "messages": [{"role": "user", "content": q}],
            "max_tokens": 60, "temperature": 0.0,
        }
        if a.no_think:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        r = post(a.host, "/v1/chat/completions", body)
        el = time.time() - t0
        ans = r["choices"][0]["message"]["content"] or ""
        # Collapse Unicode whitespace before matching. Models that emit typographic
        # spaces score a false FAIL otherwise: Nemotron-3-Nano answered
        # "March 14th" — a NARROW NO-BREAK SPACE — which is a correct recall
        # that a plain substring test against "march 14" misses.
        norm = re.sub(r"\s+", " ", re.sub(r"[,*`]", "", ans.lower()))
        ok = key.lower() in norm
        hits += ok
        print(f"{frac*100:6.0f}%  {subject:<42} {'PASS' if ok else 'FAIL':<6}  {el:6.1f}")
        if not ok:
            print(f"{'':>7}  expected {fact!r}, got: {ans.strip()[:90]!r}")

    print("-" * 68)
    print(f"recall {hits}/{len(placed)} at ~{actual} tokens")


if __name__ == "__main__":
    main()
