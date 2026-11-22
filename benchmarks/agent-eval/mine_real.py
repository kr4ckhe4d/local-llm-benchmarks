#!/usr/bin/env python3
"""Find real bug-fix commits that can become agent-eval tasks (SWE-bench style).

For each recent non-merge commit of an upstream repo that changes 1-2 source .py files
(a few to 80 lines) together with at least one test file, it checks in the sandbox:

  1. parent commit + the fix commit's test files   -> some tests fail
  2. ... + the fix commit's source files            -> those tests pass, nothing else fails

The tests that flip are the task's FAIL_TO_PASS set. Candidates go to
.cache/candidates-<repo>.jsonl; turning one into a task (writing the bug report the model
sees) is done by hand, from the diff and the failing tests.

    ./mine_real.py https://github.com/pallets/click --commits 400
"""
import argparse, json, pathlib, re, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from agent_eval import CACHE, sandbox, upstream_snapshot  # noqa: E402


def git(clone, *a):
    return subprocess.run(["git", "-C", str(clone), *a], capture_output=True, text=True, check=True).stdout


def is_test(p):
    return bool(re.search(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|conftest\.py$", p))


def pytest_cmd(ws, files):
    env = "PYTHONPATH=src " if (ws / "src").is_dir() else ""
    return f"{env}python -m pytest -q -p no:cacheprovider --tb=no -rfE -o addopts='' {' '.join(files)}"


def failing(ws, files):
    code, out, err = sandbox(ws, pytest_cmd(ws, files), timeout=300)
    fails = set(re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M))
    ran = bool(re.search(r"\d+ (passed|failed)", out))
    return fails, ran, code


def show(clone, commit, path):
    return subprocess.run(["git", "-C", str(clone), "show", f"{commit}:{path}"], capture_output=True, check=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--commits", type=int, default=300)
    ap.add_argument("--max-lines", type=int, default=80)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as t:
        name = upstream_snapshot(a.url, "HEAD", pathlib.Path(t) / "probe")  # clones into the cache
    clone = CACHE / name
    out = CACHE / f"candidates-{name}.jsonl"
    found = 0
    for sha in git(clone, "log", "--no-merges", f"-n{a.commits}", "--format=%H").split():
        stat = [l.split("\t") for l in git(clone, "diff", "--numstat", f"{sha}^", sha).splitlines()]
        tests = [p for _, _, p in stat if p.endswith(".py") and is_test(p)]
        src = [(p, int(x) + int(y)) for x, y, p in stat if p.endswith(".py") and not is_test(p) and x != "-"]
        other = [p for _, _, p in stat if not p.endswith(".py") and not re.search(r"(CHANGE|HISTORY|NEWS|docs?/|\.rst$|\.md$|\.txt$)", p, re.I)]
        if not tests or not (1 <= len(src) <= 2) or other:
            continue
        lines = sum(n for _, n in src)
        if not (3 <= lines <= a.max_lines):
            continue
        test_files = [p for p in tests if pathlib.PurePath(p).name.startswith("test")]
        if not test_files:
            continue
        with tempfile.TemporaryDirectory() as t:
            ws = pathlib.Path(t) / "w"
            upstream_snapshot(a.url, f"{sha}^", ws)
            for p in tests:
                (ws / p).parent.mkdir(parents=True, exist_ok=True)
                (ws / p).write_bytes(show(clone, sha, p))
            before, ran_b, _ = failing(ws, test_files)
            if not ran_b or not before:
                continue
            for p, _ in src:
                (ws / p).parent.mkdir(parents=True, exist_ok=True)
                (ws / p).write_bytes(show(clone, sha, p))
            after, ran_a, code = failing(ws, test_files)
        f2p = sorted(before - after)
        if not ran_a or after or not f2p:
            continue
        subj = git(clone, "log", "-1", "--format=%s", sha).strip()
        date = git(clone, "log", "-1", "--format=%cs", sha).strip()
        rec = {"repo": a.url, "sha": sha, "parent": git(clone, "rev-parse", f"{sha}^").strip(), "date": date,
               "subject": subj, "src": [p for p, _ in src], "src_lines": lines, "tests": tests,
               "test_files": test_files, "fail_to_pass": f2p}
        found += 1
        with open(out, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{date} {sha[:10]} {lines:3d} lines  {len(f2p):2d} f2p  {','.join(p for p, _ in src)}  | {subj[:70]}",
              flush=True)
    print(f"{found} candidates -> {out}")


if __name__ == "__main__":
    main()
