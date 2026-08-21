#!/usr/bin/env python3
"""Exercise the *native* tool-calling path -- the OpenAI `tools` field parsed
by llama.cpp into structured `tool_calls`, not prompt-injected XML.

The probe tool returns a value that cannot be derived without calling it
(`PROBE-<seeded random>`), so a model answering from the forward pass cannot
fake it. Two cases: one call, and two calls plus a sum -- the second shows
whether the model delegates arithmetic to `add_numbers` or does it in-head.

  ./tool-calling-test.py http://127.0.0.1:8099
"""
import json, random, sys, urllib.request
HOST = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099"
def probe(seed): return f"PROBE-{random.Random(seed).randint(100000,999999)}"
TOOLS = [
 {"type":"function","function":{"name":"get_probe_token","description":
  "Return the secret probe token for a given seed. There is no way to derive this value without calling this function.",
  "parameters":{"type":"object","properties":{"seed":{"type":"integer","description":"Integer seed for the token."}},"required":["seed"]}}},
 {"type":"function","function":{"name":"add_numbers","description":"Add two integers and return the sum.",
  "parameters":{"type":"object","properties":{"a":{"type":"integer"},"b":{"type":"integer"}},"required":["a","b"]}}},
]
def call(msgs):
    req = urllib.request.Request(HOST+"/v1/chat/completions",
        data=json.dumps({"messages":msgs,"tools":TOOLS,"tool_choice":"auto","max_tokens":1200,
                         "chat_template_kwargs":{"enable_thinking":False}}).encode(),
        headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(req, timeout=600))["choices"][0]["message"]
def run(label, user):
    msgs=[{"role":"user","content":user}]; ncalls=0
    for _ in range(6):
        m = call(msgs)
        tc = m.get("tool_calls") or []
        if not tc:
            print(f"{label}: calls={ncalls} | {(m.get('content') or '').strip()[:220]}"); return
        msgs.append({"role":"assistant","content":m.get("content") or "","tool_calls":tc})
        for c in tc:
            ncalls += 1
            fn = c["function"]["name"]; a = json.loads(c["function"]["arguments"])
            r = probe(a["seed"]) if fn=="get_probe_token" else str(a["a"]+a["b"])
            print(f"   -> {fn}({a}) = {r}")
            msgs.append({"role":"tool","tool_call_id":c["id"],"name":fn,"content":r})
    print(f"{label}: exceeded turn budget")
run("SINGLE  ", "What is the probe token for seed 42? Use the tool.")
print()
run("PARALLEL", "Get the probe tokens for seed 7 and seed 1234, then give me the sum of the two numeric parts.")
