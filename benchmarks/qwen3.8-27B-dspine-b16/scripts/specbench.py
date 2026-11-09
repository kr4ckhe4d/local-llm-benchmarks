#!/usr/bin/env python3
import json, sys, urllib.request, statistics
host, label, nmax, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
P = {
 "code": "Write a complete Python implementation of a thread-safe LRU cache class with get, put, and delete methods, full docstrings, and type hints. Then write pytest unit tests for it. Output only code.",
 "math": "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. Then in June she sold 30% more than April and May combined. A clip costs $1.75. Solve step by step: how many clips did she sell in total, and how much money did she make? Then generalize the method into a short worked explanation with two more example problems of the same kind, each solved step by step.",
 "chat": "I'm planning a two-week trip to Japan in autumn with my partner. We like hiking, food markets and quiet towns more than big cities. Suggest an itinerary with reasons for each stop, and practical tips on rail passes, budgets and etiquette.",
}
def post(c, mt):
    r = urllib.request.Request(host+"/v1/chat/completions", data=json.dumps({"messages":[{"role":"user","content":c}],"max_tokens":mt,"temperature":0.0,"cache_prompt":False,"chat_template_kwargs":{"enable_thinking":False}}).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=1800).read())["timings"]
post(P["code"], 32)
for task, c in P.items():
    for run in range(2):
        t = post(c, 700)
        dn, da = t.get("draft_n", 0), t.get("draft_n_accepted", 0)
        rounds = dn / nmax if nmax else 0
        tau = (da + rounds) / rounds if rounds else 1.0
        rec = dict(label=label, task=task, run=run, tg=t["predicted_per_second"], n=t["predicted_n"], draft_n=dn, draft_acc=da, acc=(da/dn if dn else None), tau_est=tau)
        print(json.dumps(rec), flush=True)
        open(out, "a").write(json.dumps(rec)+"\n")
