#!/usr/bin/env python3
"""Expert "modes" on Strata: does a cache seeded from a domain's own routing beat
one seeded from another domain's, on a card that cannot hold every expert?

Qwen3.8-Flash-Next IQ3_XXS, 32K context, 30 GB of RAM. Routing is traced on both
cards (where experts sit does not change which ones the router picks); the
eval runs on the R9700 alone, which holds a bit under half the 24,576 expert
pairs. The 9070 XT alone (16 GB, ~24%) stalled in the CPU pool under RAM
pressure (22 GB of experts resident in 30 GB) and was dropped.

  1. trace: per domain, serve the TRAIN prompts with --dump-routing (both cards)
  2. build: tools/make_profile.py TRACE --no-base -> one profile per domain
  3. eval:  per profile, serve every TEST prompt with static residency
     (--adapt-every 100000, so the seed alone decides what is in VRAM) and read
     the per-request hit rate and speed from the engine log

    python run.py [trace] [build] [eval]     (default: all three)
"""
import json, os, re, signal, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STRATA = Path.home() / "code/Strata"
WORK = Path("/mnt/fast/strata-exp")
BASE_CFG = STRATA / "strata-iq3_xxs.json"
PORT = 8097
MAX_TOKENS = 400
PROMPTS = json.loads((HERE / "prompts.json").read_text())
DOMAINS = list(PROMPTS)


def config(name, extra_args, profile=None, gpu=(1,)):
    c = json.loads(BASE_CFG.read_text())
    for k in ("before_load", "idle_unload_s", "lazy_load", "api_key", "gpus_asked"):
        c.pop(k, None)
    if len(gpu) == 1:
        c.pop("layer_split", None)
    c.update(host="127.0.0.1", port=PORT, gpu=list(gpu), log=str(WORK / f"{name}.log"))
    a = c["args"]
    a[a.index("--max-context") + 1] = "32768"
    if profile:
        a[a.index("--expert-profile") + 1] = str(profile)
    c["args"] = a + extra_args
    p = WORK / f"{name}.json"
    p.write_text(json.dumps(c, indent=2))
    return p


def health():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=3) as r:
            return json.load(r)
    except OSError:
        return None


def serve(cfg_path):
    log = open(WORK / (cfg_path.stem + ".out"), "w")
    p = subprocess.Popen([str(STRATA / ".venv/bin/python"), str(STRATA / "serve/server.py"), "--engine", "strata",
                          "--config", str(cfg_path), "--port", str(PORT)],
                         cwd=STRATA, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(200):
        h = health()
        if h and h.get("loaded"):
            return p
        if p.poll() is not None:
            raise SystemExit(f"server exited, see {log.name}")
        time.sleep(3)
    raise SystemExit("server did not load")


def stop(p):
    os.killpg(p.pid, signal.SIGTERM)
    try:
        p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
    for _ in range(30):                      # the engine is a child; wait until it has freed the card
        if subprocess.run(["pgrep", "-f", "engine/strata --serve"], capture_output=True).returncode:
            return
        time.sleep(2)


def ask(prompt):
    body = json.dumps({"model": "x", "messages": [{"role": "user", "content": prompt}], "max_tokens": MAX_TOKENS,
                       "temperature": 0, "reasoning_effort": "none"}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)


RE_REQ = re.compile(r"prompt (\d+) tokens = .*?read in (\d+) ms .*?(\d+) generated in (\d+) ms \(([\d.]+) tok/s\)")
RE_HIT = re.compile(r"decode expert cache hit rate: ([\d.]+)% \((\d+) hits / (\d+) lookups\)")
RE_IO = re.compile(r"file tier I/O this request: the OS read ([\d.]+) MB")


def measure(log_path, prompt):
    start = log_path.stat().st_size
    ask(prompt)
    time.sleep(0.5)
    with open(log_path) as f:
        f.seek(start)
        text = f.read()
    m, h, io = RE_REQ.search(text), RE_HIT.search(text), RE_IO.search(text)
    return {"prompt_tokens": int(m[1]), "gen_tokens": int(m[3]), "gen_ms": int(m[4]), "tok_s": float(m[5]),
            "hits": int(h[2]), "lookups": int(h[3]), "ssd_mb": float(io[1]) if io else 0.0}


def trace():
    for d in DOMAINS:
        out = WORK / f"trace-{d}.bin"
        out.unlink(missing_ok=True)
        p = serve(config(f"trace-{d}", ["--dump-routing", str(out)], gpu=(1, 0)))
        try:
            for q in PROMPTS[d]["train"]:
                ask(q)
        finally:
            stop(p)
        print(f"trace {d}: {out.stat().st_size / 1e6:.1f} MB", flush=True)


def build():
    for d in DOMAINS:
        subprocess.run([sys.executable, str(STRATA / "tools/make_profile.py"), str(WORK / f"trace-{d}.bin"),
                        "--no-base", "--out", str(HERE / f"profile-{d}.bin")], check=True)


def evaluate():
    arms = {"shipped": STRATA / "data/expert-profile.bin"} | {d: HERE / f"profile-{d}.bin" for d in DOMAINS}
    results = {}
    for arm, prof in arms.items():
        cfg = config(f"eval-{arm}", ["--adapt-every", "100000"], profile=prof)
        p = serve(cfg)
        log = WORK / f"eval-{arm}.log"
        try:
            ask("Say OK.")                   # warm-up, not counted
            results[arm] = {d: [measure(log, q) for q in PROMPTS[d]["test"]] for d in DOMAINS}
        finally:
            stop(p)
        (HERE / "results.json").write_text(json.dumps(results, indent=1))
        for d in DOMAINS:
            r = results[arm][d]
            hit = sum(x["hits"] for x in r) / sum(x["lookups"] for x in r)
            tps = sum(x["gen_tokens"] for x in r) / (sum(x["gen_ms"] for x in r) / 1000)
            print(f"eval {arm:8s} on {d:8s}: hit {hit:6.1%}  {tps:5.1f} tok/s", flush=True)


def adapt():
    """Reactive switching: Strata's default adaptive tier on. Start from one domain's profile, then serve the
    other domain's test prompts, then the first's again, and read how fast the hit rate follows."""
    runs = {"code-then-writing": ("code", ["writing", "code"]), "writing-then-code": ("writing", ["code", "writing"])}
    results = {}
    for name, (start, seq) in runs.items():
        p = serve(config(f"adapt-{name}", [], profile=HERE / f"profile-{start}.bin"))
        log = WORK / f"adapt-{name}.log"
        try:
            ask("Say OK.")
            results[name] = [{"domain": d, **measure(log, q)} for d in seq for q in PROMPTS[d]["test"]]
        finally:
            stop(p)
        (HERE / "results-adapt.json").write_text(json.dumps(results, indent=1))
        print(name, " ".join(f"{x['domain'][0]}:{x['hits'] / x['lookups']:.0%}/{x['tok_s']:.0f}" for x in results[name]),
              flush=True)


if __name__ == "__main__":
    WORK.mkdir(exist_ok=True)
    steps = sys.argv[1:] or ["trace", "build", "eval"]
    for s in steps:
        {"trace": trace, "build": build, "eval": evaluate, "adapt": adapt}[s]()
