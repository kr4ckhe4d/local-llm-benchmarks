#!/usr/bin/env python3
"""Inference strategies on top of code-quality-test.py, same tasks, same hidden checks.

code-quality-test.py measures one answer per task. These strategies spend more
inference to get a better answer, without ever showing the model the hidden
checks:

  repair     the model writes its function, then its own assert tests; the
             harness runs them and feeds failures back, up to --rounds fixes.
             Tests may not import the module being reimplemented.
  vote       --k samples; each runs on harness-generated fuzz inputs (not the
             hidden cases) and the answer agreeing with the most others wins.
  plan       a thinking-on request writes a plan, no code; a thinking-off
             request writes the code from that plan.
  checklist  one request, the prompt asks for edge cases and a hand trace
             before the code block.
  review     a second model (--reviewer) reviews the first answer; the author
             model revises it given the review.

Added 2026-11-05 after csv_rows collapsed 7 -> 0 on a missing `field = []`, a
slip one run of the code would have caught. Runs model-written code, see
code-quality-test.py.
"""
import argparse, importlib.util, json, os, random, re, subprocess, sys, tempfile, time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("cq", HERE / "code-quality-test.py")
cq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cq)

# Module each task reimplements; self-tests importing it would be an oracle.
REF_MODULES = {"glob_match": "fnmatch", "shlex_split": "shlex", "urljoin_": "urllib",
               "wrap_": "textwrap", "csv_rows": "csv", "add_months": None,
               "parse_qsl_": "urllib"}


# The real stdlib function under the task's name. Running the model's
# differential test against it grades the TEST: a correct test reports 0
# mismatches. This uses only the stdlib, never the hidden checks. add_months
# has no stdlib equivalent, so its test is left unvalidated.
REF_IMPL = {
    "glob_match": "import fnmatch as _r\ndef glob_match(pattern, name): return _r.fnmatchcase(name, pattern)\n",
    "shlex_split": "import shlex as _r\ndef shlex_split(s): return _r.split(s)\n",
    "urljoin_": "import urllib.parse as _r\ndef urljoin_(base, url): return _r.urljoin(base, url)\n",
    "wrap_": "import textwrap as _r\ndef wrap_(text, width): return _r.wrap(text, width)\n",
    "csv_rows": "import csv as _r, io as _io\ndef csv_rows(text): return [r for r in _r.reader(_io.StringIO(text))]\n",
    "parse_qsl_": "import urllib.parse as _r\ndef parse_qsl_(qs): return _r.parse_qsl(qs, keep_blank_values=True)\n",
}
MIN_CASES = 300


def ref_check(fn, test):
    """(problem or None, total cases) for the test run against the real stdlib."""
    src = REF_IMPL.get(fn)
    if not src:
        return None, None
    ok, err, out = run_py(src + "\n\n" + test)
    m = re.findall(r"MISMATCHES\s+(\d+)\s+OF\s+(\d+)", out)
    total = int(m[-1][1]) if m else None
    if ok and m and int(m[-1][0]) == 0 and total >= MIN_CASES:
        return None, total
    why = ("it reports mismatches" if m and int(m[-1][0]) else
           f"it checks only {total} cases (need {MIN_CASES}+)" if m and total < MIN_CASES else
           "it crashes or prints no MISMATCHES line")
    return (why + ":\n" + (out.strip() + "\n" + err.strip()).strip()[-1500:]), total


def fname(prompt):
    return re.search(r"`(\w+)\(", prompt).group(1)


