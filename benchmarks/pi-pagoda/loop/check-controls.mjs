// T14: programmatic controls check.
// Launches headless Chrome on the local page (ui=1, paused) and drives every
// controls-panel control via CDP Runtime.evaluate, asserting the effect on
// window.__diag (and camera position for presets) after a settle wait —
// __diag is only rewritten in the animate loop, so a synchronous read returns
// last-frame values (see .ai/decisions.md, T13).
//
// Reload-type controls (quality, regenerate) are verified by detecting the
// navigation ("Inspected target navigated or closed") and then polling the
// reloaded page until __diag reflects the new value.
//
// Usage: node tools/check-controls.mjs
// Exit 0 = every control passes, 1 = at least one failure, 2 = launch failure.

import { spawn } from "node:child_process";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createServer } from "node:http";

const ROOT = new URL("..", import.meta.url).pathname;
const PAGE = "ui=1&time=10&preset=1"; // seed=42, quality=high, running (not paused)

const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg" };
const server = createServer((req, res) => {
  const u = req.url.split("?")[0];
  readFile(join(ROOT, u)).then(b => { res.writeHead(200, { "content-type": MIME[u.slice(u.lastIndexOf("."))] ?? "application/octet-stream" }); res.end(b); }, () => { res.writeHead(404); res.end(); });
});
await new Promise(r => server.listen(0, "127.0.0.1", r));
const port = server.address().port;

const profile = await mkdtemp(join(tmpdir(), "check-ctrl-chrome-"));
const chrome = spawn(process.env.CHROME || "google-chrome-stable", [
  "--headless=new", "--no-sandbox", "--no-first-run", "--hide-scrollbars", "--mute-audio",
  "--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=vulkan", "--enable-unsafe-swiftshader",
  `--user-data-dir=${profile}`, `--window-size=1600,900`, "--remote-debugging-port=0", "about:blank",
], { stdio: ["ignore", "ignore", "pipe"] });

const wsUrl = await new Promise((ok, bad) => {
  let buf = "";
  const t = setTimeout(() => bad(new Error("chrome did not start: " + buf.slice(0, 500))), 20000);
  chrome.stderr.on("data", d => {
    buf += d;
    const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
    if (m) { clearTimeout(t); ok(m[1]); }
  });
});
const ws = new WebSocket(wsUrl);
await new Promise(r => ws.addEventListener("open", r));
let msgId = 0;
const pending = new Map();
const pageErrors = [];
ws.addEventListener("message", e => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") pageErrors.push("exc: " + (m.params.exceptionDetails?.exception?.description ?? m.params.exceptionDetails?.text ?? "?"));
  if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") pageErrors.push("err: " + (m.params.args ?? []).map(a => a.value ?? a.description).join(" "));
});
const send = (method, params = {}, sessionId) => new Promise(ok => {
  const id = ++msgId; pending.set(id, ok);
  ws.send(JSON.stringify({ id, method, params, sessionId }));
});

const { targetId } = (await send("Target.createTarget", { url: "about:blank" })).result ?? {};
const { sessionId } = (await send("Target.attachToTarget", { targetId, flatten: true })).result ?? {};
await send("Page.enable", {}, sessionId);
await send("Runtime.enable", {}, sessionId);
await send("Emulation.setDeviceMetricsOverride", { width: 1600, height: 900, deviceScaleFactor: 1, mobile: false }, sessionId);
await send("Page.navigate", { url: `http://127.0.0.1:${port}/index.html?${PAGE}` }, sessionId);
await new Promise(r => setTimeout(r, 15000)); // scene build

// Evaluate an async expression; a page navigation mid-flight resolves to "NAVIGATED".
async function ev(expr) {
  const out = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }, sessionId);
  if (out.error) return /navigated or closed|Cannot find context|Execution context was destroyed/i.test(out.error.message ?? "") ? "NAVIGATED" : out.error;
  const r = out.result ?? {};
  if (r.exceptionDetails) return "EXC: " + (r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
  return r.result?.value;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

// Poll the (re)loaded page until expr yields the expected value.
async function pollUntil(expr, expected, timeoutMs = 90000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const v = await ev(expr);
    if (v === expected) return true;
    await sleep(1000);
  }
  return false;
}

// ---------------------------------------------------------------- battery
// Each test: name + async page JS returning {ok, info}. Every test ends with
// its control restored, so later tests start from the known baseline.
// The in-page helpers are defined once, in a warm-up expression.
const WARM = `(async () => {
  const D = () => window.__diag;
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const setRange = async (id, val) => { const el = document.getElementById(id); el.value = val; el.dispatchEvent(new Event("input", {bubbles:true})); await wait(100); return D(); };
  const setCheck = async (id, checked) => { const el = document.getElementById(id); el.checked = checked; el.dispatchEvent(new Event("change", {bubbles:true})); await wait(100); return D(); };
  const click = async (id, ms = 100) => { document.getElementById(id).click(); await wait(ms); return D(); };
  const key = async k => { window.dispatchEvent(new KeyboardEvent("keydown", {key:k, bubbles:true})); await wait(100); return D(); };
  const cam = () => window.__scene.camera.position;
  const near = (a, b, tol = 0.05) => a.every((v, i) => Math.abs(v - b[i]) < tol);
  window.__T = { D, wait, setRange, setCheck, click, key, cam, near };
  return D();
})()`;

