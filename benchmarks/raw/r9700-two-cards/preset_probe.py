#!/usr/bin/env python3
"""Fit and probe presets exactly as written, on today's two cards.

For presets the 2026-10-05 session never measured on two cards: gpt-oss-20b
and Qwen3.5-9B (left alone, they fit one card), Muse 32k and Qwen3.5-27B
32k/128k. Each preset gets [*] plus its own lines, then fit.sh (per-card
headroom) and the same 700-token probe as moe_sweep.py and dense.sh, n=3.

  LOGDIR=logs python3 preset_probe.py <out.txt> <preset> [preset ...]
  EXTRA="--device ROCm1" python3 preset_probe.py ...   # appended to every preset
"""
import os, re, shlex, sys

sys.argv, ARGS = sys.argv[:2], sys.argv  # moe_sweep reads OUT/ONLY at import
import moe_sweep as ms  # noqa: E402  (its main loop is guarded below)

SKIP = {"alias", "model", "ctx-size", "load-on-startup", "version"}


def sections():
    cur, out = None, {}
    for raw in open(ms.PRESETS):
        line = raw.split(";")[0].strip()
        if not line:
            continue
        m = re.match(r"\[(.+)\]", line)
        if m:
            cur = {"name": m.group(1), "kv": []}
            out[cur["name"]] = cur
            continue
        if "=" in line and cur is not None:
            k, v = [x.strip() for x in line.split("=", 1)]
            cur[k] = v
            cur["kv"].append((k, v))
    return out


def flags(p, glob):
    f = []
    for k, v in glob["kv"] + p["kv"]:
        if k in SKIP or k in ("n-gpu-layers", "parallel"):
            continue  # fit.sh and probe() pass -ngl 99 -np 1 themselves
        f += [f"--{k}", v]
    return f + shlex.split(os.environ.get("EXTRA", ""))


if __name__ == "__main__":
    ms.OUT = ARGS[1]
    allp = sections()
    glob = allp.pop("*", {"kv": []})
    for name in ARGS[2:]:
        p = allp[name]
        ms.flags = lambda p, n, glob=glob: flags(p, glob)  # same fit/probe, preset's own flags
        ms.log(f"\n######## {name}  (ctx {p['ctx-size']}, as written{' + ' + os.environ['EXTRA'] if os.environ.get('EXTRA') else ''})")
        ok, text, first = ms.fit(p, 0)
        ms.log(f"  fit {'OK  ' if ok else 'NO  '} {first}")
        for extra in text.splitlines()[1:]:
            if any(s in extra for s in ("per-card", "FAIL", "SPILL", "ABORT")):
                ms.log(f"      {extra.strip()}")
        ms.log(f"  probe: {ms.fmt(ms.probe(p, 0))}")
