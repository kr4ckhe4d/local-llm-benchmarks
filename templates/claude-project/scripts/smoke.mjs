#!/usr/bin/env node
// Runtime smoke test for a built static site, with text-only output.
//
// Static checks (typecheck, lint, unit tests, build) can all pass while the
// page throws on load or leaves content hidden. A text-only model cannot look
// at screenshots, so this loads dist/ in headless Chrome over the DevTools
// protocol and reports problems as text. No dependencies: Node's built-in
// http server and WebSocket, and the system Chrome.
//
//   npm run build && node scripts/smoke.mjs            exit 1 if any FAIL
//   node scripts/smoke.mjs --dir dist --wait 1200      options
//   CHROME_BIN=/path/to/chrome node scripts/smoke.mjs  pick the browser
//
// Scenarios: desktop 1440x900, phone 390x844, desktop with reduced motion,
// desktop with JavaScript disabled. In each, every <section> is scrolled into
// view, and the visible part of the page is audited:
//   FAIL  uncaught exception, console.error, failed or 4xx/5xx request
//   FAIL  text that stays invisible (opacity < 0.1, visibility hidden) after
//         its section has been in view for --wait ms
//   FAIL  text contrast under WCAG AA (4.5:1, or 3:1 for large text)
//   FAIL  a position:fixed element drawn far below its CSS top (it should be
//         at its top, or moved off screen upwards)
//   FAIL  horizontal overflow (page wider than the viewport)
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';

const args = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : dflt;
};
const DIST = path.resolve(opt('dir', 'dist'));
const WAIT = Number(opt('wait', 1200));
const MAX_LINES = 60;
// Unique problems across all scenarios: key -> { scenarios, places, items }.
const found = new Map();
const record = (key, scenario, place, item) => {
  if (!found.has(key)) found.set(key, { scenarios: new Set(), places: new Set(), items: new Set() });
  const f = found.get(key);
  f.scenarios.add(scenario); if (place) f.places.add(place); if (item) f.items.add(item);
};

if (!fs.existsSync(path.join(DIST, 'index.html'))) {
  console.error(`smoke: ${DIST}/index.html not found. Run \`npm run build\` first.`);
  process.exit(2);
}

// ---------------------------------------------------------------- server
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.avif': 'image/avif', '.gif': 'image/gif', '.ico': 'image/x-icon',
  '.mp4': 'video/mp4', '.webm': 'video/webm', '.woff2': 'font/woff2', '.woff': 'font/woff', '.txt': 'text/plain' };