const T = [];
T.push(["panel present (ui=1)", async () => {
  const ok = !!(window.__T && document.getElementById("ui-panel") && document.getElementById("ui-title"));
  const d = D();
  return { ok: ok && d.ready === true, info: `ready=${d.ready} seed=${d.seed} quality=${d.quality}` };
}]);
T.push(["time slider 9→17", async () => {
  const d = await setRange("ui-time", 17);
  return { ok: Math.abs(d.time - 17) < 0.05, info: `diag.time=${d.time}` };
}]);
T.push(["pause toggle on/off", async () => {
  const a = await click("ui-pause");
  const b = await click("ui-pause");
  return { ok: a.paused === 1 && b.paused === 0, info: `paused 0→${a.paused}→${b.paused}` };
}]);
T.push(["cycle speed 0.05→0.3", async () => {
  const d = await setRange("ui-speed", 0.3);
  return { ok: Math.abs(d.cycleSpeed - 0.3) < 0.005, info: `cycleSpeed=${d.cycleSpeed}` };
}]);
T.push(["petals 800→2000→0→800", async () => {
  const a = await setRange("ui-petals", 2000), b = await setRange("ui-petals", 0), c = await setRange("ui-petals", 800);
  return { ok: a.petals === 2000 && b.petals === 0 && c.petals === 800, info: `petals ${D().petals}→${a.petals}→${b.petals}→${c.petals}` };
}]);
T.push(["wind 1→2.5", async () => {
  const d = await setRange("ui-wind", 2.5);
  return { ok: Math.abs(d.wind - 2.5) < 0.05, info: `wind=${d.wind}` };
}]);
T.push(["auto-rotate toggle", async () => {
  const a = await setCheck("ui-rotate", true);
  const b = await setCheck("ui-rotate", false);
  return { ok: a.autoRotate === 1 && b.autoRotate === 0, info: `autoRotate ${D().autoRotate}→${a.autoRotate}→${b.autoRotate}` };
}]);
T.push(["shadows toggle", async () => {
  const a = await setCheck("ui-shadows", false);
  const b = await setCheck("ui-shadows", true);
  return { ok: a.shadows === 0 && b.shadows === 1, info: `shadows ${D().shadows}→${a.shadows}→${b.shadows}` };
}]);
T.push(["post-FX toggle", async () => {
  const a = await setCheck("ui-post", false);
  const b = await setCheck("ui-post", true);
  return { ok: a.post === 0 && b.post === 1, info: `post ${D().post}→${a.post}→${b.post}` };
}]);
T.push(["fireflies toggle", async () => {
  const a = await setCheck("ui-fireflies", false);
  const b = await setCheck("ui-fireflies", true);
  return { ok: a.fireflies === 0 && b.fireflies === 1, info: `fireflies ${D().fireflies}→${a.fireflies}→${b.fireflies}` };
}]);
T.push(["water toggle", async () => {
  const a = await setCheck("ui-water", false);
  const b = await setCheck("ui-water", true);
  return { ok: a.water === 0 && b.water === 1, info: `water ${D().water}→${a.water}→${b.water}` };
}]);
T.push(["wireframe toggle", async () => {
  const a = await setCheck("ui-wireframe", true);
  const b = await setCheck("ui-wireframe", false);
  return { ok: a.wireframe === 1 && b.wireframe === 0, info: `wireframe ${D().wireframe}→${a.wireframe}→${b.wireframe}` };
}]);
T.push(["preset 3 button → pond camera", async () => {
  const d = await click("ui-preset-3", 1700); // tween is 1.4 s
  const p = [cam().x, cam().y, cam().z];
  return { ok: d.preset === 3 && near(p, [2.3, 5.7, 15.9]), info: `preset=${d.preset} cam=[${p.map(v => v.toFixed(2))}]` };
}]);
for (const k of ["1", "2", "4", "5"]) {
  const pos = { "1": [64, 40, 66], "2": [20, 14, 22], "4": [-30, 8, 34], "5": [34, -26, 40] }[k];
  T.push([`keyboard preset ${k}`, async (a) => {
    const [k, pos] = a;
    const d = await key(k);
    await wait(1700);
    const p = [cam().x, cam().y, cam().z];
    return { ok: d.preset === +k && near(p, pos), info: `preset=${d.preset} cam=[${p.map(v => v.toFixed(2))}] want [${pos}]` };
  }, [k, pos]]);
}
T.push(["reset view returns to preset camera", async () => {
  await click("ui-preset-5", 1700); // make the target preset deterministic
  const S = window.__scene;
  S.camera.position.set(99, 9, 99); S.controls.target.set(9, 9, 9);
  const d = await click("ui-reset", 1700);
  const p = [cam().x, cam().y, cam().z];
  return { ok: near(p, [34, -26, 40]), info: `preset=${d.preset} cam=[${p.map(v => v.toFixed(2))}] want [34,-26,40]` };
}]);
T.push(["keyboard Space toggles auto-rotate", async () => {
  const a = await key(" ");
  const b = await key(" ");
  return { ok: a.autoRotate === 1 && b.autoRotate === 0, info: `autoRotate ${D().autoRotate}→${a.autoRotate}→${b.autoRotate}` };
}]);
T.push(["keyboard N jumps day↔night", async () => {
  await setRange("ui-time", 17); // start deterministically in the day window
  const a = await key("n");
  const b = await key("n");
  return { ok: Math.abs(a.time - 23) < 0.05 && Math.abs(b.time - 9) < 0.05, info: `time 17→${a.time}→${b.time}` };
}]);
T.push(["collapse + reopen panel", async () => {
  document.getElementById("ui-head").click();
  const hidden = document.getElementById("ui-body").style.display === "none";
  document.getElementById("ui-head").click();
  const shown = document.getElementById("ui-body").style.display !== "none";
  await wait(50);
  return { ok: hidden && shown, info: `hidden=${hidden} reshown=${shown}` };
}]);