def chat(a, messages, thinking=False, temperature=0.0, top_p=None, extra=None,
         budget=None, max_tokens=12288, model=None):
    payload = {"messages": messages, "max_tokens": max_tokens,
               "temperature": temperature,
               "chat_template_kwargs": {"enable_thinking": thinking},
               "model": model or a.model}
    if top_p is not None:
        payload["top_p"] = top_p
    if budget is not None:
        payload["reasoning_budget_tokens"] = budget
    if extra:
        payload.update(extra)
    req = urllib.request.Request(a.host + "/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=a.timeout) as r:
        return json.load(r)["choices"][0]["message"]["content"] or ""


def run_py(src, timeout=30):
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.py"
        f.write_text(src)
        try:
            p = subprocess.run([sys.executable, str(f)], capture_output=True,
                               text=True, timeout=timeout, cwd=td)
        except subprocess.TimeoutExpired:
            return False, "timeout after %ds" % timeout, ""
        return p.returncode == 0, p.stderr, p.stdout


def strip_redefs(tests, fn):
    """Drop top-level definitions of the function under test from the tests.
    Told not to, the model still put its own wrap_ in the textwrap tests;
    it shadowed every candidate and looped, so all six timed out."""
    import ast
    try:
        tree = ast.parse(tests)
    except SyntaxError:
        return tests
    lines = tests.splitlines()
    drop = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == fn:
            start = min([n.lineno] + [d.lineno for d in n.decorator_list])
            drop.update(range(start - 1, n.end_lineno))
    return "\n".join(l for i, l in enumerate(lines) if i not in drop)


def dedupe_lines(src):
    seen, out = set(), []
    for line in src.splitlines():
        if line.strip().startswith("assert") and line in seen:
            continue
        seen.add(line); out.append(line)
    return "\n".join(out)


def salvage_tests(tests):
    """Tests that will not compile: keep the lines that compile on their own.
    Asserts are almost always one line, so this keeps most of a file that one
    mis-escaped string literal would otherwise void (shlex_split: the model
    could not write its backslash cases in three attempts)."""
    try:
        compile(tests, "tests", "exec")
        return tests
    except SyntaxError:
        pass
    keep = []
    for line in tests.splitlines():
        try:
            compile(line, "line", "exec")
            keep.append(line)
        except SyntaxError:
            continue
    return "\n".join(keep)


# ---------------------------------------------------------------- repair
TEST_REQ = (
    "Now write tests for your function: one code block of plain `assert` "
    "statements, each in the form `assert got == want, (got, want)`, covering "
    "every edge case the task lists. Work out each expected value by hand "
    "from the specification. Do not import {mod}, and do not redefine the "
    "function.")
TESTFIX_REQ = (
    "Your test code does not compile: {err}. Rewrite the tests, same rules, "
    "in one code block. Do not repeat the function.")
FIX_REQ = (
    "Running your tests against your function failed:\n```\n{err}\n```\n"
    "Find the bug. If the function is wrong, fix it; if the expected value in "
    "the test is wrong, say so and keep the function. Output the complete "
    "function, and nothing else, in one code block.")


def strat_repair(a, name, prompt, log):
    fn = fname(prompt)
    msgs = [{"role": "user", "content": prompt}]
    body = chat(a, msgs)
    code = cq.extract_code(body)
    msgs += [{"role": "assistant", "content": body},
             {"role": "user", "content": TEST_REQ.format(
                 mod=REF_MODULES.get(fn) or "any module that already does this")}]
    tbody = chat(a, msgs)
    tests = cq.extract_code(tbody)
    msgs.append({"role": "assistant", "content": tbody})
    # Tests that do not even compile give the model a SyntaxError it would
    # then "fix" in the function; ask for the tests again instead (seen on
    # shlex_split, whose tests mis-escaped a quote in all three rounds).
    for _ in range(2):
        try:
            compile(tests, "tests", "exec")
            break
        except SyntaxError as e:
            msgs.append({"role": "user", "content": TESTFIX_REQ.format(err=f"{e.msg} at line {e.lineno}: {e.text!r}")})
            tbody = chat(a, msgs)
            msgs.append({"role": "assistant", "content": tbody})
            tests = cq.extract_code(tbody)
            log.append({"turn": "tests-rewrite", "body": tbody, "syntax_error": e.msg})
    tests = strip_redefs(salvage_tests(tests), fn)
    if not re.search(r"^\s*assert\b", tests, re.M):
        log.append({"turn": "tests", "body": tbody, "usable": False})
        return code, "no usable self-tests, first answer kept"
    mod = REF_MODULES.get(fn)
    oracle = bool(mod and re.search(rf"^\s*(import|from)\s+{mod}\b", tests, re.M))
    log.append({"turn": "tests", "body": tbody, "imports_reference": oracle})
    for rnd in range(a.rounds + 1):
        ok, err, _ = run_py(code + "\n\n" + tests)
        log.append({"turn": f"run{rnd}", "ok": ok, "err": err[-1500:]})
        if ok or rnd == a.rounds:
            break
        msgs.append({"role": "user", "content": FIX_REQ.format(err=err.strip()[-1500:])})
        fbody = chat(a, msgs)
        msgs.append({"role": "assistant", "content": fbody})
        new = cq.extract_code(fbody)
        if re.search(rf"^def {fn}\(", new, re.M):
            code = new
        log.append({"turn": f"fix{rnd + 1}", "body": fbody})
    note = f"self-tests {'pass' if ok else 'FAIL'} after {rnd} fix(es)"
    if oracle:
        note += ", tests imported reference"
    return code, note


# ---------------------------------------------------------------- oracle
# A different tier from the rest: the model may test against the real stdlib
# function. It still never sees the hidden checks, but it no longer has to
# know the behaviour, only to debug toward it -- what a developer porting a
# library would do. Added after textwrap's long-word packing proved to be a
# misunderstanding the model's own tests shared, so no self-check could fix it.
ORACLE_TEST_REQ = (
    "Now write a differential test script for your function. It may import "
    "the standard-library function you are reproducing and must compare your "
    "function against it on every edge case the task lists plus at least 300 "
    "seeded random inputs you generate (random.Random(0)). Treat two "
    "exceptions of the same type as a match, and guard every call so one "
    "exception never stops the run. Check every case, print the first 5 "
    "mismatches (input, your output, reference output), then print exactly "
    "`MISMATCHES <n> OF <total>` on the last line and exit with status 1 if "
    "n > 0. Do not redefine the function. One code block.")
ORACLE_FIX_REQ = (
    "The differential test found a mismatch:\n```\n{err}\n```\n"
    "If the function is wrong, output the complete corrected function, and "
    "nothing else, in one code block; it must still not import the module it "
    "reproduces. If instead the TEST is wrong (for example it compares "
    "exception objects with ==, which is never true), output the complete "
    "corrected test script in one code block, without the function.")


TEST_BAD_REQ = (
    "Your test was run with the REAL standard-library function substituted "
    "for yours, and {err}\n\nIn that run the function your test treats as "
    "yours WAS the real one, so every mismatch shown comes from the test "
    "itself: how it calls the reference (argument order, keyword arguments) "
    "or how it compares results and exceptions. A correct differential test "
    "reports MISMATCHES 0 against the real function. Output the complete "
    "corrected test script in one code block, without the function.")
TEST_REJECTED = (
    "Your corrected test was rejected: with the real standard-library "
    "function substituted, {err}\nThe previous test stays. Fix the function "
    "instead.")


def strat_oracle(a, name, prompt, log):
    fn = fname(prompt)
    msgs = [{"role": "user", "content": prompt}]
    body = chat(a, msgs)
    code = cq.extract_code(body)
    msgs += [{"role": "assistant", "content": body},
             {"role": "user", "content": ORACLE_TEST_REQ}]
    # The model tends to paste its whole function into the test despite being
    # told not to; at 6144 tokens that truncated glob_match's test mid-line,
    # and the SyntaxError then burned all four fix rounds.
    # Retries start from the same base conversation: keeping failed attempts
    # in history filled the 32K context on urljoin and truncated every retry.
    base, test, tbody = list(msgs), "", ""
    for attempt in range(3):
        if attempt:
            msgs = base[:-1] + [{"role": "user", "content": base[-1]["content"] +
                                 " Keep it under 150 lines: generate random cases in a loop "
                                 "instead of listing them, and do not repeat the function."}]
        # temp 0 retries reproduced the same looping, truncated urljoin test
        # byte for byte; vary them, and cap so a loop fails fast.
        tbody = chat(a, msgs, max_tokens=4096,
                     temperature=0.6 if attempt else 0.0, top_p=0.95 if attempt else None)
        raw = tbody.split("```", 1)[-1] if tbody.count("```") == 1 else tbody
        test = strip_redefs(cq.extract_code(raw).removeprefix("python\n"), fn)
        log.append({"turn": f"difftest{attempt}", "body": tbody})
        try:
            compile(test, "difftest", "exec")
            msgs.append({"role": "assistant", "content": tbody})
            break
        except SyntaxError:
            test = ""
    if not test:
        return code, "no compiling differential test, first answer kept"
    # Fix the TEST before ranking, against the stdlib only: textwrap's test
    # crashed on its own `cases.append("hello", 10)`, every candidate scored
    # "crash" and selection was blind.
    # glob_match: a test calling fnmatchcase(pattern, name) survived 3 fixes,
    # and the climb then bent a correct answer toward it (lost `class`). An
    # invalid test is never used: fresh tests are drawn, and if none passes
    # against the stdlib the greedy answer is returned untouched.
    tnote, valid = "test unvalidated (no stdlib reference)", fn not in REF_IMPL
    for fresh in range(3):
        if fresh:
            tb = chat(a, base, max_tokens=4096, temperature=0.6, top_p=0.95)
            log.append({"turn": f"freshtest{fresh}", "body": tb})
            raw = tb.split("```", 1)[-1] if tb.count("```") == 1 else tb
            test = strip_redefs(cq.extract_code(raw).removeprefix("python\n"), fn)
            try:
                compile(test, "difftest", "exec")
            except SyntaxError:
                continue
            msgs = base + [{"role": "assistant", "content": tb}]
        for vfix in range(4):
            bad, ref_total = ref_check(fn, test)
            log.append({"turn": f"refcheck{fresh}.{vfix}", "problem": bad, "total": ref_total})
            if valid or bad is None:
                if not valid:
                    valid = True
                    tnote = (f"test valid vs stdlib ({ref_total} cases, "
                             f"{fresh} fresh draw(s), {vfix} test fix(es))")
                break
            if vfix == 3:
                break
            msgs.append({"role": "user", "content": TEST_BAD_REQ.format(err=bad)})
            vb = chat(a, msgs, max_tokens=4096)
            msgs.append({"role": "assistant", "content": vb})
            new_t = strip_redefs(cq.extract_code(vb).removeprefix("python\n"), fn)
            log.append({"turn": f"testfix{fresh}.{vfix + 1}", "body": vb})
            try:
                compile(new_t, "difftest", "exec")
                test = new_t
            except SyntaxError:
                pass
        if valid:
            break
    if not valid:
        return code, "no test passed against the stdlib in 3 draws x 3 fixes: greedy answer kept, no ranking or repair"
    sel_note = ""
    if a.strategy == "oracle-select":
        # Rank sampled candidates by the model's own differential test before
        # climbing. Repair never reached urljoin's dot_only fix, but sampling
        # has produced 9/9 answers; the test, not the hidden checks, picks.
        mod = REF_MODULES.get(fn)
        def counted(c):
            if mod and re.search(rf"^\s*(import|from)\s+{mod}\b", c, re.M):
                return 10**9   # an answer that wraps the reference scores 0; void it
            ok_, e_, o_ = run_py(c + "\n\n" + test)
            if ok_:
                return 0
            m_ = re.findall(r"MISMATCHES\s+(\d+)\s+OF\s+(\d+)", o_)
            return int(m_[-1][0]) if m_ else 10**9
        pool = [(counted(code), 0, code)]
        for i in range(1, a.k + 1):
            cb = chat(a, [{"role": "user", "content": prompt}], temperature=a.temperature,
                      top_p=a.top_p, extra={"top_k": 20, "min_p": 0.0})
            cc = cq.extract_code(cb)
            pool.append((counted(cc), i, cc))
            log.append({"turn": f"cand{i}", "body": cb, "mismatches": pool[-1][0]})
        n0, pick, code = min(pool, key=lambda t: (t[0], t[1]))
        sel_note = (f"candidates mismatches {['x' if t[0] == 10**9 else t[0] for t in pool]}, "
                    f"picked cand{pick}; ")
        msgs[1] = {"role": "assistant", "content": "```python\n" + code + "\n```"}
    # Hill-climb on the model's own mismatch count: urljoin oscillated
    # between two fixes for eight rounds, and textwrap's best version (5/6)
    # was overwritten by worse ones. Keep the best; it decides nothing from
    # the hidden checks.
    def mismatches(o, e, passed):
        if passed:
            return 0
        m = re.findall(r"MISMATCHES\s+(\d+)\s+OF\s+(\d+)", o)
        return int(m[-1][0]) if m else 10**9   # crash or no count: worst
    rnd, ok, last_report = 0, False, None
    best_code, best_n, pending = code, None, ""
    for rnd in range(a.rounds + 1):
        ok, err, out = run_py(code + "\n\n" + test)
        n = mismatches(out, err, ok)
        log.append({"turn": f"run{rnd}", "ok": ok, "mismatches": n,
                    "out": out[-1500:], "err": err[-1500:]})
        if best_n is None or n < best_n:
            best_code, best_n = code, n
        if ok or rnd == a.rounds:
            break
        report = (out.strip() + "\n" + err.strip()).strip()[-1500:]
        stuck = report == last_report
        last_report = report
        req = ORACLE_FIX_REQ.format(err=report)
        if pending:
            req, pending = pending + "\n\n" + req, ""
        if stuck:
            # urljoin: four temp-0 "fixes" left the same '.' mismatch in place.
            req = ("Your last change did not fix this; the output is unchanged. "
                   "Trace the failing input through the code step by step and "
                   "change the logic that produces it.\n\n" + req)
        msgs.append({"role": "user", "content": req})
        fbody = chat(a, msgs, temperature=0.6 if stuck else 0.0,
                     top_p=0.95 if stuck else None)
        msgs.append({"role": "assistant", "content": fbody})
        new = cq.extract_code(fbody)
        if re.search(rf"^def {fn}\(", new, re.M):
            code = new
            log.append({"turn": f"fix{rnd + 1}", "kind": "function", "body": fbody})
        else:
            # textwrap's test compared ValueError objects with ==, so it
            # reported its first case as a mismatch forever; let it fix that.
            # A rewritten test is accepted only if the real stdlib still
            # passes it with at least as many cases: the model may not make
            # the test easier to make its function pass.
            try:
                compile(new, "difftest", "exec")
                bad, t2 = ref_check(fn, new)
                if fn in REF_IMPL and (bad or (ref_total and t2 < ref_total)):
                    rejected = bad or f"it checks {t2} cases, fewer than the {ref_total} before"
                    log.append({"turn": f"fix{rnd + 1}", "kind": "test-rejected", "body": fbody,
                                "why": rejected})
                    pending = TEST_REJECTED.format(err=rejected)
                else:
                    test, ref_total = new, t2 or ref_total
                    best_n = None   # counts from a different test do not compare
                    log.append({"turn": f"fix{rnd + 1}", "kind": "test", "body": fbody})
            except SyntaxError:
                log.append({"turn": f"fix{rnd + 1}", "kind": "unusable", "body": fbody})
    code = best_code
    mod = REF_MODULES.get(fn)
    if mod and re.search(rf"^\s*(import|from)\s+{mod}\b", code, re.M):
        return "", "solution imported the reference module: voided"
    nn = "crash" if best_n == 10**9 else best_n
    return code, tnote + "; " + sel_note + f"difftest {'pass' if ok else 'FAIL'} after {rnd} fix(es), kept best: {nn} mismatches"


# ---------------------------------------------------------------- vote
def fuzz_inputs(fn, n=150):
    r = random.Random(20261105)
    pick = lambda alpha, lo, hi: "".join(r.choice(alpha) for _ in range(r.randint(lo, hi)))
    out = []
    for _ in range(n):
        if fn == "glob_match":
            pat = pick("aab*?[]!-", 0, 6)
            if r.random() < 0.5:   # a name built from the pattern, so matches happen
                name = "".join(pick("ab", 0, 2) if c == "*" else r.choice("ab") if c in "?[]!" else c
                               for c in pat)
            else:
                name = pick("ab-]!", 0, 5)
            out.append((pat, name))
        elif fn == "shlex_split":
            out.append((pick(["a", "b", "a", "b", " ", " ", '"', "'", "\\", "\t"], 0, 10),))
        elif fn == "urljoin_":
            toks = ["g", "..", ".", "/", "?y", "#s", "//x.com", "http:", "g/", ";x"]
            out.append(("http://a.com/b/c/d;p?q",
                        "".join(r.choice(toks) for _ in range(r.randint(0, 4)))))
        elif fn == "wrap_":
            words = [pick("ab", 1, 14) for _ in range(r.randint(0, 8))]
            seps = [r.choice([" ", "  ", "\t", "\n "]) for _ in words]
            out.append(("".join(w + s for w, s in zip(words, seps)), r.randint(3, 15)))
        elif fn == "csv_rows":
            out.append((pick(["a", "b", ",", '"', "\n", "\r\n", " "], 0, 12),))
        elif fn == "add_months":
            y, m = r.randint(1990, 2030), r.randint(1, 12)
            import calendar
            out.append((y, m, r.randint(1, calendar.monthrange(y, m)[1]), r.randint(-40, 40)))
        elif fn == "parse_qsl_":
            out.append((pick(["a", "b", "=", "&", "+", "%20", "%", "%2", "%41", ";"], 0, 8),))
    return out


SIG_RUNNER = """
import json
_out = []
for _args in json.loads({inp!r}):
    try:
        _out.append(repr({fn}(*_args)))
    except Exception as _e:
        _out.append("EXC " + type(_e).__name__)
print("__SIG__" + json.dumps(_out))
"""


def signature(code, fn, inputs):
    ok, err, out = run_py(code + "\n" + SIG_RUNNER.format(inp=json.dumps(inputs), fn=fn))
    for line in out.splitlines():
        if line.startswith("__SIG__"):
            return json.loads(line[7:])
    return None


def strat_vote(a, name, prompt, log):
    fn = fname(prompt)
    inputs = [list(x) for x in fuzz_inputs(fn)]
    cands = []
    for i in range(a.k):
        body = chat(a, [{"role": "user", "content": prompt}], temperature=a.temperature,
                    top_p=a.top_p, extra={"top_k": 20, "min_p": 0.0})
        code = cq.extract_code(body)
        sig = signature(code, fn, inputs)
        res, err = cq.run_checks(code, cq_checks[name], 30)
        hidden = sum(ok for _, ok in res) if res else 0
        cands.append({"code": code, "sig": sig, "hidden": hidden})
        log.append({"turn": f"cand{i}", "body": body, "hidden": hidden,
                    "ran": sig is not None})
    live = [c for c in cands if c["sig"] is not None]
    if not live:
        return cands[0]["code"], "no candidate ran"
    for c in live:
        c["agree"] = sum(sum(x == y for x, y in zip(c["sig"], o["sig"]))
                         for o in live if o is not c)
    best = max(live, key=lambda c: c["agree"])   # first max wins ties
    hs = [c["hidden"] for c in cands]
    return best["code"], f"candidates {hs}, picked {best['hidden']}"


# ---------------------------------------------------------------- select
# vote showed the good answers exist (best-of-5 would have scored 46/50) but
# agreement picks the shared mistake. select scores candidates against the
# model's own tests instead, one assert at a time, agreement only as tiebreak.
TESTS_ONLY_REQ = (
    "\n\nDo not write the function. Write only tests for it: one code block of "
    "plain `assert` statements, each `assert got == want, (got, want)`, "
    "covering every edge case above, at most 40 asserts. Work out each "
    "expected value by hand from the specification. Do not import {mod}.")

ASSERT_RUNNER = """
import ast, json
_src = {tests!r}
_ok = _n = 0
for _node in ast.parse(_src).body:
    _code = compile(ast.Module([_node], []), "tests", "exec")
    if isinstance(_node, ast.Assert):
        _n += 1
        try:
            exec(_code, globals()); _ok += 1
        except Exception:
            pass
    else:
        try:
            exec(_code, globals())
        except Exception:
            pass
print("__PASS__" + json.dumps([_ok, _n]))
"""


def passes(code, tests):
    ok, err, out = run_py(code + "\n" + ASSERT_RUNNER.format(tests=tests))
    for line in out.splitlines():
        if line.startswith("__PASS__"):
            return json.loads(line[8:])
    return None


def strat_select(a, name, prompt, log):
    fn = fname(prompt)
    mod = REF_MODULES.get(fn) or "any module that already does this"
    tests = ""
    for _ in range(3):   # tests that do not compile are useless for ranking
        # 4096 cap and dedupe: at temp 0 the glob_match tests looped on one
        # wrong assert ~250 times until max_tokens, 13 minutes for one task.
        tbody = chat(a, [{"role": "user", "content": prompt + TESTS_ONLY_REQ.format(mod=mod)}],
                     max_tokens=4096)
        tests = dedupe_lines(cq.extract_code(tbody.split("```", 1)[-1] if tbody.count("```") == 1 else tbody))
        try:
            compile(tests, "tests", "exec"); break
        except SyntaxError:
            tests = salvage_tests(tests)
    tests = strip_redefs(tests, fn)
    log.append({"turn": "tests", "body": tbody, "compiles": bool(tests)})
    inputs = [list(x) for x in fuzz_inputs(fn)]
    cands = []
    for i in range(a.k + 1):     # candidate 0 is the temp-0 answer
        greedy = i == 0
        body = chat(a, [{"role": "user", "content": prompt}],
                    temperature=0.0 if greedy else a.temperature,
                    top_p=None if greedy else a.top_p,
                    extra=None if greedy else {"top_k": 20, "min_p": 0.0})
        code = cq.extract_code(body)
        res, _ = cq.run_checks(code, cq_checks[name], 30)
        c = {"code": code, "hidden": sum(o for _, o in res) if res else 0,
             "pass": passes(code, tests) if tests else None,
             "sig": signature(code, fn, inputs)}
        cands.append(c)
        log.append({"turn": f"cand{i}", "body": body, "hidden": c["hidden"], "pass": c["pass"]})
    # Rank every candidate. Filtering on a fuzz signature first dropped the
    # only textwrap answer that passed its tests (it hung on a fuzz input),
    # and a 3/6 answer won by default. Agreement now only breaks ties.
    for c in cands:
        c["agree"] = sum(sum(x == y for x, y in zip(c["sig"] or [], o["sig"] or []))
                         for o in cands if o is not c)
    best = max(cands, key=lambda c: ((c["pass"] or [0])[0], c["agree"]))
    note = (f"candidates {[c['hidden'] for c in cands]} "
            f"self-test {[(c['pass'] or ['-'])[0] for c in cands]}/{max((c['pass'] or [0, 0])[1] for c in cands)}, "
            f"picked {best['hidden']}")
    code = best["code"]
    if a.rounds and tests:
        msgs = [{"role": "user", "content": prompt},
                {"role": "assistant", "content": "```python\n" + code + "\n```"}]
        for rnd in range(a.rounds):
            ok, err, _ = run_py(code + "\n\n" + tests)
            if ok:
                break
            msgs.append({"role": "user", "content": FIX_REQ.format(err=err.strip()[-1500:])})
            fbody = chat(a, msgs)
            msgs.append({"role": "assistant", "content": fbody})
            new = cq.extract_code(fbody)
            if re.search(rf"^def {fn}\(", new, re.M):
                code = new
            log.append({"turn": f"fix{rnd + 1}", "body": fbody})
        note += f", then {rnd + 1 if not ok else rnd} fix round(s)"
    return code, note


# ---------------------------------------------------------------- plan
PLAN_REQ = ("\n\nDo not write the code yet. Write a concise implementation "
            "plan: the algorithm, and every edge case and exact behaviour the "
            "function must match. No code blocks.")


def strat_plan(a, name, prompt, log):
    plan = chat(a, [{"role": "user", "content": prompt + PLAN_REQ}], thinking=True,
                budget=a.budget, max_tokens=a.budget + 8192)
    log.append({"turn": "plan", "body": plan})
    body = chat(a, [{"role": "user", "content":
                     prompt + "\n\nImplementation plan to follow:\n\n" + plan}])
    log.append({"turn": "code", "body": body})
    return cq.extract_code(body), f"plan {len(plan)} chars"


# ---------------------------------------------------------------- checklist
CHECKLIST = ("\n\nBefore the code block, list the edge cases the function must "
             "handle, then trace your function by hand on one small input to "
             "confirm it works. Use a code block only for the final function.")


def strat_checklist(a, name, prompt, log):
    body = chat(a, [{"role": "user", "content": prompt + CHECKLIST}])
    log.append({"turn": "answer", "body": body})
    return cq.extract_code(body), ""


# ---------------------------------------------------------------- review
REVIEW_REQ = ("Review this Python function for correctness against the task. "
              "List concrete bugs with the input that triggers each; say "
              "'no bugs found' if there are none. Do not rewrite the function."
              "\n\nTask:\n{prompt}\n\nFunction:\n```python\n{code}\n```")
REVISE_REQ = ("A reviewer wrote:\n\n{review}\n\nFix any real bugs it found and "
              "ignore claims that are wrong. Output the complete function in "
              "one code block.")


def strat_review(a, name, prompt, log):
    msgs = [{"role": "user", "content": prompt}]
    body = chat(a, msgs)
    code = cq.extract_code(body)
    review = chat(a, [{"role": "user", "content": REVIEW_REQ.format(prompt=prompt, code=code)}],
                  model=a.reviewer, max_tokens=16384)
    log.append({"turn": "review", "body": review})
    msgs += [{"role": "assistant", "content": body},
             {"role": "user", "content": REVISE_REQ.format(review=review)}]
    rbody = chat(a, msgs)
    log.append({"turn": "revise", "body": rbody})
    new = cq.extract_code(rbody)
    if re.search(rf"^def {fname(prompt)}\(", new, re.M):
        code = new
    return code, ""


STRATS = {"oracle": strat_oracle, "oracle-select": strat_oracle, "repair": strat_repair, "vote": strat_vote, "select": strat_select, "plan": strat_plan,
          "checklist": strat_checklist, "review": strat_review}
cq_checks = {n: c for n, _, c in cq.TASKS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy", choices=STRATS)
    ap.add_argument("--host", default="http://127.0.0.1:8090")
    ap.add_argument("--model", default="qwen3.8-27B-q8-32k")
    ap.add_argument("--label", default=None)
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--save-dir", default=None)
    ap.add_argument("--rounds", type=int, default=2, help="repair/select: max fix rounds (select: 0 = no repair)")
    ap.add_argument("--k", type=int, default=5, help="vote/select: sampled candidates per task")
    ap.add_argument("--temperature", type=float, default=0.6, help="vote: sampling temperature")
    ap.add_argument("--top-p", type=float, default=0.95, help="vote: top_p")
    ap.add_argument("--budget", type=int, default=8000, help="plan: reasoning budget")
    ap.add_argument("--reviewer", default=None, help="review: router preset of the reviewer")
    ap.add_argument("--only", default=None, help="comma-separated task names")
    a = ap.parse_args()
    if a.strategy == "review" and not a.reviewer:
        ap.error("review needs --reviewer")
    if a.save_dir:
        Path(a.save_dir).mkdir(parents=True, exist_ok=True)

    tot_ok = tot = full = 0
    print(f"\n=== {a.label or a.strategy} ===", flush=True)
    for name, prompt, checks in cq.TASKS:
        if a.only and name not in a.only.split(","):
            continue
        log, t0 = [], time.time()
        n = cq.n_checks(checks)
        try:
            code, note = STRATS[a.strategy](a, name, prompt, log)
        except Exception as e:
            print(f"  {name:18s}  0/{n}   STRATEGY FAILED {type(e).__name__}: {e}", flush=True)
            tot += n
            continue
        if a.save_dir:
            Path(a.save_dir, f"{name}.py").write_text(code)
            Path(a.save_dir, f"{name}.log.json").write_text(json.dumps(log, indent=1))
        res, err = cq.run_checks(code, checks, 30)
        dt = f"{time.time() - t0:.0f}s"
        if res is None:
            print(f"  {name:18s}  0/{n}   DID NOT RUN — {err}  [{note}; {dt}]", flush=True)
            tot += n
            continue
        ok = sum(1 for _, v in res if v)
        miss = [k for k, v in res if not v]
        tot_ok += ok; tot += len(res); full += not miss
        tail = "clean" if not miss else "missed: " + ", ".join(miss)
        print(f"  {name:18s}  {ok}/{len(res)}   {tail}  [{note}{'; ' if note else ''}{dt}]", flush=True)
    print(f"\n{a.label or a.strategy}: {tot_ok}/{tot} checks pass "
          f"({100 * tot_ok / max(tot, 1):.1f}%) | {full}/{len(cq.TASKS)} tasks fully clean", flush=True)


if __name__ == "__main__":
    main()
