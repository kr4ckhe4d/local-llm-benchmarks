#!/usr/bin/env node
// Headless check of the scene: screenshots, console errors, FPS, renderer stats.
// No dependencies (Node >= 22 global WebSocket + Chrome DevTools Protocol).
//
//   node tools/shot.mjs                         -> default view, shots/default.png
//   node tools/shot.mjs --name dusk --query "preset=2&time=18.5"
//   node tools/shot.mjs --all                   -> every view in tools/views.json
//   options: --width 1920 --height 1080 --wait 6000 (ms after load) --fps-ms 3000
//
// The page is served from the repo root by a built-in static server.
// Output: shots/<name>.png and one JSON line per view on stdout:
//   {"name","png","errors":[...],"warnings":n,"fps":..,"image":{stats},"diag":{...window.__diag}}
// image stats (from a 320px-wide downscale): meanLum 0-1, darkPct (<4% lum), brightPct (>96% lum),
//   meanSat 0-1, edgePct (detail/texture density), colours4bit (distinct 12-bit colours), huesPct (top hues).
// Exit code 1 if any view had a console error, page error or failed request.
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, writeFile, mkdir, mkdtemp, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, extname, resolve, dirname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(`--${k}`); return i >= 0 ? args[i + 1] : d; };
const W = +opt("width", 1600), H = +opt("height", 900);
const WAIT = +opt("wait", 6000), FPS_MS = +opt("fps-ms", 3000);
const PAGE = opt("page", "index.html");

let views;
if (args.includes("--all")) views = JSON.parse(await readFile(join(ROOT, "tools/views.json"), "utf8"));
else views = [{ name: opt("name", "default"), query: opt("query", "") }];

const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
  ".ktx2": "image/ktx2", ".hdr": "application/octet-stream", ".exr": "application/octet-stream", ".glb": "model/gltf-binary",
  ".gltf": "model/gltf+json", ".wasm": "application/wasm", ".bin": "application/octet-stream", ".svg": "image/svg+xml" };
const server = createServer(async (req, res) => {
  const p = join(ROOT, decodeURIComponent(new URL(req.url, "http://x").pathname));
  if (!p.startsWith(ROOT)) { res.writeHead(403).end(); return; }
  try { const b = await readFile(p); res.writeHead(200, { "content-type": MIME[extname(p)] || "application/octet-stream" }).end(b); }
  catch { res.writeHead(404).end("not found"); }
});
await new Promise(r => server.listen(0, "127.0.0.1", r));
const port = server.address().port;

const profile = await mkdtemp(join(tmpdir(), "shot-chrome-"));
const chrome = spawn(process.env.CHROME || "google-chrome-stable", [
  "--headless=new", "--no-sandbox", "--no-first-run", "--hide-scrollbars", "--mute-audio",
  "--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=vulkan", "--enable-unsafe-swiftshader",
  `--user-data-dir=${profile}`, `--window-size=${W},${H}`, "--remote-debugging-port=0", "about:blank",
], { stdio: ["ignore", "ignore", "pipe"] });
const wsUrl = await new Promise((ok, bad) => {
  let buf = ""; const t = setTimeout(() => bad(new Error("chrome did not start")), 20000);
  chrome.stderr.on("data", d => { buf += d; const m = buf.match(/DevTools listening on (ws:\/\/\S+)/); if (m) { clearTimeout(t); ok(m[1]); } });
});

const ws = new WebSocket(wsUrl); await new Promise(r => ws.addEventListener("open", r));
let id = 0; const pending = new Map(); const listeners = [];
ws.addEventListener("message", e => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { const { ok, bad } = pending.get(m.id); pending.delete(m.id); m.error ? bad(new Error(m.error.message)) : ok(m.result); }
  else listeners.forEach(f => f(m));
});
const send = (method, params = {}, sessionId) => new Promise((ok, bad) => { const i = ++id; pending.set(i, { ok, bad }); ws.send(JSON.stringify({ id: i, method, params, sessionId })); });

