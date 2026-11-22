#!/usr/bin/env python3
"""Agentic coding eval: real-shaped tasks in a sandboxed repo, graded by hidden tests.

code-quality-test.py asks for one function in one shot. This asks a model to do what a
coding agent is used for: read an unfamiliar repo, reproduce a reported bug, change
several files, run the tests, and say when it is done. Each task is a small repo under
tasks/<id>/repo, an issue-style prompt, and hidden checks the model never sees.

The agent loop is deliberately small and identical for every model, so a difference in
score belongs to the model and not to a client: native OpenAI tool calls (llama.cpp's
parser), five tools, a turn limit. Shell commands run under bubblewrap with no network,
no home directory, and only the task's working copy writable.

Per run it records:
  pass         hidden checks pass (and, where the prompt forbids it -- tests_frozen -- no
               visible test was changed; elsewhere adding or fixing tests is allowed)
  claimed      the model called finish(status="done")
  false_claim  claimed done but the hidden checks fail: the Nemotron failure from
               real-world-testing.md, counted instead of noticed
  turns, tool calls, prompt/completion tokens, wall time, malformed tool calls

    ./agent_eval.py validate                      # every task: pristine fails, reference passes
    ./agent_eval.py run --model huihui-qwen3.8-128k --label huihui-q6 --repeats 3
    ./agent_eval.py run --host http://127.0.0.1:8099 --label x --tasks csv-quoted-fields
"""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile, time, tomllib
import urllib.error, urllib.request
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
TASKS = HERE / "tasks"
RESULTS = HERE / "results"
VENV = HERE / ".venv"          # python + pytest for the sandbox; created by setup (see README)
OUT_CAP = 12000                # chars of tool output returned to the model
CMD_TIMEOUT = 120              # seconds per shell command
CHECK_TIMEOUT = 300

SYSTEM = """You are an autonomous coding agent. The repository is checked out at /work (a git \
repo; your working directory). Use the tools to inspect files, run commands and edit code. \
Python is available as `python`, and pytest as `python -m pytest`. There is no network access.

Work like a careful engineer: read the relevant code, reproduce the problem, make the fix, \
and run the tests before you finish. Keep changes focused on the task. Do not edit existing \
tests unless the task asks you to; you may add new tests.

When you are finished, call `finish` exactly once. Use status "done" only if you believe the \
task is complete and verified; use "cannot" if you could not complete it, and say why."""

TOOLS = [
    {"type": "function", "function": {
        "name": "bash", "description": "Run a shell command in /work and return its stdout, stderr and exit code. "
        "Commands time out after 120 s. No network.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a text file (path relative to /work). Returns numbered lines.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer", "description": "1-based first line (default 1)"},
            "limit": {"type": "integer", "description": "max lines (default 400)"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "Create or overwrite a file (path relative to /work) with the given content.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "edit_file", "description": "Replace one exact occurrence of old_str with new_str in a file. "
        "old_str must match the file exactly (including indentation) and occur exactly once.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old_str": {"type": "string"}, "new_str": {"type": "string"}},
            "required": ["path", "old_str", "new_str"]}}},
    {"type": "function", "function": {
        "name": "finish", "description": "End the task. status is \"done\" or \"cannot\".",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["done", "cannot"]},
            "summary": {"type": "string", "description": "What you changed and how you verified it, or why you could not."}},
            "required": ["status", "summary"]}}},
]