const server = http.createServer((req, res) => {
  const url = decodeURIComponent((req.url || '/').split('?')[0]);
  let file = path.join(DIST, url);
  if (!file.startsWith(DIST)) { res.writeHead(403).end(); return; }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
  if (!fs.existsSync(file)) { res.writeHead(404).end('not found'); return; }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}/`;

// ---------------------------------------------------------------- chrome
function findChrome() {
  if (process.env.CHROME_BIN) return process.env.CHROME_BIN;
  for (const c of ['google-chrome-stable', 'google-chrome', 'chromium', 'chromium-browser']) {
    try { return execFileSync('which', [c], { encoding: 'utf8' }).trim(); } catch { /* next */ }
  }
  console.error('smoke: no Chrome/Chromium found; set CHROME_BIN');
  process.exit(2);
}
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'smoke-chrome-'));
const chrome = spawn(findChrome(), [
  '--headless=new', '--ozone-platform=headless', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
  '--in-process-gpu', '--ignore-gpu-blocklist', '--hide-scrollbars', '--no-first-run', '--no-default-browser-check',
  `--user-data-dir=${profile}`, '--remote-debugging-port=0', 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe'] });
const cleanup = () => {
  try { chrome.kill('SIGKILL'); } catch { /* gone */ }
  try { server.close(); } catch { /* closed */ }
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* best effort */ }
};
process.on('exit', cleanup);
const wsUrl = await new Promise((resolve, reject) => {
  let buf = '';
  const t = setTimeout(() => reject(new Error('Chrome did not start within 30 s')), 30000);
  chrome.stderr.on('data', (d) => {
    buf += d;
    const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
    if (m) { clearTimeout(t); resolve(m[1]); }
  });
  chrome.on('exit', (c) => reject(new Error(`Chrome exited with code ${c}`)));
}).catch((e) => { console.error(`smoke: ${e.message}`); process.exit(2); });

// ---------------------------------------------------------------- CDP
const ws = new WebSocket(wsUrl);
await new Promise((r, j) => { ws.onopen = r; ws.onerror = () => j(new Error('cannot connect to Chrome')); });
let nextId = 1;
const pending = new Map();
const listeners = new Set();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(msg.error.message)); else resolve(msg.result);
  } else if (msg.method) listeners.forEach((fn) => fn(msg));
};
const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
  const id = nextId++;
  pending.set(id, { resolve, reject });
  ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Runs in the page. Returns problems in the part of the page now on screen.
const AUDIT = `(() => {
  const out = [];
  const vh = innerHeight, vw = innerWidth;
  const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const over = (top, bottom) => { const a = top[3]; return [0, 1, 2].map((i) => top[i] * a + bottom[i] * (1 - a)).concat(1); };
  const bgOf = (el) => { const layers = []; for (let e = el; e; e = e.parentElement) {
      const c = parse(getComputedStyle(e).backgroundColor); if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; } }
    let col = [255, 255, 255, 1]; for (let i = layers.length - 1; i >= 0; i--) col = over(layers[i], col); return col; };
  const opacityOf = (el) => { let o = 1; for (let e = el; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };
  const label = (el) => { const t = (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ');
    return el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/)[0] : '') + (t ? ' "' + t.slice(0, 50) + '"' : ''); };
  const textEls = [...document.querySelectorAll('h1,h2,h3,h4,p,li,a,button,figcaption,td,th,span,label')]
    .filter((el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && !el.closest('[aria-hidden="true"]'));
  for (const el of textEls) {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1 || r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none') continue;
    const op = opacityOf(el);
    if (op < 0.1 || cs.visibility === 'hidden') { out.push('HIDDEN ' + label(el) + ' (opacity ' + op.toFixed(2) + ', visibility ' + cs.visibility + ')'); continue; }
    const fg = parse(cs.color); if (!fg) continue;
    const bg = bgOf(el); const fgc = over(fg, bg);
    const L1 = lum(fgc), L2 = lum(bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight, 10) >= 700;
    const need = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
    if (ratio < need) out.push('CONTRAST ' + label(el) + ' ' + ratio.toFixed(2) + ':1 (needs ' + need + ':1; color ' + cs.color + ' on ' + 'rgb(' + bg.slice(0, 3).map(Math.round).join(', ') + '))');
  }
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el); if (cs.position !== 'fixed' || cs.display === 'none') continue;
    const r = el.getBoundingClientRect(); if (r.height < 1) continue;
    const top = parseFloat(cs.top);
    if (!isNaN(top) && cs.bottom === 'auto' && r.top > top + 40) out.push('FIXED ' + label(el) + ' drawn at y=' + Math.round(r.top) + ' but CSS top is ' + cs.top);
  }
  if (document.documentElement.scrollWidth > vw + 1) out.push('OVERFLOW page is ' + document.documentElement.scrollWidth + 'px wide in a ' + vw + 'px viewport');
  return out;
})()`;

async function scenario(name, { width, height, mobile = false, reducedMotion = false, noJs = false }) {
  let count = 0;
  const add = (key, place, item) => { count++; record(key, name, place, item); };
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  const s = (m, p) => send(m, p, sessionId);
  let loaded = false;
  const onEvent = (msg) => {
    if (msg.sessionId !== sessionId) return;
    const p = msg.params;
    if (msg.method === 'Runtime.exceptionThrown') {
      const d = p.exceptionDetails;
      add('EXCEPTION ' + (d.exception?.description || d.text).split('\n')[0] + (d.url ? ` (${d.url.replace(BASE, '')}:${d.lineNumber + 1})` : ''));
    } else if (msg.method === 'Runtime.consoleAPICalled' && p.type === 'error') {
      add('CONSOLE.ERROR ' + p.args.map((a) => a.value ?? a.description ?? '').join(' ').slice(0, 200));
    } else if (msg.method === 'Network.responseReceived' && p.response.status >= 400) {
      add(`HTTP ${p.response.status} for requests`, null, p.response.url.replace(BASE, '/'));
    } else if (msg.method === 'Network.loadingFailed' && !p.canceled) {
      add(`REQUEST FAILED ${p.errorText}`);
    } else if (msg.method === 'Page.loadEventFired') loaded = true;
  };
  listeners.add(onEvent);
  await Promise.all(['Runtime.enable', 'Network.enable', 'Page.enable'].map((m) => s(m)));
  await s('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile });
  if (reducedMotion) await s('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
  if (noJs) await s('Emulation.setScriptExecutionDisabled', { value: true });
  await s('Page.navigate', { url: BASE });
  for (let i = 0; i < 100 && !loaded; i++) await sleep(100);
  if (!loaded) add('LOAD page did not fire load within 10 s');
  await sleep(WAIT);
  const evaluate = async (expr) => (await s('Runtime.evaluate', { expression: expr, returnByValue: true })).result.value;
  const audit = async (where) => ((await evaluate(AUDIT)) || []).forEach((x) => add(x, where));
  await audit('top');
  const ids = (await evaluate(`[...document.querySelectorAll('section')].map((s, i) => s.id || ('section ' + (i + 1)))`)) || [];
  for (let i = 0; i < ids.length; i++) {
    const tall = await evaluate(`(() => { const s = document.querySelectorAll('section')[${i}]; const r = s.getBoundingClientRect();
      const top = r.top + scrollY; const span = Math.max(0, s.offsetHeight - innerHeight); return [top, span]; })()`);
    const [top, span] = tall || [0, 0];
    for (const f of span > innerHeightGuard(height) ? [0.25, 0.75] : [0]) {
      await evaluate(`scrollTo(0, ${top + f * span})`);
      await sleep(WAIT);
      await audit(`${ids[i]}${f ? ` ${Math.round(f * 100)}%` : ''}`);
    }
  }
  listeners.delete(onEvent);
  await send('Target.closeTarget', { targetId });
  return count;
}
const innerHeightGuard = (h) => h * 0.5; // only scrub inside sections taller than 1.5 viewports

const scenarios = [
  ['desktop 1440x900', { width: 1440, height: 900 }],
  ['phone 390x844', { width: 390, height: 844, mobile: true }],
  ['desktop, reduced motion', { width: 1440, height: 900, reducedMotion: true }],
  ['desktop, JavaScript disabled', { width: 1440, height: 900, noJs: true }],
];
for (const [name, cfg] of scenarios) {
  const n = await scenario(name, cfg);
  console.log(`== ${name}: ${n ? `${n} finding(s)` : 'clean'}`);
}
const list = (set, max) => { const a = [...set]; return a.slice(0, max).join(', ') + (a.length > max ? `, +${a.length - max} more` : ''); };
let lines = 0;
console.log(found.size ? `\n${found.size} unique problem(s):` : '');
for (const [key, f] of found) {
  if (lines++ >= MAX_LINES) continue;
  const items = f.items.size ? ` (${f.items.size}): ${list(f.items, 5)}` : '';
  const places = f.places.size ? `; at ${list(f.places, 6)}` : '';
  console.log(`FAIL ${key}${items}\n     in: ${[...f.scenarios].join(' | ')}${places}`);
}
if (lines > MAX_LINES) console.log(`... ${lines - MAX_LINES} more unique problem(s) not shown; fix these and run again`);
console.log(found.size ? `smoke: FAILED with ${found.size} unique problem(s)` : 'smoke: all scenarios clean');
ws.close();
cleanup();
process.exit(found.size ? 1 : 0);
