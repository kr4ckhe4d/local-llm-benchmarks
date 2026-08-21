#!/usr/bin/env python3
"""Measure whether a model's *library* knowledge is current, objectively.

The premise: a model asked to build a self-contained browser page must emit
real CDN URLs from memory. Stale training data shows up as dead paths -- a
version that was yanked, a UMD bundle that moved, a package that never shipped
the file shape the model believes in. That is checkable without judgement:
regex every <script src>/<link href>, HEAD each one, count what resolves.

This is the repo's "recharts_test.py" idea (handover.md, helper-scripts list),
generalised past Recharts. It scores two things at once -- knowledge freshness
and whether the model can assemble a working page -- because on this box those
failed together (see the Recharts/MUI UMD gotchas in handover.md).

  ./cdn-freshness-test.py --host http://127.0.0.1:8099 --runs 3 --label qwen3.8

Scoring is per-URL, not per-run: a run emitting 6 good URLs and a run emitting
1 good URL are not equally informative, so both the URL rate and the
all-URLs-resolve run rate are reported.
"""
import argparse, json, re, sys, urllib.error, urllib.request

PROMPTS = [
    "Build a single self-contained HTML file that renders a Recharts bar chart of "
    "five hardcoded values. Load React, ReactDOM, PropTypes and Recharts from a CDN "
    "with <script src> tags. Output only the HTML.",
    "Build a single self-contained HTML file showing a Material UI (MUI) card with a "
    "button, loading React, ReactDOM, Emotion and MUI from a CDN via <script src> "
    "tags. Output only the HTML.",
    "Build a single self-contained HTML file that renders a Chart.js line chart and a "
    "D3 axis below it, loading both libraries from a CDN via <script src> tags. "
    "Output only the HTML.",
]
SRC_RE = re.compile(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', re.I)

def ask(host, prompt, timeout):
    req = urllib.request.Request(
        host + "/v1/chat/completions",
        data=json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000, "temperature": 0.0,
            "chat_template_kwargs": {"enable_thinking": False},
        }).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)["choices"][0]["message"]["content"] or ""

def head(url, timeout=20):
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith("http"):
        return None                      # relative/local path, not a CDN claim
    # Bare origins are <link rel=preconnect/dns-prefetch> hints, not assets.
    # They legitimately 404 on a HEAD and scoring them punishes correct markup.
    from urllib.parse import urlparse
    if urlparse(url).path in ("", "/"):
        return None
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 300
    except urllib.error.HTTPError as e:
        if e.code in (403, 405):         # some CDNs reject HEAD; retry as GET
            try:
                req = urllib.request.Request(url)
                req.add_header("User-Agent", "Mozilla/5.0")
                req.add_header("Range", "bytes=0-64")
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return 200 <= r.status < 300
            except Exception:
                return False
        return False
    except Exception:
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8099")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--label", default="model")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    ok = bad = 0
    clean_runs = total_runs = 0
    for r in range(a.runs):
        for pi, p in enumerate(PROMPTS):
            try:
                body = ask(a.host, p, a.timeout)
            except Exception as e:
                print(f"  run{r+1} prompt{pi+1}: REQUEST FAILED {type(e).__name__}: {e}")
                total_runs += 1
                continue
            urls = [u for u in dict.fromkeys(SRC_RE.findall(body)) if head(u) is not None]
            results = [(u, head(u)) for u in urls]
            good = sum(1 for _, v in results if v)
            ok += good; bad += len(results) - good
            total_runs += 1
            if results and good == len(results):
                clean_runs += 1
            print(f"  run{r+1} prompt{pi+1}: {good}/{len(results)} resolve")
            for u, v in results:
                if not v:
                    print(f"      DEAD  {u}")
    tot = ok + bad
    print(f"\n{a.label}: {ok}/{tot} URLs resolve"
          f" ({(ok/tot*100 if tot else 0):.0f}%)"
          f" | {clean_runs}/{total_runs} runs fully clean")

if __name__ == "__main__":
    main()