# ------------------------------------------------------------------ sandbox
def sandbox(ws, command, timeout=CMD_TIMEOUT):
    """Run `command` with bash in a bubblewrap jail: /usr and /etc read-only, the venv
    read-only at its own path (its scripts hardcode it), /work = ws read-write, no network,
    no /home, fresh /tmp, separate pid namespace."""
    args = ["bwrap", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/bin", "/sbin", "--ro-bind", "/etc", "/etc",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--ro-bind", str(VENV), str(VENV),
            "--bind", str(ws), "/work", "--chdir", "/work", "--unshare-all", "--die-with-parent", "--new-session",
            "--clearenv", "--setenv", "HOME", "/work", "--setenv", "PATH", f"{VENV}/bin:/usr/bin",
            "--setenv", "LANG", "C.UTF-8", "--setenv", "TERM", "dumb", "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            # upstream repos run with filterwarnings=error; a newer pytest than their CI must not
            # turn its own deprecation notices about their test files into collection errors
            "--setenv", "PYTEST_ADDOPTS", "-W ignore::pytest.PytestRemovedIn10Warning",
            "--setenv", "GIT_AUTHOR_NAME", "agent", "--setenv", "GIT_AUTHOR_EMAIL", "agent@localhost",
            "--setenv", "GIT_COMMITTER_NAME", "agent", "--setenv", "GIT_COMMITTER_EMAIL", "agent@localhost",
            "bash", "-c", command]
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace")
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or b"").decode(errors="replace"), (e.stderr or b"").decode(errors="replace") + \
            f"\n[timed out after {timeout} s]"


def cap(s, n=OUT_CAP):
    if len(s) <= n:
        return s
    head = n // 3
    return s[:head] + f"\n... [{len(s) - n} chars omitted] ...\n" + s[-(n - head):]


def inside(ws, rel):
    """Map a model-supplied path ('src/x.py', './x', '/work/x') into ws; refuse anything that
    resolves outside it, symlinks included."""
    rel = rel.strip()
    if rel == "/work" or rel.startswith("/work/"):
        rel = rel[len("/work"):]
    p = (ws / rel.lstrip("/")).resolve()
    if not p.is_relative_to(ws.resolve()):
        raise ValueError(f"path {rel!r} is outside /work")
    return p


def run_tool(ws, name, a):
    if name == "bash":
        code, out, err = sandbox(ws, a["command"])
        body = out + (("\n[stderr]\n" + err) if err.strip() else "")
        return cap(body) + f"\n[exit code {code}]"
    if name == "read_file":
        p = inside(ws, a["path"])
        if not p.is_file():
            return f"error: {a['path']} is not a file"
        lines = p.read_text(errors="replace").splitlines()
        off = max(1, int(a.get("offset") or 1)); lim = max(1, int(a.get("limit") or 400))
        sel = lines[off - 1: off - 1 + lim]
        more = f"\n[{len(lines) - (off - 1 + len(sel))} more lines]" if off - 1 + len(sel) < len(lines) else ""
        return cap("\n".join(f"{i:5}\t{l}" for i, l in enumerate(sel, off)) + more)
    if name == "write_file":
        p = inside(ws, a["path"]); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(a["content"])
        return f"wrote {a['path']} ({len(a['content'])} chars)"
    if name == "edit_file":
        p = inside(ws, a["path"])
        if not p.is_file():
            return f"error: {a['path']} is not a file"
        t = p.read_text(); n = t.count(a["old_str"])
        if n != 1:
            return f"error: old_str occurs {n} times in {a['path']}; it must occur exactly once"
        p.write_text(t.replace(a["old_str"], a["new_str"], 1))
        return f"edited {a['path']}"
    return f"error: unknown tool {name}"


# ------------------------------------------------------------------ tasks
def load_task(tid):
    d = TASKS / tid
    t = tomllib.loads((d / "task.toml").read_text())
    t["id"], t["dir"] = tid, d
    t.setdefault("max_turns", 40)
    t.setdefault("protected", [])
    t.setdefault("tests_frozen", False)  # only when the prompt itself says not to touch the tests
    t.setdefault("check", "python -m pytest -q -p no:cacheprovider .hidden_check")
    return t


def all_tasks():
    return sorted(p.name for p in TASKS.iterdir() if (p / "task.toml").exists())


CACHE = HERE / ".cache"        # upstream clones for real-repo tasks (mine_real.py fills it)


