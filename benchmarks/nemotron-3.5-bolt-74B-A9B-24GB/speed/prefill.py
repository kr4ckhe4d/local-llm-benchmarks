import json, sys, urllib.request, time
model = sys.argv[1]
src = open('/home/nipuna/llama.cpp/tools/server/server-context.cpp', errors='ignore').read() if False else ''
import glob
txt = ''
for f in sorted(glob.glob('/home/nipuna/llama.cpp/src/llama-*.cpp')):
    txt += open(f, errors='ignore').read()
    if len(txt) > 60000: break
txt = txt[:60000]
for run in range(2):
    body = {"model": model, "messages": [{"role": "user", "content": f"run {run}\n" + txt + "\n\nSummarise this code in one sentence."}],
            "max_tokens": 64, "temperature": 0, "cache_prompt": False}
    req = urllib.request.Request('http://127.0.0.1:8090/v1/chat/completions', json.dumps(body).encode(), {'Content-Type': 'application/json'})
    t = json.load(urllib.request.urlopen(req, timeout=1800)).get('timings', {})
    print(f"{model} run{run}: prompt {t.get('prompt_n')} tok at {t.get('prompt_per_second',0):.0f} tok/s ({t.get('prompt_ms',0)/1000:.1f} s)", flush=True)
