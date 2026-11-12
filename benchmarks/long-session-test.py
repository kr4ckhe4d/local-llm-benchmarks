#!/usr/bin/env python3
"""An agent-shaped long session against a running llama-server: one conversation that only
grows, as a coding agent's does, from a few thousand tokens to --depth.

Each turn appends one "tool result" (a slice of real source files, --chunk tokens) carrying a
planted fact, then asks for the fact planted TWO turns earlier and a one-line summary of the new
slice. Per turn it records what a preset has to get right over a long session:

  * recall     the earlier fact comes back (the KV cache at depth is intact)
  * reuse      prompt tokens actually evaluated: should be the new slice, not the whole history
  * speed      prefill and decode tok/s, draft acceptance
  * memory     server RSS (context checkpoints live in system RAM) and VRAM

  ./long-session-test.py --host http://127.0.0.1:8099 --pid <server pid> --depth 120000
"""
import argparse, json, pathlib, subprocess, sys, urllib.request

SRC = pathlib.Path.home() / "llama.cpp"
GLOBS = ("src/*.cpp", "common/*.cpp", "tools/server/*.cpp", "ggml/src/*.c", "ggml/src/*.cpp")
WORDS = ("amber", "basalt", "cobalt", "dune", "ember", "fjord", "garnet", "heron", "indigo",
         "juniper", "kestrel", "lichen", "marrow", "nectar", "onyx", "pollen")


def post(host, path, obj, timeout=3600):
    req = urllib.request.Request(host + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ntok(host, text):
    return len(post(host, "/tokenize", {"content": text})["tokens"])


def rss_mib(pid):
    """RSS of the server, or of the router's child if the pid has one."""
    best = 0
    for p in [pid] + subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split():
        try:
            for line in open(f"/proc/{p}/status"):
                if line.startswith("VmRSS"):
                    best = max(best, int(line.split()[1]) // 1024)
        except OSError:
            pass
    return best


def vram_mib():
    tot = 0
    for f in pathlib.Path("/sys/class/drm").glob("card[0-9]*/device/mem_info_vram_used"):
        if not f.parent.parent.name[4:].isdigit():      # skip card0-DP-3 and other connectors
            continue
        if int((f.parent / "mem_info_vram_total").read_text()) > 2 << 30:    # dGPUs only (gpu-mem.sh)
            tot += int(f.read_text()) >> 20
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://127.0.0.1:8099")
    ap.add_argument("--model", default="")
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--depth", type=int, default=120000)
    ap.add_argument("--chunk", type=int, default=12000)
    ap.add_argument("--max-tokens", type=int, default=160)
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    files = sorted(f for g in GLOBS for f in SRC.glob(g))
    corpus = "".join(f"\n// ===== {f.relative_to(SRC)} =====\n{f.read_text(errors='replace')}" for f in files)
    per_tok = len(corpus[:200000]) / ntok(a.host, corpus[:200000])
    step = int(a.chunk * per_tok)

    msgs = [{"role": "system", "content": "You are a coding agent reading a C++ code base. Answer in the exact "
             "format asked for, nothing else."}]
    rows, pos, turn = [], 0, 0
    print(f"{'turn':>4} {'ctx':>7} {'eval':>6} {'cached':>7} {'pp t/s':>7} {'tg t/s':>7} {'draft':>6} "
          f"{'rss':>6} {'vram':>6}  recall")
    while True:
        code = f"TOOL-{turn}-{WORDS[turn % len(WORDS)]}-{(turn * 7919 + 1237) % 9000 + 1000}"
        ask_turn = turn - 2
        want = (f"TOOL-{ask_turn}-{WORDS[ask_turn % len(WORDS)]}-{(ask_turn * 7919 + 1237) % 9000 + 1000}"
                if ask_turn >= 0 else None)
        chunk = corpus[pos:pos + step]; pos += step
        mid = len(chunk) // 2
        chunk = chunk[:mid] + f"\n// build ticket for tool result {turn}: {code}\n" + chunk[mid:]
        q = (f"Tool result {turn}:\n```\n{chunk}\n```\n"
             + (f"Line 1: the build ticket that was inside tool result {ask_turn}, exactly.\n" if want else "Line 1: the word none.\n")
             + "Line 2: one sentence on what the code in this tool result does.")
        msgs.append({"role": "user", "content": q})
        body = {"messages": msgs, "max_tokens": a.max_tokens, "temperature": 0, "cache_prompt": True}
        if a.model:
            body["model"] = a.model
        r = post(a.host, "/v1/chat/completions", body)
        text = r["choices"][0]["message"].get("content") or ""
        t, u = r.get("timings", {}), r.get("usage", {})
        ok = None if want is None else (want in text)
        row = dict(turn=turn, ctx=u.get("prompt_tokens"), eval=t.get("prompt_n"), cached=t.get("cache_n"),
                   pp=t.get("prompt_per_second"), tg=t.get("predicted_per_second"), n=t.get("predicted_n"),
                   draft_n=t.get("draft_n"), draft_acc=t.get("draft_n_accepted"),
                   rss=rss_mib(a.pid) if a.pid else None, vram=vram_mib(), recall=ok, text=text)
        rows.append(row)
        acc = f"{100 * row['draft_acc'] / row['draft_n']:.0f}%" if row["draft_n"] else "-"
        print(f"{turn:>4} {row['ctx']:>7} {row['eval']:>6} {str(row['cached']):>7} {row['pp']:>7.0f} {row['tg']:>7.1f} "
              f"{acc:>6} {str(row['rss']):>6} {row['vram']:>6}  {'-' if ok is None else 'ok' if ok else 'MISS'}", flush=True)
        msgs.append({"role": "assistant", "content": text})
        turn += 1
        if row["ctx"] + a.chunk + 2000 > a.depth or pos >= len(corpus):
            break

    asked = [r for r in rows if r["recall"] is not None]
    print(f"\nrecall {sum(r['recall'] for r in asked)} of {len(asked)}; final context {rows[-1]['ctx']} tokens; "
          f"decode first / last turn {rows[0]['tg']:.1f} / {rows[-1]['tg']:.1f} tok/s; "
          f"peak RSS {max((r['rss'] or 0) for r in rows)} MiB")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    sys.exit(main())