def upstream_snapshot(url, commit, dest):
    """Export `commit` of an upstream repo (cached clone) into dest, without its git history:
    the fix the task is built from is a later commit, and `git log` must not reveal it."""
    name = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    clone = CACHE / name
    if not clone.exists():
        CACHE.mkdir(exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", url, str(clone)], check=True)
    dest.mkdir(parents=True)
    arc = subprocess.run(["git", "-C", str(clone), "archive", commit], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=arc, check=True)
    return name


def fresh_workspace(task, root):
    ws = pathlib.Path(root) / "work"
    if "upstream" in task:
        upstream_snapshot(task["upstream"], task["commit"], ws)
    else:
        shutil.copytree(task["dir"] / "repo", ws)
    g = ["git", "-C", str(ws), "-c", "user.name=agent", "-c", "user.email=agent@localhost"]
    subprocess.run(g + ["init", "-q", "-b", "main"], check=True)
    subprocess.run(g + ["add", "-A"], check=True)
    subprocess.run(g + ["commit", "-q", "-m", "initial"], check=True)
    return ws


def digest(ws, rels):
    out = {}
    for r in rels:
        p = ws / r
        out[r] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    return out


def grade(task, ws, before):
    """Copy the hidden checks in only now, run them in the sandbox, and check protected files."""
    changed = [r for r, h in digest(ws, task["protected"]).items() if h != before[r]]
    hc = ws / ".hidden_check"
    if task.get("overlay"):
        # real-repo tasks: the upstream test tree is restored (edits to any test cannot hide a
        # regression), then hidden/ -- the fix commit's test files, at their repo paths -- goes on top
        if "upstream" in task:
            for d in task.get("restore", ["tests"]):
                shutil.rmtree(ws / d, ignore_errors=True)
            with tempfile.TemporaryDirectory() as t:
                upstream_snapshot(task["upstream"], task["commit"], pathlib.Path(t) / "u")
                for d in task.get("restore", ["tests"]):
                    shutil.copytree(pathlib.Path(t) / "u" / d, ws / d)
        shutil.copytree(task["dir"] / "hidden", ws, dirs_exist_ok=True)
    else:
        if hc.exists():
            shutil.rmtree(hc)
        shutil.copytree(task["dir"] / "hidden", hc)
    code, out, err = sandbox(ws, task["check"], timeout=CHECK_TIMEOUT)
    shutil.rmtree(hc, ignore_errors=True)
    tail = (out + err).strip().splitlines()[-15:]
    return {"pass": passes(task, code, changed), "check_exit": code, "protected_changed": changed,
            "check_tail": "\n".join(tail)}


def passes(task, check_exit, changed):
    """Hidden checks decide. Editing a visible test fails a run only when the prompt forbade it:
    the hidden checks are separate files, so a model adding regression tests cannot game them."""
    return check_exit == 0 and not (changed and task["tests_frozen"])


# ------------------------------------------------------------------ model
def chat(host, model, messages, think, timeout=1800):
    body = {"messages": messages, "tools": TOOLS, "tool_choice": "auto", "max_tokens": 12288,
            "chat_template_kwargs": {"enable_thinking": think}}
    if model:
        body["model"] = model
    req = urllib.request.Request(host + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def run_one(task, host, model, think, log):
    with tempfile.TemporaryDirectory(prefix=f"agent-eval-{task['id']}-") as root:
        ws = fresh_workspace(task, root)
        before = digest(ws, task["protected"])
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task["prompt"].strip()}]
        m = {"task": task["id"], "turns": 0, "tool_calls": 0, "bad_calls": 0, "prompt_tokens": 0,
             "completion_tokens": 0, "max_prompt": 0, "finish": None, "summary": None, "end": None}
        t0 = time.time(); nudged = False
        while m["turns"] < task["max_turns"]:
            m["turns"] += 1
            try:
                r = chat(host, model, msgs, think)
            except urllib.error.HTTPError as e:
                m["end"] = f"http {e.code}: {e.read()[:300].decode(errors='replace')}"; break
            except Exception as e:  # noqa: BLE001 -- a dead server ends the run, recorded
                m["end"] = f"error: {e}"; break
            u = r.get("usage") or {}
            m["prompt_tokens"] += u.get("prompt_tokens", 0); m["completion_tokens"] += u.get("completion_tokens", 0)
            m["max_prompt"] = max(m["max_prompt"], u.get("prompt_tokens", 0))
            msg = r["choices"][0]["message"]
            calls = msg.get("tool_calls") or []
            log.append({"turn": m["turns"], "content": msg.get("content"), "reasoning": msg.get("reasoning_content"),
                        "tool_calls": calls, "finish_reason": r["choices"][0].get("finish_reason")})
            if not calls:
                if nudged:
                    m["end"] = "stopped without finish"; break
                nudged = True
                msgs.append({"role": "assistant", "content": msg.get("content") or ""})
                msgs.append({"role": "user", "content": "Continue working with the tools. When you are done, call finish."})
                continue
            msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for c in calls:
                m["tool_calls"] += 1
                name = c["function"]["name"]
                try:
                    a = json.loads(c["function"].get("arguments") or "{}")
                    if name == "finish":
                        m["finish"], m["summary"] = a.get("status"), a.get("summary")
                        res = "ok"
                    else:
                        res = run_tool(ws, name, a)
                except Exception as e:  # noqa: BLE001 -- malformed calls are the model's error, returned to it
                    m["bad_calls"] += 1; res = f"error: {type(e).__name__}: {e}"
                log.append({"tool": name, "result": res[:4000]})
                msgs.append({"role": "tool", "tool_call_id": c.get("id", ""), "name": name, "content": res})
            if m["finish"]:
                m["end"] = "finish"; break
        else:
            m["end"] = "turn limit"
        m["wall_s"] = round(time.time() - t0, 1)
        m.update(grade(task, ws, before))
        m["claimed"] = m["finish"] == "done"
        m["false_claim"] = m["claimed"] and not m["pass"]
        diff = subprocess.run(["git", "-C", str(ws), "diff", "--stat"], capture_output=True, text=True).stdout
        m["diffstat"] = diff.strip().splitlines()[-1] if diff.strip() else "no changes"
        return m


