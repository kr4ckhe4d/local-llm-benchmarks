#!/usr/bin/env python3
"""Strata opt-in settings against setup's defaults, on this box's production
config: Qwen3.8-Flash-Next IQ3_XXS, R9700 + 9070 XT (auto layer split),
200K context, int8 KV, resident low-RAM mode. See README.md beside this file.

Per arm, a fresh server (so nothing is cached between arms):
  prefill  one cold ~20K-token prompt, the size of Claude Code's first turn
  decode   6 fresh prompts (3 code, 3 prose), 1,000 tokens max, temperature 0,
           thinking off; tok/s = all generated tokens / all generation time
The baseline runs first and last, to show drift.

    python sweep.py [arm ...]        (default: every arm)
"""
import json, os, re, signal, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
STRATA = Path.home() / "code/Strata"
BASE_CFG = STRATA / "strata-iq3_xxs.json"
WORK = Path("/mnt/fast/strata-exp/tuning")
PORT = 8097
PROMPTS = json.loads((REPO / "benchmarks/strata-expert-modes/prompts.json").read_text())
DECODE = PROMPTS["code"]["test"][:3] + PROMPTS["writing"]["test"][:3]

# ~20K tokens of this repo's own prose, fixed across arms
_doc = ((REPO / "README.md").read_text() + (REPO / "r9700+rx9070.md").read_text())[:76000]
LONG = _doc + "\n\nSummarise the document above in three bullet points."


def arm_config(name, args=(), env=None, split=None, replace=None):
    c = json.loads(BASE_CFG.read_text())
    for k in ("before_load", "idle_unload_s", "lazy_load", "api_key"):
        c.pop(k, None)
    c.update(host="127.0.0.1", port=PORT, log=str(WORK / f"{name}.log"))
    a = list(c["args"])
    for flag, value in (replace or {}).items():
        a[a.index(flag) + 1] = value
    c["args"] = a + list(args)
    if env:
        c["env"] = {**c.get("env", {}), **env}
    if split:
        c["layer_split"] = split
    p = WORK / f"{name}.json"
    p.write_text(json.dumps(c, indent=2))
    return p


ARMS = {
    "base":         {},
    "adapt-async":  {"args": ["--adapt-async", "1"]},
    "pipeline-w2":  {"args": ["--pipeline-windows", "2"]},
    "split-own":    {"env": {"STRATA_SPLIT_OWN": "1"}},
    "stage-trim":   {"env": {"STRATA_STAGE_TRIM": "1"}, "split": "33"},   # needs explicit split points
    "spec3":        {"replace": {"--spec": "3"}},
    "spec5":        {"replace": {"--spec": "5"}},
    "spec6":        {"replace": {"--spec": "6"}},
    "base-again":   {},
    # the two winners together, then with a longer draft
    "pw2+trim":       {"args": ["--pipeline-windows", "2"], "env": {"STRATA_STAGE_TRIM": "1"}, "split": "33"},
    "pw2+trim+spec5": {"args": ["--pipeline-windows", "2"], "env": {"STRATA_STAGE_TRIM": "1"}, "split": "33",
                       "replace": {"--spec": "5"}},
}


def health():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=3) as r:
            return json.load(r)
    except OSError:
        return None


def serve(cfg):
    out = open(WORK / (cfg.stem + ".out"), "w")
    p = subprocess.Popen([str(STRATA / ".venv/bin/python"), str(STRATA / "serve/server.py"), "--engine", "strata",
                          "--config", str(cfg), "--port", str(PORT)],
                         cwd=STRATA, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(200):
        h = health()
        if h and h.get("loaded"):
            return p
        if p.poll() is not None:
            raise RuntimeError(f"server exited, see {out.name}")
        time.sleep(3)
    raise RuntimeError("server did not load")


def stop(p):
    os.killpg(p.pid, signal.SIGTERM)
    try:
        p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
    for _ in range(30):
        if subprocess.run(["pgrep", "-f", "engine/strata --serve"], capture_output=True).returncode:
            return
        time.sleep(2)


def ask(prompt, max_tokens):
    body = json.dumps({"model": "x", "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
                       "temperature": 0, "reasoning_effort": "none"}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)


RE_REQ = re.compile(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms .*?(\d+) generated in (\d+) ms")
RE_HIT = re.compile(r"decode expert cache hit rate: ([\d.]+)%")
RE_SPLIT = re.compile(r"caches hold (\d+) of (\d+) profiled pairs")


def measure(log, prompt, max_tokens):
    start = log.stat().st_size
    ask(prompt, max_tokens)
    time.sleep(0.5)
    text = log.read_text()[start:]
    m, h = RE_REQ.search(text), RE_HIT.search(text)
    return {"prompt": int(m[1]), "read": int(m[3]), "read_ms": int(m[4]), "gen": int(m[5]), "gen_ms": int(m[6]),
            "hit": float(h[1]) if h else None}


def run_arm(name, spec):
    cfg = arm_config(name, spec.get("args", ()), spec.get("env"), spec.get("split"), spec.get("replace"))
    log = WORK / f"{name}.log"
    log.unlink(missing_ok=True)
    t0 = time.time()
    p = serve(cfg)
    load_s = time.time() - t0
    try:
        ask("Say OK.", 16)
        pre = measure(log, LONG, 64)
        dec = [measure(log, q, 1000) for q in DECODE]
    finally:
        stop(p)
    split = RE_SPLIT.findall(log.read_text())
    r = {"load_s": round(load_s, 1),
         "prefill_tok_s": round(pre["read"] / (pre["read_ms"] / 1000), 1), "prefill_tokens": pre["read"],
         "decode_tok_s": round(sum(d["gen"] for d in dec) / (sum(d["gen_ms"] for d in dec) / 1000), 1),
         "decode_per_prompt": [round(d["gen"] / (d["gen_ms"] / 1000), 1) for d in dec],
         "hit": [d["hit"] for d in dec], "cached_pairs": split[-1][0] if split else None}
    return r


if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or list(ARMS)
    out_path = HERE / "results.json"
    results = json.loads(out_path.read_text()) if out_path.exists() else {}
    for n in names:
        try:
            results[n] = run_arm(n, ARMS[n])
        except Exception as e:
            results[n] = {"error": str(e)}
        out_path.write_text(json.dumps(results, indent=1))
        r = results[n]
        print(n, "ERROR " + r["error"] if "error" in r else
              f"prefill {r['prefill_tok_s']} tok/s ({r['prefill_tokens']} tok)  decode {r['decode_tok_s']} tok/s "
              f"{r['decode_per_prompt']}  pairs {r['cached_pairs']}  load {r['load_s']}s", flush=True)
