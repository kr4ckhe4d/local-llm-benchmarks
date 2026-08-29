#!/usr/bin/env python3
"""Score coding quality by *executing* the model's output, not reading it.

`cdn-freshness-test.py` measures whether a model's library knowledge is
current. It tied Qwen3.8-27B against Qwen3-Coder-Next (92% vs 93%), which
answers "is the knowledge stale" but not "which one writes better code".

This does the latter. Each task is a precise spec whose edge cases are easy to
miss and impossible to fudge: touching intervals, version segments of unequal
length, a cache whose recency must update on overwrite, a cycle that must
raise. The model writes the function, the function gets run against hidden
checks in a subprocess, and the score is the fraction of checks that pass.

Resolution comes from scoring individual checks rather than whole tasks: a
solution that handles the happy path and misses one edge case is materially
better than one that does not run, and all-or-nothing scoring hides that.

  ./code-quality-test.py --host http://127.0.0.1:8099 --label qwen3.8

Runs model-written code. It executes in a temp dir with a wall-clock timeout
and no arguments, but it is still model-written code running on your box --
which is the only way to score correctness rather than plausibility.
"""
import argparse, json, re, subprocess, sys, tempfile, textwrap, urllib.request
from pathlib import Path

TASKS = [
    # Differential tasks: the model reimplements a stdlib behaviour from
    # scratch, and the checks compare it against the real thing over edge
    # cases plus a seeded random batch. This is what gives the suite its
    # resolution -- an earlier version of this file used self-contained
    # leetcode-style tasks and every model scored 50/50, which measured
    # nothing. Matching `urljoin` or `shlex.split` exactly is hard; matching
    # them on the happy path only is easy. The gap between those is the score.
    ("glob_match",
     "Write a Python function `glob_match(pattern, name)` implementing "
     "fnmatch.fnmatchcase semantics FROM SCRATCH, without importing fnmatch, "
     "glob, or re. Support `*` (any run including empty), `?` (exactly one "
     "char), `[abc]` and ranges `[a-z]`, and negation `[!abc]`. A `]` "
     "immediately after `[` or `[!` is a literal. An unterminated `[` is a "
     "literal `[`. Match is anchored to the whole string. Output only the "
     "function in one code block.",
     '''
import fnmatch, random
def _diff(cases):
    return all(glob_match(p, n) == fnmatch.fnmatchcase(n, p) for p, n in cases)
def _rand():
    rnd = random.Random(1234)
    alpha = "ab?*[]!-"
    cases = []
    for _ in range(300):
        p = "".join(rnd.choice(alpha) for _ in range(rnd.randint(1, 6)))
        n = "".join(rnd.choice("abc") for _ in range(rnd.randint(0, 5)))
        cases.append((p, n))
    return _diff(cases)
CHECKS = [
 ("star",      lambda: _diff([("a*c","abc"),("a*c","ac"),("a*c","abd"),("*","")])),
 ("question",  lambda: _diff([("a?c","abc"),("a?c","ac"),("?","a"),("?","")])),
 ("class",     lambda: _diff([("[abc]","b"),("[abc]","d"),("[a-z]","q"),("[a-z]","Q")])),
 ("negation",  lambda: _diff([("[!abc]","d"),("[!abc]","a"),("[!a-z]","Q")])),
 ("rbracket",  lambda: _diff([("[]]","]"),("[!]]","a"),("[]a]","a")])),
 ("unterm",    lambda: _diff([("[abc","[abc"),("a[","a[")])),
 ("anchored",  lambda: _diff([("a","ab"),("b","ab"),("ab","ab")])),
 ("random300", _rand),
]'''),

    ("shlex_split",
     "Write a Python function `shlex_split(s)` reproducing shlex.split(s) in "
     "POSIX mode FROM SCRATCH, without importing shlex. Handle: whitespace "
     "splitting; single quotes (everything literal inside, no escapes); "
     "double quotes (a backslash escapes only another backslash, a double "
     "quote, a dollar sign or a backtick, and is otherwise literal); "
     "backslash escaping outside quotes; and adjacent quoted and unquoted "
     "runs concatenating into ONE token. Output only the function in one "
     "code block.",
     '''
import shlex
BS = chr(92); DQ = chr(34); SQ = chr(39)
def _d(cases):
    return all(shlex_split(c) == shlex.split(c) for c in cases)
CHECKS = [
 ("plain",      lambda: _d(["a b c", "  a   b  ", ""])),
 ("single_q",   lambda: _d([SQ+"a b"+SQ, SQ+"a"+BS+"b"+SQ, SQ+SQ])),
 ("double_q",   lambda: _d([DQ+"a b"+DQ, DQ+DQ])),
 ("dq_escapes", lambda: _d([DQ+"a"+BS+DQ+"b"+DQ, DQ+"a"+BS+BS+"b"+DQ,
                            DQ+"a"+BS+"$b"+DQ, DQ+"a"+BS+"nb"+DQ])),
 ("adjacent",   lambda: _d(["a"+DQ+"b"+DQ+"c", "a"+SQ+"b"+SQ+"c",
                            DQ+"a"+DQ+DQ+"b"+DQ])),
 ("backslash",  lambda: _d(["a"+BS+" b", "a"+BS+BS+"b", BS+"a"])),
 ("mixed",      lambda: _d(["echo "+SQ+"hello world"+SQ+" "+DQ+"and more"+DQ+" plain"])),
]'''),

    ("urljoin",
     "Write a Python function `urljoin_(base, url)` reproducing "
     "urllib.parse.urljoin FROM SCRATCH, without importing urllib. Implement "
     "RFC 3986 reference resolution: absolute URLs replace the base, "
     "scheme-relative `//host/p`, absolute paths `/p`, relative paths, `.` "
     "and `..` normalisation, empty string returning the base without its "
     "fragment, and query-only `?q` and fragment-only `#f` references. "
     "Output only the function in one code block.",
     '''
from urllib.parse import urljoin
B = "http://a.com/b/c/d;p?q"
def _d(cases, base=B):
    return all(urljoin_(base, u) == urljoin(base, u) for u in cases)
CHECKS = [
 ("absolute",  lambda: _d(["http://x.com/y", "https://z.org/"])),
 ("netloc",    lambda: _d(["//x.com/y"])),
 ("abs_path",  lambda: _d(["/g", "/"])),
 ("rel_path",  lambda: _d(["g", "g/", "./g"])),
 ("dotdot",    lambda: _d(["../g", "../../g", "../../../g"])),
 ("empty",     lambda: _d([""])),
 ("query",     lambda: _d(["?y"])),
 ("fragment",  lambda: _d(["#s", "g#s"])),
 ("dot_only",  lambda: _d([".", "./", "..", "../"])),
]'''),

    ("textwrap",
     "Write a Python function `wrap_(text, width)` reproducing "
     "textwrap.wrap(text, width) with default options FROM SCRATCH, without "
     "importing textwrap. Default options mean: whitespace is collapsed and "
     "tabs expanded, words longer than width ARE broken, and the result is a "
     "list of lines none longer than width (except where a single unbreakable "
     "chunk forces it). Output only the function in one code block.",
     '''
import textwrap, random
def _d(cases, w):
    return all(wrap_(t, w) == textwrap.wrap(t, w) for t in cases)
def _rand():
    rnd = random.Random(99)
    ok = True
    for _ in range(60):
        words = ["".join(rnd.choice("ab") for _ in range(rnd.randint(1, 12)))
                 for _ in range(rnd.randint(1, 10))]
        t = " ".join(words)
        w = rnd.randint(4, 20)
        if wrap_(t, w) != textwrap.wrap(t, w):
            ok = False
    return ok
CHECKS = [
 ("simple",   lambda: _d(["the quick brown fox jumps"], 10)),
 ("collapse", lambda: _d(["a   b\\tc\\n d"], 10)),
 ("longword", lambda: _d(["aaaaaaaaaaaaaaaaaaaa bb"], 8)),
 ("exact",    lambda: _d(["abcd efgh"], 4)),
 ("empty",    lambda: _d(["", "   "], 10)),
 ("random60", _rand),
]'''),

    ("csv_rows",
     "Write a Python function `csv_rows(text)` that parses RFC 4180 CSV and "
     "returns a list of rows, each a list of string fields -- matching "
     "csv.reader(io.StringIO(text)) FROM SCRATCH, without importing csv. "
     "Handle quoted fields containing commas and newlines, doubled quotes as "
     "an escaped quote, and CRLF or LF line endings. Output only the function "
     "in one code block.",
     '''
import csv, io
def _ref(t): return [r for r in csv.reader(io.StringIO(t))]
def _d(cases): return all(csv_rows(t) == _ref(t) for t in cases)
CHECKS = [
 ("plain",     lambda: _d(["a,b,c\\n1,2,3\\n"])),
 ("quoted",    lambda: _d(['a,"b,c",d\\n'])),
 ("dquote",    lambda: _d(['a,"b""c",d\\n'])),
 ("embed_nl",  lambda: _d(['a,"b\\nc",d\\n'])),
 ("crlf",      lambda: _d(["a,b\\r\\n1,2\\r\\n"])),
 ("empty_f",   lambda: _d(["a,,c\\n", ",\\n"])),
 ("no_trail",  lambda: _d(["a,b\\n1,2"])),
]'''),

    ("add_months",
     "Write a Python function `add_months(y, m, d, n)` returning a "
     "(year, month, day) tuple n calendar months after the given date, where "
     "n may be negative. If the day does not exist in the target month it is "
     "CLAMPED to the last day of that month (Jan 31 + 1 month = Feb 28, or "
     "Feb 29 in a leap year). Handle year rollover in both directions. "
     "Output only the function in one code block.",
     '''
import calendar
def _ref(y, m, d, n):
    t = (y * 12 + (m - 1)) + n
    ny, nm = divmod(t, 12); nm += 1
    return (ny, nm, min(d, calendar.monthrange(ny, nm)[1]))
def _d(cases): return all(tuple(add_months(*c)) == _ref(*c) for c in cases)
def _sweep():
    cases = [(2020 + (i % 8), 1 + (i % 12), 28 + (i % 4), (i % 61) - 30)
             for i in range(400)]
    return _d(cases)
CHECKS = [
 ("simple",   lambda: _d([(2024, 1, 15, 1), (2024, 6, 1, 3)])),
 ("clamp",    lambda: _d([(2023, 1, 31, 1), (2024, 1, 31, 1)])),
 ("rollover", lambda: _d([(2023, 12, 15, 1), (2023, 1, 15, -1)])),
 ("negative", lambda: _d([(2024, 3, 31, -1), (2024, 1, 1, -13)])),
 ("leap",     lambda: _d([(2024, 2, 29, 12), (2024, 2, 29, -12)])),
 ("sweep400", _sweep),
]'''),

    ("parse_qsl",
     "Write a Python function `parse_qsl_(qs)` reproducing "
     "urllib.parse.parse_qsl(qs, keep_blank_values=True) FROM SCRATCH, "
     "without importing urllib. Return a list of (key, value) pairs in order, "
     "decoding percent-escapes and '+' as space, keeping blank values, and "
     "treating both '&' and ';' -- no, ONLY '&' -- as the separator. A "
     "component with no '=' yields a pair with an empty value. Output only "
     "the function in one code block.",
     '''
from urllib.parse import parse_qsl
def _d(cases):
    return all(list(map(tuple, parse_qsl_(c))) == parse_qsl(c, keep_blank_values=True)
               for c in cases)
CHECKS = [
 ("basic",   lambda: _d(["a=1&b=2"])),
 ("blank",   lambda: _d(["a=&b=2", "a="])),
 ("noeq",    lambda: _d(["a&b=2"])),
 ("plus",    lambda: _d(["q=a+b"])),
 ("pct",     lambda: _d(["q=a%20b%26c", "%6b=v"])),
 ("repeat",  lambda: _d(["a=1&a=2&a=3"])),
 ("empty",   lambda: _d(["", "&", "&&a=1"])),
]'''),
]