# ------------------------------------------------------------------ commands
def cmd_validate(a):
    ok = True
    for tid in a.tasks or all_tasks():
        t = load_task(tid)
        with tempfile.TemporaryDirectory() as root:
            ws = fresh_workspace(t, root); before = digest(ws, t["protected"])
            vis = sandbox(ws, "python -m pytest -q -p no:cacheprovider")[0]
            pristine = grade(t, ws, before)
            shutil.copytree(t["dir"] / "reference", ws, dirs_exist_ok=True)
            ref = grade(t, ws, before)
        good = not pristine["pass"] and ref["pass"]
        ok &= good
        print(f"{'OK ' if good else 'BAD'} {tid:28} visible tests exit {vis} | pristine "
              f"{'PASS' if pristine['pass'] else 'fail'} | reference {'PASS' if ref['pass'] else 'fail'}")
        if not ref["pass"]:
            print("    " + ref["check_tail"].replace("\n", "\n    "))
    sys.exit(0 if ok else 1)


def server_info(host):
    try:
        with urllib.request.urlopen(host + "/props", timeout=10) as r:
            p = json.loads(r.read())
        return {"build": p.get("build_info"), "model_path": p.get("model_path"),
                "ctx": (p.get("default_generation_settings") or {}).get("n_ctx")}
    except Exception:  # noqa: BLE001 -- the router has no /props; the header just says so
        return {}


def cmd_run(a):
    tasks = a.tasks or all_tasks()
    out = RESULTS / a.label
    (out / "runs").mkdir(parents=True, exist_ok=True)
    rows = []
    for rep in range(1, a.repeats + 1):
        for tid in tasks:
            t = load_task(tid); log = []
            m = run_one(t, a.host, a.model, a.think, log)
            m["repeat"] = rep
            rows.append(m)
            (out / "runs" / f"{tid}-r{rep}.json").write_text(json.dumps({"metrics": m, "log": log}, indent=1))
            with open(out / "results.jsonl", "a") as f:
                f.write(json.dumps(m) + "\n")
            print(f"r{rep} {tid:28} {'PASS' if m['pass'] else 'fail'} | finish={m['finish']} end={m['end']} "
                  f"turns={m['turns']} calls={m['tool_calls']} bad={m['bad_calls']} {m['wall_s']}s "
                  f"| {m['diffstat']}{' | FALSE CLAIM' if m['false_claim'] else ''}", flush=True)
    info = server_info(a.host)
    head = [f"# agent-eval -- agentic coding tasks, hidden tests, sandboxed tool loop, thinking {'on' if a.think else 'off'}",
            f"# model : {a.model or info.get('model_path') or '?'}",
            f"# ctx   : {info.get('ctx') or '?'}",
            f"# host  : {a.host} {info.get('build') or ''}".rstrip(),
            f"# date  : {datetime.now().isoformat(timespec='seconds')}",
            f"# repeats: {a.repeats}"]
    write_summary(a.label, out, rows, tasks, head)