await mkdir(join(ROOT, "shots"), { recursive: true });
let failed = false;
for (const v of views) {
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  const errors = []; let warnings = 0;
  const onMsg = m => {
    if (m.sessionId !== sessionId) return;
    if (m.method === "Runtime.consoleAPICalled") {
      const text = m.params.args.map(a => a.value ?? a.description ?? "").join(" ");
      if (m.params.type === "error" || m.params.type === "assert") errors.push(`console.error: ${text}`);
      if (m.params.type === "warning") warnings++;
    } else if (m.method === "Runtime.exceptionThrown") {
      const d = m.params.exceptionDetails; errors.push(`exception: ${d.exception?.description || d.text}`);
    } else if (m.method === "Network.loadingFailed" && !m.params.canceled) {
      errors.push(`request failed: ${m.params.errorText} ${m.params.requestId}`);
    } else if (m.method === "Network.responseReceived" && m.params.response.status >= 400 && !m.params.response.url.endsWith("/favicon.ico")) {
      errors.push(`HTTP ${m.params.response.status}: ${m.params.response.url}`);
    }
  };
  listeners.push(onMsg);
  await send("Runtime.enable", {}, sessionId); await send("Network.enable", {}, sessionId); await send("Page.enable", {}, sessionId);
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false }, sessionId);
  const q = v.query ? `?${v.query}` : "";
  await send("Page.navigate", { url: `http://127.0.0.1:${port}/${PAGE}${q}` }, sessionId);
  await new Promise(r => setTimeout(r, WAIT));
  const fpsExpr = `new Promise(r=>{let n=0;const t0=performance.now();(function f(){n++;performance.now()-t0<${FPS_MS}?requestAnimationFrame(f):r(n*1000/(performance.now()-t0))})()})`;
  const fps = (await send("Runtime.evaluate", { expression: fpsExpr, awaitPromise: true, returnByValue: true }, sessionId)).result.value;
  const diag = (await send("Runtime.evaluate", { expression: "JSON.stringify(window.__diag ?? null)", returnByValue: true }, sessionId)).result.value;
  const { data } = await send("Page.captureScreenshot", { format: "png" }, sessionId);
  const png = join("shots", `${v.name}.png`);
  await writeFile(join(ROOT, png), Buffer.from(data, "base64"));
  // Image statistics for models that cannot look at the PNG (decoded by Chrome in the page).
  const statsExpr = `(async()=>{const b=await (await fetch("data:image/png;base64,${data}")).blob();
    const bm=await createImageBitmap(b);const w=320,h=Math.round(bm.height*320/bm.width);
    const c=new OffscreenCanvas(w,h);const g=c.getContext("2d");g.drawImage(bm,0,0,w,h);
    const d=g.getImageData(0,0,w,h).data;let n=w*h,sl=0,dark=0,bright=0,sat=0,edges=0;const L=new Float32Array(n);const hues=new Array(12).fill(0);const cols=new Set();
    for(let i=0;i<n;i++){const r=d[i*4]/255,gg=d[i*4+1]/255,bb=d[i*4+2]/255;const l=0.2126*r+0.7152*gg+0.0722*bb;L[i]=l;sl+=l;
      if(l<0.04)dark++;if(l>0.96)bright++;const mx=Math.max(r,gg,bb),mn=Math.min(r,gg,bb),s=mx?(mx-mn)/mx:0;sat+=s;
      cols.add((d[i*4]>>4)<<8|(d[i*4+1]>>4)<<4|(d[i*4+2]>>4));
      if(s>0.2&&mx>0.15){let hh=mx===r?((gg-bb)/(mx-mn))%6:mx===gg?(bb-r)/(mx-mn)+2:(r-gg)/(mx-mn)+4;hues[Math.floor(((hh*60+360)%360)/30)]++;}}
    for(let y=1;y<h-1;y++)for(let x=1;x<w-1;x++){const i=y*w+x;const gx=L[i+1]-L[i-1],gy=L[i+w]-L[i-w];if(Math.hypot(gx,gy)>0.1)edges++;}
    const names=["red","orange","yellow","lime","green","teal","cyan","sky","blue","violet","magenta","pink"];
    const top=hues.map((v,i)=>[names[i],Math.round(v*1000/n)/10]).filter(x=>x[1]>=1).sort((a,b)=>b[1]-a[1]).slice(0,5);
    return {meanLum:+(sl/n).toFixed(3),darkPct:+(dark*100/n).toFixed(1),brightPct:+(bright*100/n).toFixed(1),
      meanSat:+(sat/n).toFixed(3),edgePct:+(edges*100/n).toFixed(1),colours4bit:cols.size,huesPct:top};})()`;
  const stats = (await send("Runtime.evaluate", { expression: statsExpr, awaitPromise: true, returnByValue: true }, sessionId)).result.value;
  listeners.splice(listeners.indexOf(onMsg), 1);
  await send("Target.closeTarget", { targetId });
  if (errors.length) failed = true;
  console.log(JSON.stringify({ name: v.name, png, query: v.query, errors, warnings, fps: Math.round(fps * 10) / 10, image: stats, diag: JSON.parse(diag) }));
}
ws.close(); chrome.kill(); server.close();
await rm(profile, { recursive: true, force: true }).catch(() => {});
process.exit(failed ? 1 : 0);
