import importlib.util, json, urllib.request, sys
spec = importlib.util.spec_from_file_location("cq", "/home/nipuna/code/local-llm-benchmarks/benchmarks/code-quality-test.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
tasks = {t[0]: t[1] for t in m.TASKS}
for name in ("csv_rows", "glob_match"):
    payload = {"messages":[{"role":"user","content":tasks[name]}],
               "max_tokens":30000,"temperature":0.0,
               "chat_template_kwargs":{"enable_thinking":True}}
    req = urllib.request.Request("http://127.0.0.1:8099/v1/chat/completions",
        data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.load(r)
    ch = d["choices"][0]; msg = ch["message"]
    print(f"{name:12s} finish={ch.get('finish_reason')!r:12s} "
          f"content={len(msg.get('content') or '')}ch "
          f"reasoning={len(msg.get('reasoning_content') or '')}ch "
          f"completion_tokens={d['usage']['completion_tokens']}")
    print("   content head:", repr((msg.get('content') or '')[:120]))