RUNNER = '''
import json, sys
_results = []
for _name, _fn in CHECKS:
    try:
        _results.append((_name, bool(_fn())))
    except Exception as _e:
        _results.append((_name, False))
print("__RESULTS__" + json.dumps(_results))
'''

FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def n_checks(checks_src):
    """How many checks a task defines. Needed so a task that fails to RUN
    still contributes its true weight to the denominator -- an earlier
    version added a hardcoded 6, which silently made scores from different
    models incomparable whenever a solution did not compile."""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "count.py"
        f.write_text(textwrap.dedent(checks_src) + "\nprint(len(CHECKS))\n")
        try:
            p = subprocess.run([sys.executable, str(f)], capture_output=True,
                               text=True, timeout=30, cwd=td)
            return int(p.stdout.strip().splitlines()[-1])
        except Exception:
            return 0


def extract_code(text):
    """Prefer fenced blocks; fall back to the whole body if the model
    ignored the format, since an unfenced-but-correct answer is still
    correct code and penalising formatting would measure the wrong thing."""
    blocks = FENCE.findall(text)
    if blocks:
        return "\n\n".join(blocks)
    return text


def ask(host, prompt, timeout, max_tokens, model=None):
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if model:                       # router mode needs an explicit preset name
        payload["model"] = model
    req = urllib.request.Request(
        host + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)["choices"][0]["message"]["content"] or ""