const warm = await ev(WARM);
if (typeof warm !== "object" || !warm) { console.error("WARM-UP FAILED:", String(warm).slice(0, 400)); chrome.kill(); server.close(); process.exit(2); }

let pass = 0, fail = 0;
// Tests are written as `async (arg) => {...}` bodies that reference the
// helpers defined by WARM; re-wrap each one so the helpers are in scope.
// NOTE: fn.toString() is serialized to the page — a test body may only refer
// to its own params/locals (free Node-scope variables would be undefined
// in-page; that's why loop vars are passed as the arg).
async function runTest(name, fn, arg) {
  const expr = `(async () => { const {D,wait,setRange,setCheck,click,key,cam,near} = window.__T; const inner = ${fn.toString()}; return await inner(${JSON.stringify(arg)}); })()`;
  const v = await ev(expr);
  if (v === "NAVIGATED") return { nav: true };
  const ok = v && v.ok === true && typeof v.info === "string";
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${v && typeof v.info === "string" ? "  — " + v.info : "  — " + JSON.stringify(v).slice(0, 300)}`);
  if (ok) pass++; else fail++;
  return { ok };
}
for (const [name, fn, arg] of T) await runTest(name, fn, arg);

// ------------------------------------------------ reload-type controls
// A search-only URL change is a full document navigation. During the reload,
// Runtime.evaluate can return NAVIGATED (context destroyed) or resolve in the
// fresh context — so detect the reload by polling location.search for the new
// value, then poll __diag until the rebuilt scene reports it.
async function runReload(name, driveExpr, urlChangedExpr, pollExpr, pollExpected) {
  const driven = await ev(driveExpr);
  let nav = false;
  for (let i = 0; i < 60 && !nav; i++) {
    await sleep(500);
    const v = await ev(urlChangedExpr);
    if (v === true) nav = true;
  }
  // the reload takes a full scene rebuild; poll until the page reports it
  const settled = nav && await pollUntil(pollExpr, pollExpected);
  console.log(`${nav && settled ? "PASS" : "FAIL"}  ${name}${nav ? (settled ? "  — reloaded, reloaded page reports the new value" : "  — navigated but reloaded page never reported the new value") : "  — no navigation detected: " + JSON.stringify(driven).slice(0, 200)}`);
  if (nav && settled) pass++; else fail++;
  pageErrors.length = 0; // fresh document after reload
}
await runReload(
  "quality low (reload)",
  `(() => { const el = document.getElementById("ui-quality"); el.value = "low"; el.dispatchEvent(new Event("change", {bubbles:true})); return "dispatched"; })()`,
  `(async () => location.search.includes("quality=low"))()`,
  `window.__diag?.ready && window.__diag?.seed === 42 ? window.__diag.quality : "not-ready"`,
  "low",
);
await runReload(
  "regenerate seed (reload)",
  `(() => { document.getElementById("ui-regen").click(); return "dispatched"; })()`,
  "(async () => { const m = location.search.match(/seed=(\\d+)/); return m ? m[1] !== '42' : false; })()",

  `window.__diag?.ready ? true : "not-ready"`,
  true, // reloaded with a different seed
);

// ------------------------------------------------ page errors
const errs = pageErrors;
if (errs.length === 0) { console.log("PASS  no page console errors / exceptions"); pass++; }
else { console.log(`FAIL  ${errs.length} page error(s):\n  ` + errs.slice(0, 10).map(e => e.slice(0, 200)).join("\n  ")); fail++; }

console.log(`\n${pass + fail} checks: ${pass} passed, ${fail} failed`);
chrome.kill(); server.close();
process.exit(fail === 0 ? 0 : 1);
