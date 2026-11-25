#!/usr/bin/env python3
"""Summarise the unattended pi run that built the pagoda garden (~/code/pi-test).

Reads pi's session files and the loop log, writes run-stats.json next to this script.
    python3 benchmarks/pi-pagoda/collect.py [--sessions DIR] [--repo ~/code/pi-test]
"""
import argparse, glob, json, os
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.path.expanduser("~/code/pi-test"))
ap.add_argument("--sessions", default=None)
a = ap.parse_args()
repo = Path(a.repo)
sdir = a.sessions or glob.glob(os.path.expanduser("~/.pi/agent/sessions/*pi-test*"))[0]
ts = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))

sessions, models, tok = [], Counter(), Counter()
for f in sorted(glob.glob(f"{sdir}/*.jsonl")):
    s = {"file": Path(f).name, "start": None, "end": None, "assistant": 0, "tool_calls": 0,
         "task_complete": 0, "compactions": 0, "output_tokens": 0}
    for line in open(f):
        r = json.loads(line)
        t = r.get("timestamp")
        if t:
            s["start"] = s["start"] or t
            s["end"] = t
        if r.get("type") == "model_change":
            models[f'{r["provider"]}/{r["modelId"]}'] += 1
        if r.get("type") == "compaction":
            s["compactions"] += 1
        m = r.get("message") or {}
        if m.get("role") == "assistant":
            s["assistant"] += 1
            u = m.get("usage") or {}
            for k in ("input", "output", "cacheRead"):
                tok[k] += u.get(k) or 0
            s["output_tokens"] += u.get("output") or 0
            for p in m.get("content") or []:
                if isinstance(p, dict) and p.get("type") == "toolCall":
                    s["tool_calls"] += 1
                    s["task_complete"] += p.get("name") == "task_complete"
    s["minutes"] = round((ts(s["end"]) - ts(s["start"])).total_seconds() / 60, 1)
    sessions.append(s)

# task timeline from the loop log: the last entry per (task, status) run, first start = previous task's end
log = [l.split("\t") for l in (repo / ".ai/loop-log.tsv").read_text().splitlines() if l.strip()]
tasks, prev_end = OrderedDict(), ts(sessions[0]["start"])
for when, tid, status, summary in log:
    t = tasks.setdefault(tid, {"task": tid, "start": prev_end.isoformat(), "partials": 0, "calls": 0})
    t["calls"] += 1
    if status == "partial":
        t["partials"] += 1
    if status == "done":
        t["end"] = when
        t["minutes"] = round((ts(when) - ts(t["start"])).total_seconds() / 60, 1)
        t["summary"] = summary.strip()
        prev_end = ts(when)
goal = (repo / ".ai/GOAL_MET").read_text().splitlines()[0].strip()
if "T16" not in tasks:  # the final review ends with goal_complete, not task_complete
    tasks["T16"] = {"task": "T16", "start": prev_end.isoformat(), "end": goal, "partials": 0, "calls": 0,
                    "minutes": round((ts(goal) - prev_end).total_seconds() / 60, 1),
                    "summary": "Final review: every acceptance check run in-session, README, final screenshots; goal_complete."}

start, end = ts(sessions[0]["start"]), ts(sessions[-1]["end"])
out = {
    "repo": str(repo).replace(str(Path.home()), "~"),
    "model": dict(models),
    "start": start.isoformat(), "end": end.isoformat(),
    "wall_hours": round((end - start).total_seconds() / 3600, 2),
    "sessions": len(sessions),
    "assistant_messages": sum(s["assistant"] for s in sessions),
    "tool_calls": sum(s["tool_calls"] for s in sessions),
    "compactions": sum(s["compactions"] for s in sessions),
    "tokens": {"output": tok["output"], "prompt_uncached": tok["input"], "prompt_cached": tok["cacheRead"]},
    "goal_met": goal,
    "tasks": list(tasks.values()),
    "per_session": sessions,
}
(Path(__file__).parent / "run-stats.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print(json.dumps({k: out[k] for k in ("model", "wall_hours", "sessions", "tool_calls", "compactions", "tokens")}))