def run_checks(solution, checks_src, exec_timeout):
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "candidate.py"
        f.write_text(solution + "\n\n" + textwrap.dedent(checks_src) + "\n" + RUNNER)
        try:
            p = subprocess.run([sys.executable, str(f)], capture_output=True,
                               text=True, timeout=exec_timeout, cwd=td)
        except subprocess.TimeoutExpired:
            return None, "timeout"
        for line in p.stdout.splitlines():
            if line.startswith("__RESULTS__"):
                return json.loads(line[len("__RESULTS__"):]), None
        err = (p.stderr or "").strip().splitlines()
        return None, (err[-1] if err else "no results emitted")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8099")
    ap.add_argument("--label", default="model")
    ap.add_argument("--model", default=None,
                    help="preset name, when talking to router mode on :8090")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--exec-timeout", type=int, default=30)
    # 12288, not 1600: reasoning counts against max_tokens and run-suite.sh
    # serves with --reasoning-budget 1024, so the old default left 576
    # tokens of content headroom on models that ignore enable_thinking.
    # Headroom, not a fix for a known failure. See needle-test.py.
    ap.add_argument("--max-tokens", type=int, default=12288)
    ap.add_argument("--show-code", action="store_true")
    a = ap.parse_args()

    tot_ok = tot = 0
    full = 0
    print(f"\n=== {a.label} ===")
    for name, prompt, checks_src in TASKS:
        try:
            body = ask(a.host, prompt, a.timeout, a.max_tokens, a.model)
        except Exception as e:
            n = n_checks(checks_src)
            print(f"  {name:18s}  0/{n}   REQUEST FAILED {type(e).__name__}")
            tot += n
            continue
        code = extract_code(body)
        if a.show_code:
            print(f"\n----- {name} -----\n{code}\n")
        results, err = run_checks(code, checks_src, a.exec_timeout)
        if results is None:
            n = n_checks(checks_src)
            print(f"  {name:18s}  0/{n}   DID NOT RUN — {err}")
            tot += n
            continue
        ok = sum(1 for _, v in results if v)
        tot_ok += ok; tot += len(results)
        if ok == len(results):
            full += 1
        failed = [n for n, v in results if not v]
        print(f"  {name:18s} {ok:2d}/{len(results)}"
              + (f"   missed: {', '.join(failed)}" if failed else "   clean"))
    print(f"\n{a.label}: {tot_ok}/{tot} checks pass"
          f" ({tot_ok/tot*100:.1f}%) | {full}/{len(TASKS)} tasks fully clean")


if __name__ == "__main__":
    main()
