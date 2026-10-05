#!/usr/bin/env python3
"""For every MoE preset with n-cpu-moe: find the least CPU offload that fits
both cards with MARGIN MiB free on the tightest one, then probe old vs new.

Old = the preset exactly as written (it auto-splits across both cards today).
New = the same flags with the smallest n-cpu-moe that fits, ideally none.

  python3 moe_sweep.py <out.txt> [preset ...]
  DIO=1 python3 moe_sweep.py <out.txt> [preset ...]   # load with --load-mode dio
  PRESETS=/tmp/old.ini python3 moe_sweep.py ...       # sweep another preset file
  LOGDIR=logs python3 moe_sweep.py ...                # keep llama-server logs there

PRESETS was added after the run, for reproducing the "as written" column
without touching the live file the router reads:
  git show 4c4b695:models-preset.ini > /tmp/old.ini

Run 2026-10-05 against models-preset.ini as of 4c4b695. Presets named as
separate argv entries -- under zsh, expand a list with ${=names}, or it arrives
as one argument that matches nothing and the sweep exits silently.
"""
import json, os, re, subprocess, sys, time, urllib.request

REPO = "/home/nipuna/code/local-llm-benchmarks"
BIN = "/home/nipuna/llama.cpp/build/bin/llama-server"
MARGIN = int(os.environ.get("MARGIN", 1024))
PRESETS = os.environ.get("PRESETS", f"{REPO}/models-preset.ini")
LOGDIR = os.environ.get("LOGDIR", "/tmp/claude-1000")
OUT = sys.argv[1]
ONLY = sys.argv[2:]  # optional preset names

SKIP_KEYS = {"alias", "model", "ctx-size", "load-on-startup", "n-gpu-layers", "parallel", "version"}
PROMPT = ("Write a complete Python implementation of a thread-safe LRU cache class with get, put, "
          "and delete methods, full docstrings, and type hints. Then write pytest unit tests for it. "
          "Output only code.")


def presets():
    cur, out = None, []
    for raw in open(PRESETS):
        line = raw.split(";")[0].strip()
        if not line:
            continue
        m = re.match(r"\[(.+)\]", line)
        if m:
            cur = {"name": m.group(1), "kv": []}
            out.append(cur)
            continue
        if "=" in line and cur is not None:
            k, v = [x.strip() for x in line.split("=", 1)]
            cur[k] = v
            cur["kv"].append((k, v))
    return [p for p in out if "n-cpu-moe" in p]


def flags(p, ncmoe):
    f = []
    for k, v in p["kv"]:
        if k in SKIP_KEYS or k == "n-cpu-moe":
            continue
        f += [f"--{k}", v]
    if ncmoe:
        f += ["--n-cpu-moe", str(ncmoe)]
    # DirectIO, added after Laguna Q8 (35.6 GB) timed out loading through mmap
    # on 32 GB of RAM. Applied to old and new alike so both load the same way.
    if os.environ.get("DIO"):
        f += ["--load-mode", "dio"]
    return f


def log(msg):
    print(msg, flush=True)
    with open(OUT, "a") as fh:
        fh.write(msg + "\n")


def fit(p, ncmoe):
    env = dict(os.environ, MODEL=os.path.relpath(p["model"], "/home/nipuna/llama.cpp/models"))
    r = subprocess.run([f"{REPO}/benchmarks/fit.sh", p["ctx-size"], *flags(p, ncmoe)],
                       env=env, capture_output=True, text=True, timeout=900)
    text = (r.stdout + r.stderr).strip()
    m = re.search(r"tightest: (\S+) (-?\d+) free", text)
    ok = r.returncode == 0 and m is not None and int(m.group(2)) >= MARGIN
    first = text.splitlines()[0] if text else "(no output)"
    return ok, text, first


def wait_idle():
    for _ in range(90):
        r = subprocess.run(["bash", "-c", f". {REPO}/benchmarks/gpu-mem.sh; vram_idle 900"])
        if r.returncode == 0:
            return
        time.sleep(1)


def probe(p, ncmoe):
    wait_idle()
    logf = open(f"{LOGDIR}/sweep-{p['name']}-{ncmoe}.log", "w")
    proc = subprocess.Popen([BIN, "-m", p["model"], "-ngl", "99", "-np", "1", "-c", p["ctx-size"],
                             *flags(p, ncmoe), "--host", "127.0.0.1", "--port", "8099"],
                            stdout=logf, stderr=subprocess.STDOUT)
    try:
        for _ in range(600):
            if proc.poll() is not None:
                return None
            try:
                if b"ok" in urllib.request.urlopen("http://127.0.0.1:8099/health", timeout=2).read():
                    break
            except Exception:
                pass
            time.sleep(1)
        runs = []
        body = json.dumps({"messages": [{"role": "user", "content": PROMPT}], "max_tokens": 700,
                           "temperature": 0.0, "chat_template_kwargs": {"enable_thinking": False}}).encode()
        for _ in range(3):
            req = urllib.request.Request("http://127.0.0.1:8099/v1/chat/completions", data=body,
                                         headers={"Content-Type": "application/json"})
            t = json.load(urllib.request.urlopen(req, timeout=900))["timings"]
            runs.append((t["prompt_per_second"], t["predicted_per_second"], t["predicted_n"]))
        return runs
    finally:
        proc.terminate()
        try:
            proc.wait(30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def fmt(runs):
    if not runs:
        return "LOAD FAILED"
    tg = sorted(r[1] for r in runs)[1]
    pp = sum(r[0] for r in runs[1:]) / 2  # run 1 includes the cold prompt
    return f"tg {tg:6.2f} (runs {', '.join(f'{r[1]:.2f}' for r in runs)}) | pp warm {pp:6.1f} | n {runs[0][2]}"


for p in presets():
    if ONLY and p["name"] not in ONLY:
        continue
    old = int(p["n-cpu-moe"])
    log(f"\n######## {p['name']}  (ctx {p['ctx-size']}, preset n-cpu-moe {old})")
    chosen = None
    candidates = [0] + list(range(2, old, 2))
    for n in candidates:
        ok, text, first = fit(p, n)
        log(f"  fit ncmoe={n:<2} {'OK  ' if ok else 'NO  '} {first}")
        for extra in text.splitlines()[1:]:
            if "per-card" in extra or "FAIL" in extra or "SPILL" in extra or "ABORT" in extra:
                log(f"      {extra.strip()}")
        if ok:
            chosen = n
            break
    if chosen is None:
        log("  -> nothing below the preset value fits with margin; leaving it")
        continue
    log(f"  -> new n-cpu-moe {chosen}")
    log(f"  probe old (ncmoe {old}): {fmt(probe(p, old))}")
    log(f"  probe new (ncmoe {chosen}): {fmt(probe(p, chosen))}")
