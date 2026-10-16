#!/usr/bin/env python3
"""Every [MEASURE] number for YouTube Ep 1 ("16 / 32 / 48"), in one session, same software.

Uses the repo's own tools, so each number has the same provenance as the rest
of the repo: fit.sh for memory, raw/r9700-two-cards/preset_probe.py for the
700-token probe (median of 3, temperature 0), depth_presets.sh for real 128K
depth. Card names, never indexes: llama.cpp ROCm0 = RX 9070 XT, ROCm1 = R9700.

    python3 ep1/run_ep1.py                 # refuses if the router or Strata is up
    python3 ep1/run_ep1.py --stop-servers  # stops both first (switch-model.sh router restarts them)
    python3 ep1/run_ep1.py --only gptoss,q38   # a subset: devices,gptoss,q36,q38,depth

Output: ep1/runs/<date>/ with one log per measurement and results.md holding
every cell the script's [MEASURE] tags ask for. Takes about 1-1.5 hours.
"""
import argparse, datetime, os, re, signal, subprocess, sys, time
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent
REPO = BENCH.parent
RAW = BENCH / "raw/r9700-two-cards"
LLAMA_BIN = Path.home() / "llama.cpp/build/bin/llama-server"
SWITCH = REPO / "switch-model.sh"
OUT = BENCH / "ep1/runs" / datetime.date.today().isoformat()
LOGS = OUT / "logs"

