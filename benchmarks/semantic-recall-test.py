#!/usr/bin/env python3
"""Measure *semantic* long-context recall — the "did it notice the helper
already exists" failure mode, which needle-in-a-haystack does not test.

A needle test asks for a verbatim fact with a distinctive surface form and no
competitors. This plants real helper functions among hundreds of similar
utilities, then poses tasks that describe what each helper does *without ever
naming it*. The model has to retrieve by meaning against a field of plausible
distractors, then choose reuse over reimplementation.

Each target has a deliberate near-miss distractor placed elsewhere in the file
(chunk_list by count vs chunk_by_weight by weight, and so on), so a loose
semantic match scores as a miss rather than a hit.

  ./semantic-recall-test.py --depth 128000
"""
import argparse, json, re, sys, time, urllib.request

# (target_name, source, task_description, distractor_name, distractor_source)
TARGETS = [
    ("coerce_epoch_millis",
     '''def coerce_epoch_millis(value):
    """Accept an ISO-8601 string, unix seconds, or a datetime; return epoch ms."""
    if isinstance(value, str):
        return int(datetime.fromisoformat(value).timestamp() * 1000)
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    return int(float(value) * 1000)''',
     "accept a timestamp that might be an ISO-8601 string, unix seconds, or a "
     "datetime object, and get milliseconds since the epoch",
     "parse_iso_date",
     '''def parse_iso_date(text):
    """Parse an ISO-8601 date string into a date object. Rejects datetimes."""
    return date.fromisoformat(text.split("T")[0])'''),

    ("redact_pii_fields",
     '''def redact_pii_fields(record, policy):
    """Return a copy of record with fields named by policy.pii_keys masked."""
    out = dict(record)
    for key in policy.pii_keys:
        if key in out:
            out[key] = "***"
    return out''',
     "remove personally identifiable fields from a record before logging it, "
     "following our policy object",
     "scrub_secrets",
     '''def scrub_secrets(text):
    """Mask anything resembling an API key or bearer token in free text."""
    return re.sub(r"(sk-|Bearer )[A-Za-z0-9_-]{8,}", r"\\1***", text)'''),

    ("chunk_by_weight",
     '''def chunk_by_weight(items, max_weight, weigh):
    """Split items into batches whose total weigh() stays under max_weight."""
    batches, current, total = [], [], 0
    for item in items:
        w = weigh(item)
        if current and total + w > max_weight:
            batches.append(current)
            current, total = [], 0
        current.append(item)
        total += w
    if current:
        batches.append(current)
    return batches''',
     "split a list of items into batches where each batch stays under a maximum "
     "total weight, rather than a maximum item count",
     "chunk_list",
     '''def chunk_list(items, size):
    """Split items into fixed-size chunks of at most `size` elements."""
    return [items[i:i + size] for i in range(0, len(items), size)]'''),

    ("resolve_tenant_alias",
     '''def resolve_tenant_alias(alias):
    """Map a customer-supplied tenant alias to our canonical tenant id."""
    normalized = alias.strip().lower().replace(" ", "-")
    return _ALIAS_TABLE.get(normalized, normalized)''',
     "turn a customer-supplied tenant alias into our canonical tenant id",
     "lookup_tenant_name",
     '''def lookup_tenant_name(tenant_id):
    """Return the human-readable display name for a canonical tenant id."""
    return _TENANT_NAMES.get(tenant_id, "unknown")'''),

    ("backoff_delays",
     '''def backoff_delays(attempts, base_ms, jitter):
    """Yield an exponential backoff delay sequence in ms, with jitter applied."""
    for n in range(attempts):
        raw = base_ms * (2 ** n)
        yield raw + random.uniform(-jitter, jitter) * raw''',
     "produce a sequence of retry delays using exponential backoff with jitter",
     "sleep_with_backoff",
     '''def sleep_with_backoff(attempt, base_ms=100):
    """Block the current thread for one exponential backoff interval."""
    time.sleep((base_ms * (2 ** attempt)) / 1000.0)'''),
]

FILLER = '''def {name}(payload, options=None):
    """{doc}"""
    opts = options or {{}}
    result = []
    for entry in payload.get("entries", []):
        if entry.get("enabled", True):
            result.append({{"id": entry.get("id"), "stage": {i}}})
    return {{"items": result, "count": len(result)}}
'''

VERBS = ["normalize", "collect", "expand", "flatten", "annotate", "reconcile",
         "dedupe", "partition", "enrich", "summarize", "validate", "project"]