def cmd_rescore(a):
    """Re-apply the current pass rule (passes()) to recorded runs, without rerunning anything."""
    for label in a.labels:
        out = RESULTS / label
        rows = [json.loads(l) for l in (out / "results.jsonl").read_text().splitlines() if l.strip()]
        flipped = 0
        for m in rows:
            t = load_task(m["task"])
            new = passes(t, m["check_exit"], m["protected_changed"])
            flipped += new != m["pass"]
            m["pass"] = new; m["false_claim"] = m["claimed"] and not new
            f = out / "runs" / f"{m['task']}-r{m['repeat']}.json"
            if f.exists():
                d = json.loads(f.read_text()); d["metrics"] = m; f.write_text(json.dumps(d, indent=1))
        (out / "results.jsonl").write_text("".join(json.dumps(m) + "\n" for m in rows))
        old = (out / "summary.txt").read_text().splitlines() if (out / "summary.txt").exists() else []
        head = [l for l in old if l.startswith("#")]
        tasks = list(dict.fromkeys(m["task"] for m in rows))
        print(f"{label}: {flipped} runs changed")
        write_summary(label, out, rows, sorted(tasks), head)


def write_summary(label, out, rows, tasks, head):
    by = {}
    for r in rows:
        by.setdefault(r["task"], []).append(r)
    n = len(rows); p = sum(r["pass"] for r in rows)
    lines = head + ["",
             f"{label}: {p}/{n} runs pass ({100 * p / n:.0f}%) | "
             f"{sum(all(x['pass'] for x in v) for v in by.values())}/{len(by)} tasks pass every run | "
             f"{sum(r['false_claim'] for r in rows)} false claims", ""]
    for tid in tasks:
        v = by.get(tid, [])
        lines.append(f"  {tid:28} {sum(x['pass'] for x in v)}/{len(v)}  "
                     f"turns {sum(x['turns'] for x in v) / len(v):5.1f}  "
                     f"wall {sum(x['wall_s'] for x in v) / len(v):6.0f}s  "
                     f"false claims {sum(x['false_claim'] for x in v)}  "
                     f"ends {','.join(sorted({x['end'] for x in v}))}")
    tok = sum(r["completion_tokens"] for r in rows)
    lines += ["", f"completion tokens {tok}, prompt tokens {sum(r['prompt_tokens'] for r in rows)}, "
                  f"max prompt {max(r['max_prompt'] for r in rows)}, wall {sum(r['wall_s'] for r in rows) / 60:.1f} min"]
    (out / "summary.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("--tasks", nargs="*")
    r = sub.add_parser("run")
    r.add_argument("--host", default="http://127.0.0.1:8090")
    r.add_argument("--model", help="router preset name (omit for a pinned server)")
    r.add_argument("--label", required=True, help="results/<label>/")
    r.add_argument("--repeats", type=int, default=1)
    r.add_argument("--think", action="store_true", help="enable_thinking (default off)")
    r.add_argument("--tasks", nargs="*")
    rs = sub.add_parser("rescore", help="re-apply the pass rule to recorded runs")
    rs.add_argument("labels", nargs="+")
    a = ap.parse_args()
    if a.cmd == "rescore":
        return cmd_rescore(a)
    if not VENV.exists():
        sys.exit(f"missing {VENV}: uv venv --python /usr/bin/python3 {VENV} && "
                 f"uv pip install --python {VENV}/bin/python pytest")
    cmd_validate(a) if a.cmd == "validate" else cmd_run(a)


if __name__ == "__main__":
    main()
