#!/usr/bin/env python3
import json, os, signal, subprocess, sys, time

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
# npx spawns node -> chrome-devtools-mcp -> node watchdog -> chrome -> chrome
# zygote/renderer children. Killing only the immediate Popen leaves the deeper
# ones as orphans holding this process's stdout fd open, which hangs any
# caller piping our output (e.g. `verify.sh | tail` blocks on EOF forever).
# start_new_session=True puts the whole tree in one process group so it can
# be killed together with os.killpg.
p = subprocess.Popen(["npx", "-y", "chrome-devtools-mcp@latest", "--isolated", "--headless"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
    start_new_session=True)
def kill_tree():
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except Exception:
        p.kill()
rid = [0]
def call(method, params=None):
    rid[0] += 1
    p.stdin.write(json.dumps({"jsonrpc":"2.0","id":rid[0],"method":method,"params":params or {}})+"\n"); p.stdin.flush()
    for _ in range(300):
        l = p.stdout.readline()
        if not l: return None
        try: m = json.loads(l)
        except Exception: continue
        if m.get("id") == rid[0]: return m
def notify(method, params=None):
    p.stdin.write(json.dumps({"jsonrpc":"2.0","method":method,"params":params or {}})+"\n"); p.stdin.flush()
def tool(name, args=None):
    r = call("tools/call", {"name":name,"arguments":args or {}})
    if not r: return ""
    if "error" in r: return f"ERROR: {r['error']}"
    c = r.get("result",{}).get("content",[])
    return "\n".join(x.get("text","") for x in c if isinstance(x,dict))

call("initialize", {"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"v","version":"1"}})
notify("notifications/initialized")
tool("navigate_page", {"url": URL})
time.sleep(2.5)
mounted = tool("evaluate_script", {"function":
    "() => { const r=document.getElementById('root'); return r ? r.children.length : -1; }"})
console = tool("list_console_messages", {})
network = tool("list_network_requests", {})
kill_tree()

print("=== MOUNTED (React children under #root) ===")
print(mounted)

print("=== CONSOLE ===")
print(console)
print("=== NETWORK ===")
print(network)

ALLOWED_WARN = "in-browser Babel transformer"
# favicon.ico is requested by every browser automatically and no task in this
# comparison ever asks for one; treat it as browser noise, same class as the
# Babel warning, not a real bug.
# One generic "Failed to load resource: 404" console line with no URL
# attached is the favicon fetch; the network log's own favicon.ico [404] is
# what actually identifies it. Exempt exactly one such line per run.
FAVICON_GENERIC = "Failed to load resource: the server responded with a status of 404"
favicon_console_exempted = False
bad = []
for line in console.splitlines():
    if "favicon.ico" in line:
        continue
    if "[error]" in line:
        if FAVICON_GENERIC in line and not favicon_console_exempted:
            favicon_console_exempted = True
            continue
        bad.append(line)
    elif "[warn]" in line and ALLOWED_WARN not in line:
        bad.append(line)
for line in network.splitlines():
    if "favicon.ico" in line:
        continue
    if "]" in line and "[" in line:
        try:
            code = line.rsplit("[",1)[1].rstrip("]")
            code = code.split("→")[-1]
            if code.isdigit() and not (200 <= int(code) < 400):
                bad.append(line)
        except Exception:
            pass

if bad:
    print("=== FAIL: unexpected console/network entries ===")
    for b in bad: print(" ", b)
    sys.exit(1)
try:
    n_children = int("".join(c for c in mounted if c.isdigit() or c=="-") or "-1")
except Exception:
    n_children = -1
if n_children <= 0:
    print(f"=== FAIL: #root has {n_children} children -- nothing rendered (missing/broken index.html, or dashboard not built yet) ===")
    sys.exit(1)

print("=== PASS: clean, and #root has real content ===")
sys.exit(0)