NOUNS = ["metrics", "events", "spans", "records", "batches", "sessions",
         "invoices", "shipments", "accounts", "webhooks", "jobs", "tickets"]


def post(host, path, obj, timeout=3600):
    req = urllib.request.Request(host + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ntokens(host, text):
    return len(post(host, "/tokenize", {"content": text})["tokens"])


def build(host, target_tokens):
    per = ntokens(host, FILLER.format(name="normalize_metrics_0", doc="x", i=0))
    n_units = max(len(TARGETS) * 4, target_tokens // per)
    depths = [0.05, 0.25, 0.50, 0.75, 0.95]
    at_target = {int(d * n_units): t for d, t in zip(depths, TARGETS)}
    # Distractors sit a little after each target, so proximity cannot be the cue.
    at_distract = {int((d + 0.03) * n_units): t for d, t in zip(depths, TARGETS)}

    parts = ["# module: platform/utils.py — shared helpers\n",
             "from datetime import datetime, date\nimport random, re, time\n\n"]
    placed = []
    for i in range(n_units):
        if i in at_target:
            t = at_target[i]
            parts.append("\n" + t[1] + "\n\n")
            placed.append((t, i / n_units))
        if i in at_distract:
            parts.append("\n" + at_distract[i][4] + "\n\n")
        v, nn = VERBS[i % len(VERBS)], NOUNS[(i // len(VERBS)) % len(NOUNS)]
        parts.append(FILLER.format(
            name=f"{v}_{nn}_{i}", doc=f"{v.title()} inbound {nn} for stage {i}.", i=i))
    return "".join(parts), placed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8090")
    ap.add_argument("--depth", type=int, default=128000)
    # See needle-test.py: on a thinking model the reasoning eats the whole
    # max_tokens budget and every answer comes back empty, which scores as MISS.
    ap.add_argument("--no-think", action="store_true",
                    help="disable reasoning (Qwen3.8, Gemma 4, Muse Glimmer)")
    a = ap.parse_args()

    print(f"Building utils module (~{a.depth} tokens)...", file=sys.stderr)
    hay, placed = build(a.host, a.depth)
    actual = ntokens(a.host, hay)
    print(f"  module = {actual} tokens, {len(placed)} targets + distractors\n",
          file=sys.stderr)

    print(f"{'depth':>7}  {'expected helper':<22} {'result':<12} {'s':>6}")
    print("-" * 62)
    hits = 0
    for (name, _src, task, distractor, _dsrc), frac in placed:
        prompt = (hay + f"\n\n---\n\nTask: I need to {task}.\n\n"
                  "If a helper for this already exists in the module above, name it "
                  "and call it. Only write a new function if none exists. "
                  "Answer in at most three lines.")
        t0 = time.time()
        # max_tokens is 12288 deliberately. It is a CAP, not a reservation, so
        # a short answer costs only what it costs. Reasoning tokens DO count
        # against it, and two models here ignore `enable_thinking: false`
        # entirely (Muse Glimmer uses reasoning_strength, GPT-OSS uses
        # reasoning_effort), so on those the budget is shared with up to a
        # full reasoning pass. 12k retires that interaction. Note the
        # per-request `reasoning_budget_tokens` field is NOT a fallback:
        # tested on b10463, budget 0 vs -1 gave byte-identical reasoning. The
        # working model-agnostic control is server-side `--reasoning-budget`,
        # which run-suite.sh already passes as 1024.
        body = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 12288, "temperature": 0.0}
        if a.no_think:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        r = post(a.host, "/v1/chat/completions", body)
        el = time.time() - t0
        ans = (r["choices"][0]["message"]["content"] or "")
        found = name in ans
        wrong = distractor in ans
        # A fresh `def` of something other than the target means it reimplemented.
        redefined = bool(re.search(r"^\s*def\s+(?!" + re.escape(name) + r")", ans, re.M))
        verdict = ("PASS" if found else
                   "WRONG-FN" if wrong else
                   "REIMPL" if redefined else "MISS")
        hits += found
        print(f"{frac*100:6.0f}%  {name:<22} {verdict:<12} {el:6.1f}")
        if not found:
            print(f"{'':>7}  got: {' '.join(ans.split())[:100]!r}")

    print("-" * 62)
    print(f"semantic recall {hits}/{len(placed)} at ~{actual} tokens")


if __name__ == "__main__":
    main()