Q36 = "Qwen3.6-35B-A3B-UD-Q6_K.gguf"
Q36_FLAGS = ["--load-mode", "dio", "-ub", "1024", "-b", "2048", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0"]
Q36_LAYERS = 40
MARGIN = 1024        # MiB the 9070 XT must keep free for an offload count to count as a fit
results = {}         # key -> dict, written to results.md at the end


def log(msg):
    print(msg, flush=True)
    with open(OUT / "run.log", "a") as f:
        f.write(msg + "\n")


def pids(pattern):
    r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
    return [int(p) for p in r.stdout.split()]


def preflight(stop):
    router = subprocess.run(["pgrep", "-x", "llama-server"], capture_output=True).returncode == 0
    strata = pids("serve/server.py --engine strata")
    if not (router or strata):
        return
    if not stop:
        up = [n for n, on in (("the llama.cpp router", router), ("Strata", strata)) if on]
        sys.exit("ABORT: " + " and ".join(up) + (" are" if len(up) > 1 else " is") + " running. fit.sh only guards against llama-server; a Strata load takes ~47 GB across both"
                 " cards and silently ruins every number. Rerun with --stop-servers, or stop them yourself.")
    if router:
        log("stopping the router: switch-model.sh stop")
        subprocess.run([str(SWITCH), "stop"], check=False)
    for p in strata:
        log(f"stopping Strata (pid {p})")
        os.kill(p, signal.SIGTERM)
    for _ in range(60):
        if not pids("engine/strata --serve") and not pids("serve/server.py --engine strata"):
            break
        time.sleep(1)
    time.sleep(5)       # let VRAM settle; fit.sh also waits for two identical readings


def run(cmd, name, env=None, cwd=BENCH, timeout=3600):
    """Run a command, keep its full output in logs/<name>.txt, return (returncode, text)."""
    log(f"\n$ {' '.join(map(str, cmd))}")
    r = subprocess.run(list(map(str, cmd)), cwd=cwd, env={**os.environ, **(env or {})},
                       capture_output=True, text=True, timeout=timeout)
    text = (r.stdout + r.stderr).strip()
    (LOGS / f"{name}.txt").write_text(f"$ {' '.join(map(str, cmd))}\n{text}\n")
    for line in text.splitlines()[-4:]:
        log("  " + line[:200])
    return r.returncode, text


CARD_RE = re.compile(r"R9700 model=(\d+) peak=(\d+) free=(-?\d+)\s+9070XT model=(\d+) peak=(\d+) free=(-?\d+)")


def cards(text):
    m = CARD_RE.search(text)
    return None if not m else {"r9700_model": int(m[1]), "r9700_free": int(m[3]),
                               "xt_model": int(m[4]), "xt_free": int(m[6])}


def probe(key, preset, extra="", drop=""):
    """preset_probe.py with EXTRA appended: fit.sh line, per-card memory, tg median, MTP acceptance."""
    logdir = LOGS / key
    logdir.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{key}.txt"
    out.unlink(missing_ok=True)
    rc, text = run(["python3", RAW / "preset_probe.py", out, preset], key,
                   env={"LOGDIR": str(logdir), "EXTRA": extra, "DROP": drop}, cwd=RAW)
    body = out.read_text() if out.exists() else text
    fit = re.search(r"fit (OK|NO)\s+(.*)", body)
    tg = re.search(r"probe: tg\s+([\d.]+)", body)
    acc = []
    for f in logdir.glob("sweep-*.log"):
        acc += [float(a) for a in re.findall(r"draft acceptance = ([\d.]+)", f.read_text(errors="replace"))]
    r = {"preset": preset, "extra": extra, "fit": fit[1] if fit else "?", "fit_line": fit[2][:160] if fit else "",
         "tg": float(tg[1]) if tg else None, "load_failed": "LOAD FAILED" in body,
         "acceptance": sorted(acc)[len(acc) // 2] if acc else None, **(cards(body) or {})}
    results[key] = r
    log(f"  => {key}: fit {r['fit']}, tg {r['tg']}, accept {r['acceptance']}, "
        f"free R9700 {r.get('r9700_free')} / 9070 XT {r.get('xt_free')}")
    return r


def fit36(ctx, n, device="ROCm0"):
    rc, text = run([BENCH / "fit.sh", ctx, *Q36_FLAGS, "--device", device, "--n-cpu-moe", n],
                   f"q36-fit-{ctx}-{device}-ncmoe{n}", env={"MODEL": Q36})
    c = cards(text)
    ok = rc == 0 and c is not None and c["xt_free"] >= MARGIN
    return ok, (c or {}).get("xt_free"), text


def smallest_offload(ctx):
    """The smallest --n-cpu-moe that fits the 9070 XT alone with MARGIN free. N=0 is tried first on purpose:
    its failure is the '16GB wall' terminal moment."""
    ok0, free0, _ = fit36(ctx, 0)
    results[f"q36-{ctx}-rocm0-n0"] = {"ok": ok0, "xt_free": free0}
    if ok0:
        return 0
    lo, hi = 1, Q36_LAYERS
    if not fit36(ctx, hi)[0]:
        return None
    while lo < hi:                        # assumes more offload never fits worse
        mid = (lo + hi) // 2
        if fit36(ctx, mid)[0]:
            hi = mid
        else:
            lo = mid + 1
    ok, free, _ = fit36(ctx, lo)          # re-measure the answer so its log is the last one
    results[f"q36-{ctx}-n"] = {"n": lo, "xt_free": free}
    log(f"  => Qwen3.6 UD-Q6_K {ctx} on the 9070 XT alone: --n-cpu-moe {lo} ({free} MiB free)")
    return lo


def step_devices():
    run([LLAMA_BIN, "--list-devices"], "list-devices")


def step_gptoss():
    for key, extra in (("gptoss-rocm0", "--device ROCm0"), ("gptoss-rocm1", "--device ROCm1"),
                       ("gptoss-both", "--device ROCm0,ROCm1")):
        probe(key, "gpt-oss-20b-A3.6B-mxfp4-32k", extra)


def step_q36():
    for ctx, preset in (("32768", "qwen3.6-35B-A3B-q6-32k"), ("131072", "qwen3.6-35B-A3B-q6-128k")):
        tag = "32k" if ctx == "32768" else "128k"
        n = smallest_offload(ctx)
        if n is not None:
            probe(f"q36-{tag}-rocm0-offload", preset, f"--device ROCm0 --n-cpu-moe {n}")
            probe(f"q36-{tag}-both-offload", preset, f"--n-cpu-moe {n}")      # the twist: same offload, both cards
        probe(f"q36-{tag}-rocm1", preset, "--device ROCm1")                     # prediction: does not fit
        probe(f"q36-{tag}-both", preset, "")                                    # as written: no offload, auto split


def step_q38():
    p = "qwen3.8-27B-q6-128k"
    probe("q38-both-mtp", p, "")
    probe("q38-rocm1-mtp", p, "--device ROCm1")
    probe("q38-rocm1-nomtp", p, "--device ROCm1", drop="spec-type")    # removed: appending --spec-type none left MTP on
    probe("q38-rocm0-mtp", p, "--device ROCm0")                                 # 22 GB file on 16 GB: expect no fit


def step_depth():
    d = LOGS / "depth"
    d.mkdir(parents=True, exist_ok=True)
    rc, text = run([RAW / "depth_presets.sh", "qwen3.6-35B-A3B-q6-128k", "qwen3.8-27B-q6-128k"], "depth",
                   env={"LOGDIR": str(d)}, timeout=7200)
    for m in re.finditer(r"^(\S+)\s+prompt (\d+) tok @\s+([\d.]+) tok/s \| tg\s+([\d.]+) tok/s.*?(?:draft ([\d.]+)%)?$",
                         text, re.M):
        results[f"depth-{m[1]}"] = {"prompt": int(m[2]), "prefill": float(m[3]), "tg": float(m[4]),
                                    "draft": float(m[5]) if m[5] else None}


def cell(key, field="tg", fmt="{:.2f}"):
    r = results.get(key)
    if r is None:
        return "not run"
    if field == "tg" and r.get("tg") is None:
        return "**did not fit**" if r.get("fit") == "NO" or r.get("load_failed") else "failed, see log"
    v = r.get(field)
    return "n/a" if v is None else fmt.format(v)


def write_results():
    n32, n128 = results.get("q36-32768-n", {}).get("n"), results.get("q36-131072-n", {}).get("n")
    pct = lambda v: "n/a" if v is None else f"{v * 100:.1f}%"
    wall = lambda k: "not run" if k not in results else ("fits" if results[k]["ok"] else "fails")
    nz = lambda n, k: n if n is not None else ("none fits" if k.replace("-n0", "-rocm0-n0") in results else "not run")
    md = [f"# Ep 1 measurements, {datetime.date.today().isoformat()}", "",
          "Same software for every row. Logs for each cell are in `logs/`.", "",
          "## gpt-oss-20b, 32K (control)", "",
          "| Tier | `--device` | tok/s | used card free (MiB) |", "|---|---|---|---|",
          f"| 16GB | ROCm0 | {cell('gptoss-rocm0')} | {cell('gptoss-rocm0', 'xt_free', '{:,}')} (9070 XT) |",
          f"| 32GB | ROCm1 | {cell('gptoss-rocm1')} | {cell('gptoss-rocm1', 'r9700_free', '{:,}')} (R9700) |",
          f"| 48GB | ROCm0,ROCm1 | {cell('gptoss-both')} | {cell('gptoss-both', 'xt_free', '{:,}')} (9070 XT, tightest) |",
          "", "## Qwen3.6-35B-A3B UD-Q6_K", "",
          f"Smallest `--n-cpu-moe` on the 9070 XT alone ({MARGIN} MiB margin): 32K **{nz(n32, 'q36-32768-n0')}**, "
          f"128K **{nz(n128, 'q36-131072-n0')}** (of {Q36_LAYERS} expert layers). No offload at all: "
          f"32K {wall('q36-32768-rocm0-n0')}, 128K {wall('q36-131072-rocm0-n0')}.", "",
          "| Config | 32K tok/s | 128K tok/s | 128K free: 9070 XT / R9700 (MiB) |", "|---|---|---|---|"]
    for label, k in (("9070 XT alone, offload", "rocm0-offload"), ("Both cards, same offload (the twist)", "both-offload"),
                     ("R9700 alone, no offload", "rocm1"), ("Both cards, no offload (as written)", "both")):
        md.append(f"| {label} | {cell(f'q36-32k-{k}')} | {cell(f'q36-128k-{k}')} | "
                  f"{cell(f'q36-128k-{k}', 'xt_free', '{:,}')} / {cell(f'q36-128k-{k}', 'r9700_free', '{:,}')} |")
    md += ["", "Where the experts live, 9070 XT alone:", "",
           "| Context | Expert layers on GPU | Expert layers on CPU (`--n-cpu-moe`) |", "|---|---|---|"]
    for ctx, n in (("32K", n32), ("128K", n128)):
        md.append(f"| {ctx} | {'n/a' if n is None else Q36_LAYERS - n} | {'n/a' if n is None else n} |")
    md += ["", "## Qwen3.8-27B UD-Q6_K, 128K", "", "| Config | MTP | tok/s | Draft acceptance |", "|---|---|---|---|"]
    for label, k, mtp in (("Both cards", "q38-both-mtp", "on"), ("R9700 alone", "q38-rocm1-mtp", "on"),
                          ("R9700 alone", "q38-rocm1-nomtp", "off"), ("9070 XT alone", "q38-rocm0-mtp", "on")):
        acc = pct(results.get(k, {}).get("acceptance")) if mtp == "on" else "n/a"
        md.append(f"| {label} | {mtp} | {cell(k)} | {acc} |")
    md += ["", "## Real 128K depth", "", "| Preset | Prefill tok/s | Generation at depth tok/s | Draft |", "|---|---|---|---|"]
    for k, r in results.items():
        if k.startswith("depth-"):
            md.append(f"| {k[6:]} | {r['prefill']:,.1f} | {r['tg']:.2f} | {'' if r['draft'] is None else f'{r['draft']}%'} |")
    md += ["", "Empty-context generation for the 'kept' column: Qwen3.6 128K and Qwen3.8 both-cards rows above.", ""]
    (OUT / "results.md").write_text("\n".join(md))
    log(f"\nresults: {OUT / 'results.md'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop-servers", action="store_true")
    ap.add_argument("--only", default="devices,gptoss,q36,q38,depth")
    a = ap.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)
    preflight(a.stop_servers)
    steps = {"devices": step_devices, "gptoss": step_gptoss, "q36": step_q36, "q38": step_q38, "depth": step_depth}
    try:
        for s in a.only.split(","):
            log(f"\n===== {s} =====")
            steps[s]()
    finally:
        write_results()
        if a.stop_servers:
            log("servers were stopped; restart them with: switch-model.sh router")
