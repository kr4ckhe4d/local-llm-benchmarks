/* RDNA4 LLM Research — static SPA over data.json + docs/*.html + raw/* */
(() => {
  'use strict';
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const app = $('#app');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (v, d = 1) => v == null || isNaN(v) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmtInt = v => v == null ? '—' : Number(v).toLocaleString('en-US');
  const bytes = n => n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB';
  const ctxK = v => v == null ? '—' : (v >= 1024 ? Math.round(v / 1024) + 'K' : v);
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };
  const CORRECTED = '2026-11-05';

  let D = null;              // data.json
  const docCache = {};
  let searchIdx = null;
  const redraws = [];        // charts to re-render on resize

  // ------------------------------------------------------------------ helpers
  const docBySlug = s => D.docs.find(d => d.slug === s);
  const GH = '<svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true" style="vertical-align:-2px"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>';
  const projects = () => D.meta.projects;
  const projById = id => projects().find(p => p.id === id);
  // longest matching prefix wins; the benchmarks repo has the empty prefix
  const projOf = path => [...projects()].sort((a, b) => b.prefix.length - a.prefix.length).find(p => path.startsWith(p.prefix));
  function ghFile(path, isDir) {
    const p = projOf(path); if (!p) return null;
    const rel = path.slice(p.prefix.length).replace(/\/$/, '');
    if (isDir) return `${p.url}/tree/${p.branch}/${rel}`;
    const f = D.files.find(x => x.p === path);
    return f?.g ? `${p.url}/blob/${p.branch}/${rel}` : null;
  }
  const fileHref = p => '#/files/' + p;
  const shortModel = m => m.replace(/-v(\d)$/, ' v$1');

  function cqGroup(r) {
    const p = r.path;
    if (p.includes('/superseded/')) return 'superseded';
    if (p.includes('/fixed-prompts/')) return 'fixed prompts';
    if (p.includes('/strategies/')) return 'strategies';
    if (p.includes('/sweep/')) return 'sampling sweep';
    if (p.includes('/raw/')) return 'raw';
    return 'baseline';
  }
  // prompts were fixed in place on 2026-11-05 ~20:00; fixed-prompts/ holds the reruns
  const cqCorrected = r => r.path.includes('/fixed-prompts/') || (r.date && r.date >= '2026-11-06');
  const isBaseline = r => r.path === `benchmarks/${r.model}/code-quality.txt`;

  function family(m) {
    const l = m.toLowerCase();
    if (l.startsWith('qwen3.8-flash')) return 'Qwen3.8 Flash-Next';
    if (l.startsWith('qwen3.8')) return 'Qwen3.8 27B';
    if (l.startsWith('qwen3.6')) return 'Qwen3.6 35B-A3B';
    if (l.startsWith('qwen3.5')) return 'Qwen3.5';
    if (l.startsWith('qwen3-next')) return 'Qwen3-Next 80B';
    if (l.startsWith('qwen3-coder')) return 'Qwen3-Coder-Next';
    if (l.startsWith('gemma')) return 'Gemma 4';
    if (l.startsWith('laguna')) return 'Laguna XS.2';
    if (l.startsWith('nemotron')) return 'Nemotron 3.5';
    return 'Other';
  }

  // ------------------------------------------------------------------ tooltip
  const tip = $('#tip');
  function showTip(e, html) {
    tip.innerHTML = html; tip.hidden = false;
    const r = tip.getBoundingClientRect();
    let x = e.clientX + 14, y = e.clientY + 14;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
    if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
    tip.style.left = Math.max(8, x) + 'px'; tip.style.top = Math.max(8, y) + 'px';
  }
  const hideTip = () => { tip.hidden = true; };
  const tipRows = (title, rows) => `<b>${esc(title)}</b>` + rows.filter(r => r[1] != null && r[1] !== '').map(([k, v]) => `<div class="r"><span>${esc(k)}</span><span>${esc(v)}</span></div>`).join('');
  function bindTips(root, getter) {
    root.addEventListener('mousemove', e => { const t = e.target.closest('[data-tip]'); if (t) showTip(e, getter(t.dataset.tip)); else hideTip(); });
    root.addEventListener('mouseleave', hideTip);
  }

  // ------------------------------------------------------------------ charts
  /* Horizontal bar chart. rows: {label, value, href, tip(html), dim} */
  function hbar(el, rows, o = {}) {
    const draw = () => {
      const W = Math.max(280, el.clientWidth || 600);
      const rowH = o.rowH || 24, top = 6, bottom = 26;
      const labW = Math.min(o.labW || 210, W * 0.42);
      const valW = 64;
      const H = top + rows.length * rowH + bottom;
      const x0 = labW + 8, x1 = W - valW;
      const vals = rows.map(r => r.value).filter(v => v != null && v > 0);
      let sx, ticks;
      if (o.log) {
        const lo = Math.pow(10, Math.floor(Math.log10(Math.min(...vals)))), hi = Math.pow(10, Math.ceil(Math.log10(Math.max(...vals))));
        sx = v => x0 + (Math.log10(Math.max(v, lo)) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)) * (x1 - x0);
        ticks = []; for (let t = lo; t <= hi * 1.001; t *= 10) ticks.push(t);
      } else {
        const mx = o.max ?? Math.max(...vals) * 1.05;
        sx = v => x0 + (v / mx) * (x1 - x0);
        const step = o.step || niceStep(mx);
        ticks = []; for (let t = 0; t <= mx + 1e-9; t += step) ticks.push(t);
      }
      const tf = o.tickFmt || (v => o.log ? String(v) : fmtInt(v));
      let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(o.title || 'bar chart')}">`;
      for (const t of ticks) { const x = sx(t); s += `<line class="gl" x1="${x}" x2="${x}" y1="${top}" y2="${H - bottom}"/><text class="tick" x="${x}" y="${H - 8}" text-anchor="middle">${tf(t)}</text>`; }
      rows.forEach((r, i) => {
        const y = top + i * rowH, bh = Math.min(14, rowH - 8), by = y + (rowH - bh) / 2;
        const w = r.value == null ? 0 : Math.max(2, sx(r.value) - x0 + (o.log ? 0 : 0));
        const lab = r.label.length > labW / 6.6 ? r.label.slice(0, Math.floor(labW / 6.6) - 1) + '…' : r.label;
        s += `<g class="row" data-tip="${i}" ${r.href ? `data-href="${esc(r.href)}"` : ''}>`;
        s += `<rect class="hit" x="0" y="${y}" width="${W}" height="${rowH}"/>`;
        s += `<text class="lbl" x="${labW}" y="${y + rowH / 2 + 4}" text-anchor="end">${esc(lab)}</text>`;
        if (r.value != null) s += `<path class="bar ${r.cls || ''} ${r.dim ? 'dim' : ''}" d="${roundBar(x0, by, w, bh)}"/>`;
        s += `<text class="val" x="${x0 + w + 6}" y="${y + rowH / 2 + 4}">${esc(r.text ?? (r.value == null ? '—' : fmt(r.value, o.dec ?? 1)))}</text></g>`;
      });
      s += `<line class="base" x1="${x0}" x2="${x0}" y1="${top}" y2="${H - bottom}"/></svg>`;
      el.innerHTML = s;
    };
    el.classList.add('chart');
    draw();
    redraws.push({ el, draw });
    if (!el._bound) {
      el._bound = true;
      bindTips(el, i => rows[i].tip || esc(rows[i].label));
      el.addEventListener('click', e => { const g = e.target.closest('[data-href]'); if (g) location.hash = g.dataset.href; });
    }
  }
  function roundBar(x, y, w, h) { const r = Math.min(4, w / 2, h / 2); return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`; }
  function niceStep(mx) { const raw = mx / 5, p = Math.pow(10, Math.floor(Math.log10(raw))); const n = raw / p; return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * p; }

  /* Dot strip: groups [{label, values:[{v, tip}]}], x 0..max */
  function dotStrip(el, groups, o = {}) {
    const draw = () => {
      const W = Math.max(280, el.clientWidth || 600), rowH = 30, top = 6, bottom = 26;
      const labW = Math.min(170, W * 0.36), x0 = labW + 10, x1 = W - 16, H = top + groups.length * rowH + bottom;
      const lo = o.min ?? 0, hi = o.max ?? 50, sx = v => x0 + (v - lo) / (hi - lo) * (x1 - x0);
      let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(o.title || 'dot plot')}">`;
      for (let t = lo; t <= hi; t += o.step || 5) { const x = sx(t); s += `<line class="gl" x1="${x}" x2="${x}" y1="${top}" y2="${H - bottom}"/><text class="tick" x="${x}" y="${H - 8}" text-anchor="middle">${t}</text>`; }
      groups.forEach((g, i) => {
        const cy = top + i * rowH + rowH / 2;
        s += `<text class="lbl" x="${labW}" y="${cy + 4}" text-anchor="end">${esc(g.label)}</text>`;
        const m = g.values.reduce((a, b) => a + b.v, 0) / g.values.length;
        s += `<line class="meanl" x1="${sx(m)}" x2="${sx(m)}" y1="${cy - 9}" y2="${cy + 9}"/>`;
        const seen = {};
        g.values.forEach((d, j) => {
          const k = d.v; seen[k] = (seen[k] || 0) + 1; const off = (seen[k] - 1) * 5 * (seen[k] % 2 ? 1 : -1);
          s += `<circle class="dot" cx="${sx(d.v)}" cy="${cy + off}" r="5" data-tip="${i}:${j}" ${d.href ? `data-href="${esc(d.href)}"` : ''} style="cursor:pointer"/>`;
        });
      });
      el.innerHTML = s + '</svg>';
    };
    el.classList.add('chart'); draw(); redraws.push({ el, draw });
    if (!el._bound) {
      el._bound = true;
      bindTips(el, k => { const [i, j] = k.split(':').map(Number); return groups[i].values[j].tip; });
      el.addEventListener('click', e => { const g = e.target.closest('[data-href]'); if (g) location.hash = g.dataset.href; });
    }
  }
  let rT; addEventListener('resize', () => { clearTimeout(rT); rT = setTimeout(() => { for (const r of redraws) if (r.el.isConnected) r.draw(); }, 120); });

  // ------------------------------------------------------------------ derived data
  function models() {
    const M = {};
    const get = m => M[m] ??= { model: m, family: family(m), code: [], tput: null, kld: {}, cdn: null, tools: null, fit: null };
    for (const r of D.m.code) if (r.folder !== 'raw') get(r.model).code.push(r);
    for (const r of D.m.throughput) if (r.folder !== 'raw') { const m = get(r.model); if (!m.tput || r.file === 'throughput.txt') m.tput = r; }
    for (const r of D.m.kld) if (r.folder !== 'raw') get(r.model).kld[r.ref] = r;
    for (const r of D.m.cdn) get(r.model).cdn = r;
    for (const r of D.m.tools) get(r.model).tools = r;
    for (const r of D.m.fit) get(r.model).fit = r;
    for (const m of Object.values(M)) {
      m.base = m.code.find(isBaseline) || null;
      m.best = m.code.reduce((a, b) => (!a || b.pass / b.total > a.pass / a.total) && b.total === 50 ? b : a, null);
      m.kldv = m.kld.bf16 || m.kld.q8_0 || null;
    }
    return Object.values(M).sort((a, b) => a.model.localeCompare(b.model));
  }

  // ------------------------------------------------------------------ router
  async function route() {
    hideTip();
    $('#mainnav').classList.remove('open');
    const h = decodeURIComponent(location.hash.slice(1) || '/');
    const [, kind, ...rest] = h.split('/');
    $$('#mainnav a').forEach(a => a.classList.toggle('on', a.dataset.r === (kind || '')));
    const prevKind = app.dataset.kind;
    app.dataset.kind = kind || 'home';
    redraws.length = 0;
    try {
      if (!kind) return home();
      if (kind === 'doc') return doc(rest[0] || 'readme', rest.slice(1).join('/'), prevKind === 'doc');
      if (kind === 'models') return modelsPage();
      if (kind === 'model') return modelPage(rest.join('/'));
      if (kind === 'code') return codePage(rest.join('/'));
      if (kind === 'kld') return kldPage();
      if (kind === 'strata') return strataPage();
      if (kind === 'projects') return projectsPage();
      if (kind === 'files') return filesPage(rest.join('/'), prevKind === 'files');
      app.innerHTML = `<div class="wrap"><div class="empty">Not found. <a href="#/">Back to overview</a></div></div>`;
    } catch (err) {
      console.error(err);
      app.innerHTML = `<div class="wrap"><div class="note">Something went wrong rendering this page: ${esc(err.message)}</div></div>`;
    }
  }
  function setTitle(t) { document.title = t ? `${t} · RDNA4 LLM Research` : 'RDNA4 LLM Research'; }
  const footer = () => `<div class="footer"><span>Built ${esc(D.meta.built.slice(0, 16).replace('T', ' '))} UTC from ${projects().map(p => `<a href="${p.url}" target="_blank" rel="noopener">${esc(p.name)}</a>@<a class="mono" href="${p.url}/commit/${p.commit}" target="_blank" rel="noopener">${esc(p.commit)}</a>`).join(' · ')}</span><span>Every figure measured on one machine; raw evidence under <a href="#/files/benchmarks/">benchmarks/</a>.</span></div>`;

  // ------------------------------------------------------------------ overview
  async function home() {
    setTitle('');
    const M = models();
    const readme = docBySlug('readme');
    const totalWords = D.docs.reduce((a, d) => a + d.words, 0);
    const cqFiles = D.m.code.filter(r => r.folder !== 'raw').length;
    const bestTg = D.m.throughput.reduce((a, b) => b.tg > (a?.tg || 0) ? b : a, null);
    const bestCq = D.m.code.filter(r => r.total === 50).reduce((a, b) => b.pass > (a?.pass || 0) ? b : a, null);
    const bestKld = D.m.kld.filter(r => r.kld > 0 && r.ref === 'bf16').reduce((a, b) => !a || b.kld < a.kld ? b : a, null);

    app.innerHTML = `<div class="wrap">
      <section class="hero">
        <div>
          <div class="eyebrow">Measured, not assumed · ${projects().length} open repositories</div>
          <h1>Local LLMs on AMD RDNA4, benchmarked end to end</h1>
          <p class="lede">Throughput, VRAM fit, GGUF quantization fidelity against BF16, speculative decoding, long-context recall at real depth, executed code quality and tool calling — for every model that ran on this machine under llama.cpp + ROCm. Conclusions link straight to the raw logs they were drawn from.</p>
        </div>
        <div class="hw"><dl>
          <dt>GPUs</dt><dd>RX 9070 XT 16 GB + Radeon AI PRO R9700 32 GB</dd>
          <dt>Architecture</dt><dd>RDNA4 / gfx1201, PCIe 5.0 x8 each</dd>
          <dt>Host</dt><dd>Ryzen 7 9800X3D, 32 GB DDR5-6000</dd>
          <dt>Stack</dt><dd>CachyOS, ROCm 7.2, llama.cpp b11434</dd>
        </dl></div>
      </section>
      <div class="tiles">
        <div class="tile"><div class="v">${bestTg ? fmt(bestTg.tg, 0) : '—'}<small>tok/s</small></div><div class="k">Fastest generation probe</div><div class="s">${esc(bestTg?.model || '')}</div></div>
        <div class="tile"><div class="v">${bestCq ? bestCq.pass : '—'}<small>/ 50</small></div><div class="k">Best code-quality run</div><div class="s">${esc(bestCq ? bestCq.model + ' · ' + bestCq.label : '')}</div></div>
        <div class="tile"><div class="v">${bestKld ? bestKld.kld.toFixed(4) : '—'}</div><div class="k">Lowest KLD vs BF16</div><div class="s">${esc(bestKld?.model || '')}</div></div>
        <div class="tile"><div class="v">${M.length}</div><div class="k">Model builds probed</div><div class="s">${cqFiles} code-quality runs scored</div></div>
        <div class="tile"><div class="v">${D.docs.length}</div><div class="k">Research write-ups</div><div class="s">${fmtInt(Math.round(totalWords / 1000))}K words</div></div>
        <div class="tile"><div class="v">${fmtInt(D.files.length)}</div><div class="k">Raw evidence files</div><div class="s">logs, answers, scripts</div></div>
      </div>

      <div class="section-h"><h2>Research projects</h2><a href="#/projects">All projects →</a></div>
      ${projectCards()}

      <div class="section-h"><h2>Headline results</h2><a href="#/doc/readme/headline-results-two-cards-2026-10">Read in context →</a></div>
      <div class="headline" id="headline"><div class="loading">Loading…</div></div>

      <div class="section-h"><h2>The numbers</h2><a href="#/models">All models →</a></div>
      <div class="grid2">
        <div class="card"><h3>Generation speed</h3><p class="sub">700-token code prompt, temperature 0, mean of 3 runs (tok/s). Single-card probe unless the file says otherwise.</p><div class="legend"><span><i style="background:var(--s1)"></i>llama.cpp, 700-token probe</span><span><i style="background:var(--s2)"></i>Strata engine, its own 6-prompt sweep</span></div><div id="c-tg"></div><div class="foot">Faded: partial CPU offload. Hover for setup and MTP draft acceptance; click for the model.</div></div>
        <div class="card"><h3>Code quality, baseline run</h3><p class="sub">Checks passed out of 50: the model reimplements 7 stdlib functions, scored by differential execution.</p><div id="c-cq"></div><div class="foot">Faded bars ran on the prompts before the ${CORRECTED} fix and can be up to 2 checks low.</div></div>
        <div class="card"><h3>Quantization fidelity: Qwen3.8-27B</h3><p class="sub">Mean KL divergence against the BF16 reference on wiki.test (log scale, lower is better).</p><div id="c-kld"></div><div class="foot"><a href="#/kld">KLD tables and the Q8_0-reference runs →</a></div></div>
        <div class="card"><h3>Sampling is noise: Qwen3.8-27B Q8_0</h3><p class="sub">Code-quality score per run at each sampler setting (dots), mean (tick). Temp 0 repeats exactly.</p><div id="c-sweep"></div><div class="foot"><a href="#/code">Every run, every task →</a></div></div>
      </div>

      <div class="section-h"><h2>Findings in the main write-up</h2><a href="#/doc/readme">Open README →</a></div>
      <div class="doccards">${readme.toc.filter(t => t.level === 2).map(t => `<a class="doccard" href="#/doc/readme/${esc(t.id)}"><b>${esc(t.title)}</b><span>README §</span></a>`).join('')}</div>

      ${projects().map(p => `<div class="section-h"><h2>${esc(p.title)}: write-ups</h2><a href="${p.url}" target="_blank" rel="noopener">${GH} ${esc(p.repo)}</a></div>
      <div class="doccards">${D.docs.filter(d => d.project === p.id).map(d => `<a class="doccard" href="#/doc/${d.slug}"><b>${esc(d.title)}</b><span>${esc(d.path)} · ${Math.max(1, Math.round(d.words / 230))} min read</span></a>`).join('')}</div>`).join('')}
      ${footer()}</div>`;

    // charts
    const tput = [...D.m.throughput].filter(r => r.folder !== 'raw' && (r.file === 'throughput.txt' || r.engine)).sort((a, b) => b.tg - a.tg);
    hbar($('#c-tg'), tput.map(r => ({
      label: shortModel(r.model), value: r.tg, href: '#/model/' + r.model, dim: !!r.note, cls: r.engine ? 'alt' : '',
      tip: tipRows(r.model, [['engine', r.engine ? 'Strata' : 'llama.cpp'], ['probe', r.probe], ['note', r.note], ['generation', fmt(r.tg, 1) + ' tok/s'], ['prefill', r.pp ? fmt(r.pp, 0) + ' tok/s' : null], ['MTP draft accept', r.draft ? r.draft + '%' : null], ['VRAM', r.vram ? fmtInt(r.vram) + ' MiB' : null], ['ctx', r.ctx], ['flags', r.flags], ['build', r.build], ['date', r.date.slice(0, 10)]]),
    })), { title: 'generation tok/s', dec: 1 });
    const base = M.filter(m => m.base).map(m => m.base).sort((a, b) => b.pass - a.pass);
    hbar($('#c-cq'), base.map(r => ({
      label: shortModel(r.model), value: r.pass, text: `${r.pass}/50`, href: '#/model/' + r.model, dim: !cqCorrected(r),
      tip: tipRows(r.model, [['score', `${r.pass}/${r.total}`], ['tasks fully clean', `${r.clean}/${r.ntasks}`], ['prompts', cqCorrected(r) ? 'corrected' : 'old (≤2 low)'], ...r.tasks.map(t => [t.task, `${t.pass}/${t.total}`]), ['date', r.date.slice(0, 10)]]),
    })), { max: 50, step: 10, title: 'code quality' });
    const k = D.m.kld.filter(r => r.ref === 'bf16' && r.kld > 0 && r.model.startsWith('qwen3.8-27B')).sort((a, b) => a.kld - b.kld);
    hbar($('#c-kld'), k.map(r => ({
      label: r.model.replace('qwen3.8-27B-', ''), value: r.kld, text: r.kld.toFixed(4), href: fileHref(r.path),
      tip: tipRows(r.model, [['mean KLD', r.kld.toFixed(6)], ['99th pct KLD', r.kld99], ['same top token', r.same_top + '%'], ['PPL ratio', r.ppl_ratio], ['RMS Δp', r.rms_dp + '%']]),
    })), { log: true, title: 'KLD', tickFmt: v => String(v) });
    const sw = D.m.code.filter(r => r.model === 'qwen3.8-27B-Q8_0' && (r.path.includes('/sweep/') || r.path.includes('/minp/')) && r.total === 50);
    const groups = {};
    for (const r of sw) { const g = r.label.replace(/-run\d+$/, '').replace(/-repeat$/, ' repeat'); (groups[g] ??= []).push(r); }
    dotStrip($('#c-sweep'), Object.entries(groups).sort((a, b) => a[0].localeCompare(b[0], undefined, { numeric: true })).map(([g, rs]) => ({
      label: g, values: rs.map(r => ({ v: r.pass, href: fileHref(r.path), tip: tipRows(r.label, [['score', `${r.pass}/50`], ['clean tasks', `${r.clean}/7`], ...r.tasks.map(t => [t.task, `${t.pass}/${t.total}`])]) })),
    })), { min: 25, max: 50, step: 5, title: 'sampling sweep' });

    // headline table from README
    const html = await loadDoc('readme');
    const tmp = document.createElement('div'); tmp.innerHTML = html;
    const h = tmp.querySelector('#headline-results-two-cards-2026-10');
    let n = h?.nextElementSibling, out = '';
    while (n && !/^H[12]$/.test(n.tagName)) { out += n.outerHTML; n = n.nextElementSibling; }
    const el = $('#headline'); if (el) el.innerHTML = `<div class="prose">${out}</div>`;
  }

  // ------------------------------------------------------------------ docs
  async function loadDoc(slug) {
    if (!docCache[slug]) {
      const r = await fetch(`docs/${slug}.html`);
      if (!r.ok) throw new Error('doc not found: ' + slug);
      docCache[slug] = await r.text();
    }
    return docCache[slug];
  }
  let spy = null;
  async function doc(slug, anchor, same) {
    const d = docBySlug(slug);
    if (!d) { app.innerHTML = `<div class="wrap"><div class="empty">No such document.</div></div>`; return; }
    setTitle(d.title);
    if (same && app.dataset.doc === slug) { scrollToAnchor(anchor); return; }
    app.dataset.doc = slug;
    const html = await loadDoc(slug);
    const i = D.docs.indexOf(d), prev = D.docs[i - 1], next = D.docs[i + 1];
    const touched = d.links && d.links.length ? `<span>·</span><span>evidence: ${d.links.slice(0, 6).map(l => `<a href="#/files/benchmarks/${esc(l)}/">${esc(l)}</a>`).join(', ')}${d.links.length > 6 ? ` +${d.links.length - 6}` : ''}</span>` : '';
    app.innerHTML = `<div class="docs">
      <nav class="docnav">${projects().map(p => `<div class="navh" style="margin-top:14px">${esc(p.name)}</div>${D.docs.filter(x => x.project === p.id).map(x => `<a href="#/doc/${x.slug}" class="${x.slug === slug ? 'on' : ''}">${esc(x.title.replace(/ — .*/, '').replace(/: .{30,}$/, ''))}<small>${esc(x.path.slice(p.prefix.length))}</small></a>`).join('')}`).join('')}</nav>
      <article class="article">
        <div class="docmeta"><span class="mono">${esc(d.path)}</span><span>·</span><span>${fmtInt(d.words)} words · ${Math.max(1, Math.round(d.words / 230))} min</span>${touched}<span style="margin-left:auto;display:flex;gap:6px"><a class="btn" href="#/projects">${esc(projById(d.project)?.name || '')}</a>${d.gh ? `<a class="btn" href="${esc(d.gh)}" target="_blank" rel="noopener">${GH} GitHub</a>` : ''}<a class="btn" href="raw/${esc(d.path)}" target="_blank">Markdown</a></span></div>
        <div class="prose" id="prose">${html}</div>
        <div class="pager">${prev ? `<a href="#/doc/${prev.slug}"><small>← Previous</small>${esc(prev.title)}</a>` : '<span></span>'}${next ? `<a href="#/doc/${next.slug}"><small>Next →</small>${esc(next.title)}</a>` : '<span></span>'}</div>
        ${footer()}
      </article>
      <nav class="doctoc" id="toc"><div class="navh">On this page</div>${d.toc.map(t => `<a class="l${t.level}" href="#/doc/${slug}/${esc(t.id)}" data-id="${esc(t.id)}">${esc(t.title)}</a>`).join('')}</nav>
    </div>`;
    const prose = $('#prose');
    $$('h2[id],h3[id],h4[id]', prose).forEach(h => h.insertAdjacentHTML('afterbegin', `<a class="anchor" href="#/doc/${slug}/${esc(h.id)}" aria-hidden="true">#</a>`));
    if (window.hljs) $$('pre code', prose).forEach(c => { try { hljs.highlightElement(c); } catch (e) { /* unknown lang */ } });
    // scrollspy
    if (spy) spy.disconnect();
    const links = Object.fromEntries($$('#toc a').map(a => [a.dataset.id, a]));
    let active = null;
    spy = new IntersectionObserver(es => {
      for (const e of es) if (e.isIntersecting && links[e.target.id]) {
        active?.classList.remove('on'); active = links[e.target.id]; active.classList.add('on');
        const toc = $('#toc'); if (toc && (active.offsetTop < toc.scrollTop || active.offsetTop > toc.scrollTop + toc.clientHeight - 40)) toc.scrollTop = active.offsetTop - 120;
      }
    }, { rootMargin: '-60px 0px -75% 0px' });
    $$('h2[id],h3[id],h4[id]', prose).forEach(h => spy.observe(h));
    const nav = $('.docnav a.on'); if (nav) nav.scrollIntoView({ block: 'nearest' });
    scrollToAnchor(anchor);
  }
  function scrollToAnchor(anchor) {
    if (!anchor) { scrollTo(0, 0); return; }
    const el = document.getElementById(anchor);
    if (!el) { scrollTo(0, 0); return; }
    requestAnimationFrame(() => { el.scrollIntoView({ block: 'start' }); el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); });
  }

  // ------------------------------------------------------------------ models
  function sortableTable(el, cols, rows, initial) {
    let key = initial?.key ?? cols[0].key, dir = initial?.dir ?? 'asc';
    const render = () => {
      const c = cols.find(c => c.key === key);
      const sv = r => c.sort ? c.sort(r) : r[key];
      const sorted = [...rows].sort((a, b) => {
        const x = sv(a), y = sv(b);
        if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
        const r = typeof x === 'string' ? x.localeCompare(y) : x - y;
        return dir === 'asc' ? r : -r;
      });
      el.innerHTML = `<div class="tbl"><table><thead><tr>${cols.map(c => `<th class="sort ${c.n ? 'n' : ''}" data-k="${c.key}" ${c.key === key ? `data-dir="${dir}"` : ''} title="${esc(c.title || '')}">${esc(c.label)}</th>`).join('')}</tr></thead><tbody>${sorted.map(r => `<tr>${cols.map(c => { const v = c.html(r); return `<td class="${c.n ? (v === '—' ? 'na' : 'n') : ''}">${v}</td>`; }).join('')}</tr>`).join('')}</tbody></table></div>`;
      $$('th.sort', el).forEach(th => th.onclick = () => { const k = th.dataset.k; if (k === key) dir = dir === 'asc' ? 'desc' : 'asc'; else { key = k; dir = cols.find(c => c.key === k).n ? 'desc' : 'asc'; } render(); });
    };
    render();
  }

  function modelsPage() {
    setTitle('Models');
    const M = models();
    const fams = [...new Set(M.map(m => m.family))].sort();
    app.innerHTML = `<div class="wrap">
      <div class="page-h"><h1>Models</h1><p>Every model folder under <a href="#/files/benchmarks/">benchmarks/</a>, with the figures parsed straight out of its probe files. Click a column to sort, a model for its full record. Dashes mean the probe wasn't run for that build.</p></div>
      <div class="filters"><select id="fam"><option value="">All families</option>${fams.map(f => `<option>${esc(f)}</option>`).join('')}</select>
      <input type="search" id="mq" placeholder="Filter models…"><span class="count" id="mcount"></span></div>
      <div id="mt"></div>
      <div class="note" style="margin-top:18px">Throughput rows come from the probe run for that folder — single-card setups for most, so they don't match the two-card headline numbers. Code-quality baselines dated before ${CORRECTED} used two prompts that contradicted the stdlib and can be up to 2 checks low (see <a href="#/doc/benchmarks-readme/the-two-probes-that-had-to-be-rebuilt">benchmarks/README</a>).</div>
      ${footer()}</div>`;
    const cols = [
      { key: 'model', label: 'Model', html: m => `<a href="#/model/${esc(m.model)}">${esc(m.model)}</a>` },
      { key: 'family', label: 'Family', html: m => `<span class="pill">${esc(m.family)}</span>${m.model.endsWith('-strata') ? ' <a class="pill" href="#/strata">Strata</a>' : ''}` },
      { key: 'tg', label: 'Gen tok/s', n: 1, sort: m => m.tput?.tg, html: m => m.tput ? fmt(m.tput.tg, 1) : '—' },
      { key: 'pp', label: 'Prefill tok/s', n: 1, sort: m => m.tput?.pp, html: m => m.tput?.pp ? fmt(m.tput.pp, 0) : '—' },
      { key: 'draft', label: 'MTP accept', n: 1, sort: m => m.tput?.draft, html: m => m.tput?.draft ? m.tput.draft + '%' : '—' },
      { key: 'kld', label: 'Mean KLD', n: 1, title: 'vs BF16, or vs Q8_0 where BF16 did not fit', sort: m => m.kldv?.kld, html: m => m.kldv ? `${m.kldv.kld.toFixed(4)}${m.kld.bf16 ? '' : ' <span class="pill">q8 ref</span>'}` : '—' },
      { key: 'cq', label: 'Code (baseline)', n: 1, sort: m => m.base?.pass, html: m => m.base ? `${m.base.pass}/50${cqCorrected(m.base) ? '' : ' <span class="pill warn" title="old prompts">old</span>'}<span class="minibar" style="width:${m.base.pass * 0.9}px"></span>` : '—' },
      { key: 'best', label: 'Code (best run)', n: 1, sort: m => m.best?.pass, html: m => m.best ? `<a href="${fileHref(m.best.path)}" title="${esc(m.best.label)}">${m.best.pass}/50</a>` : '—' },
      { key: 'runs', label: 'Runs', n: 1, sort: m => m.code.length, html: m => m.code.length ? `<a href="#/code/${esc(m.model)}">${m.code.length}</a>` : '—' },
      { key: 'tools', label: 'Tool calls', sort: m => m.tools ? (m.tools.ok ? 1 : 0) : null, html: m => m.tools ? `<a href="${fileHref(m.tools.path)}"><span class="pill ${m.tools.ok ? 'ok' : 'bad'}">${m.tools.ok ? '✓' : '✗'} ${m.tools.single ?? '?'} + ${m.tools.parallel ?? '?'}</span></a>` : '—' },
      { key: 'cdn', label: 'URLs live', n: 1, sort: m => m.cdn?.pct, html: m => m.cdn ? `${m.cdn.pct}%` : '—' },
      { key: 'fit', label: 'Max ctx', n: 1, sort: m => m.fit?.max_ctx, html: m => m.fit ? ctxK(m.fit.max_ctx) : '—' },
    ];
    const draw = () => {
      const f = $('#fam').value, q = $('#mq').value.toLowerCase();
      const rows = M.filter(m => (!f || m.family === f) && (!q || m.model.toLowerCase().includes(q)));
      $('#mcount').textContent = `${rows.length} of ${M.length}`;
      sortableTable($('#mt'), cols, rows, { key: 'tg', dir: 'desc' });
    };
    $('#fam').onchange = draw; $('#mq').oninput = draw; draw();
  }

  function modelPage(name) {
    const m = models().find(x => x.model === name);
    if (!m) { app.innerHTML = `<div class="wrap"><div class="empty">Unknown model ${esc(name)}. <a href="#/models">All models</a></div></div>`; return; }
    setTitle(name);
    const files = D.files.filter(f => f.p.startsWith(`benchmarks/${name}/`) || f.p.startsWith(`benchmarks/q8ref/${name}/`));
    const docs = D.docs.filter(d => d.links.includes(name));
    const t = m.tput, k = m.kldv, b = m.base;
    const runs = [...m.code].sort((a, b) => b.pass - a.pass);
    app.innerHTML = `<div class="wrap">
      <div class="page-h"><div class="eyebrow"><a href="#/models">Models</a> / ${esc(m.family)}</div><h1 style="word-break:break-word">${esc(name)}</h1>
      <p>${t?.gguf || b?.gguf ? `<span class="mono">${esc(t?.gguf || b?.gguf)}</span>` : ''}${t?.flags ? ` · flags <code>${esc(t.flags)}</code>` : ''}${t?.ctx ? ` · ctx ${esc(t.ctx)}` : ''}</p></div>
      <div class="tiles">
        <div class="tile"><div class="v">${t ? fmt(t.tg, 1) : '—'}<small>tok/s</small></div><div class="k">Generation</div><div class="s">${t?.engine ? 'Strata, production config' : t?.draft ? `MTP accept ${t.draft}%` : t ? 'mean of ' + t.tg_runs.length + ' runs' : 'not probed'}</div></div>
        <div class="tile"><div class="v">${t?.pp ? fmt(t.pp, 0) : '—'}<small>tok/s</small></div><div class="k">Prefill</div><div class="s">${t?.vram ? fmtInt(t.vram) + ' MiB VRAM' : ''}</div></div>
        <div class="tile"><div class="v">${k ? k.kld.toFixed(4) : '—'}</div><div class="k">Mean KLD</div><div class="s">${k ? `vs ${k.ref.toUpperCase()} · top-1 same ${k.same_top}%` : 'not measured'}</div></div>
        <div class="tile"><div class="v">${b ? b.pass : '—'}<small>/ 50</small></div><div class="k">Code quality (baseline)</div><div class="s">${b ? (cqCorrected(b) ? 'corrected prompts' : 'old prompts') : ''}${m.best && m.best !== b ? ` · best ${m.best.pass}` : ''}</div></div>
        <div class="tile"><div class="v">${m.cdn ? m.cdn.pct + '%' : '—'}</div><div class="k">Emitted URLs that resolve</div><div class="s">${m.cdn ? `${m.cdn.ok}/${m.cdn.total}` : ''}</div></div>
        <div class="tile"><div class="v">${m.fit ? ctxK(m.fit.max_ctx) : '—'}</div><div class="k">Largest context that fit</div><div class="s">${m.fit ? 'from fit.txt' : ''}</div></div>
      </div>
      ${name.endsWith('-strata') ? `<div class="note">Runs on the Strata engine, not llama.cpp. ${t?.probe ? esc(t.probe) + '. ' : ''}<a href="#/strata">Strata tuning, card split and expert-mode results →</a></div>` : ''}
      ${b ? `<div class="card"><h3>Code quality by task (baseline)</h3><p class="sub"><a href="${fileHref(b.path)}">${esc(b.path)}</a></p><div id="c-task"></div></div>` : ''}
      ${runs.length > 1 ? `<div class="section-h"><h2>All ${runs.length} code-quality runs</h2><a href="#/code/${esc(name)}">Task matrix →</a></div><div id="c-runs" class="card"></div>` : ''}
      ${docs.length ? `<div class="section-h"><h2>Discussed in</h2></div><div class="doccards">${docs.map(d => `<a class="doccard" href="#/doc/${d.slug}"><b>${esc(d.title)}</b><span>${esc(d.path)}</span></a>`).join('')}</div>` : ''}
      <div class="section-h"><h2>Files (${files.length})</h2><a href="#/files/benchmarks/${esc(name)}/">Browse folder →</a></div>
      ${fileTable(files.slice(0, 200))}
      ${footer()}</div>`;
    if (b) hbar($('#c-task'), b.tasks.map(x => ({ label: x.task, value: x.pass / x.total * 100, text: `${x.pass}/${x.total}`, tip: tipRows(x.task, [['passed', `${x.pass}/${x.total}`], ['missed', x.missed.join(', ') || 'none']]) })), { max: 100, step: 25, tickFmt: v => v + '%' });
    if (runs.length > 1) hbar($('#c-runs'), runs.map(r => ({ label: r.label + (r.total !== 50 ? ` (${r.total})` : ''), value: r.pass / r.total * 50, text: `${r.pass}/${r.total}`, href: fileHref(r.path), dim: !cqCorrected(r), tip: tipRows(r.label, [['group', cqGroup(r)], ['score', `${r.pass}/${r.total}`], ['clean tasks', `${r.clean}/${r.ntasks}`], ['prompts', cqCorrected(r) ? 'corrected' : 'old'], ['file', r.path.split('/').slice(2).join('/')]]) })), { max: 50, step: 10, labW: 240 });
  }

  function fileTable(files) {
    if (!files.length) return '<div class="empty">No files.</div>';
    return `<div class="tbl"><table class="dirlist"><thead><tr><th>File</th><th>Model / probe</th><th>Date</th><th class="n">Size</th></tr></thead><tbody>${files.map(f => `<tr><td><a href="${fileHref(f.p)}">${esc(f.p.split('/').slice(1).join('/'))}</a></td><td class="mono">${esc(f.h?.model || '')}</td><td class="mono">${esc((f.h?.date || '').slice(0, 10))}</td><td class="n">${bytes(f.s)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  // ------------------------------------------------------------------ code quality lab
  function codePage(pre) {
    setTitle('Code quality');
    const all = D.m.code.filter(r => r.folder !== 'raw');
    const tasks = ['glob_match', 'shlex_split', 'urljoin', 'textwrap', 'csv_rows', 'add_months', 'parse_qsl'];
    const ms = [...new Set(all.map(r => r.model))].sort();
    const groups = ['baseline', 'fixed prompts', 'strategies', 'sampling sweep', 'superseded'];
    app.innerHTML = `<div class="wrap">
      <div class="page-h"><h1>Code quality lab</h1><p>Each run asks the model to reimplement seven Python stdlib behaviours from scratch; its function is executed against the real one over edge cases and a seeded random batch. ${all.length} scored runs across ${ms.length} model builds — baselines, sampler sweeps, prompting strategies and oracle-select harnesses.</p></div>
      <div class="note">Two task prompts (shlex, textwrap) contradicted the stdlib until ${CORRECTED}; runs before that date can be up to 2 checks low on <code>dq_escapes</code> and <code>collapse</code>. <a href="#/doc/benchmarks-readme/the-two-probes-that-had-to-be-rebuilt">Why</a>.</div>
      <div class="filters">
        <select id="cm"><option value="">All models</option>${ms.map(m => `<option ${m === pre ? 'selected' : ''}>${esc(m)}</option>`).join('')}</select>
        <div class="seg" id="cg"><button data-g="" class="on">All</button>${groups.map(g => `<button data-g="${g}">${g}</button>`).join('')}</div>
        <label><input type="checkbox" id="cfull" checked> 50-check runs only</label>
        <input type="search" id="cq" placeholder="Filter by run label…">
        <span class="count" id="ccount"></span>
      </div>
      <div class="seqlegend" style="margin-bottom:10px">share of a task's checks passed: <i style="background:var(--seq-0)"></i>0 <i style="background:var(--seq-1)"></i><i style="background:var(--seq-2)"></i><i style="background:var(--seq-3)"></i><i style="background:var(--seq-4)"></i><i style="background:var(--seq-5)"></i><i style="background:var(--seq-6)"></i>all · hover a cell for the missed checks</div>
      <div id="heat"></div>
      <div class="grid2" style="margin-top:20px">
        <div class="card"><h3>Hardest checks</h3><p class="sub">How often each check was missed across the runs shown.</p><div id="c-miss"></div></div>
        <div class="card"><h3>Pass rate by task</h3><p class="sub">Mean share of checks passed across the runs shown.</p><div id="c-taskavg"></div></div>
      </div>
      ${footer()}</div>`;
    let g = '';
    $$('#cg button').forEach(b => b.onclick = () => { $$('#cg button').forEach(x => x.classList.toggle('on', x === b)); g = b.dataset.g; draw(); });
    const draw = () => {
      const m = $('#cm').value, q = $('#cq').value.toLowerCase(), full = $('#cfull').checked;
      const rows = all.filter(r => (!m || r.model === m) && (!g || cqGroup(r) === g) && (!full || r.total === 50) && (!q || (r.label + ' ' + r.path).toLowerCase().includes(q))).sort((a, b) => b.pass / b.total - a.pass / a.total || a.model.localeCompare(b.model));
      $('#ccount').textContent = `${rows.length} runs`;
      const cell = (r, t) => {
        const x = r.tasks.find(y => y.task === t); if (!x) return '<td class="c l0">—</td>';
        const f = x.pass / x.total, l = f === 1 ? 6 : f === 0 ? 0 : Math.min(5, 1 + Math.floor(f * 5));
        return `<td class="c l${l}" data-tip="${esc(JSON.stringify([r.label, t, x.pass, x.total, x.missed, x.note || '']))}">${x.pass}/${x.total}</td>`;
      };
      $('#heat').innerHTML = rows.length ? `<div class="tbl heat"><table><thead><tr><th>Run</th><th>Group</th><th class="n">Score</th>${tasks.map(t => `<th style="text-align:center">${t}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr><td class="run"><a href="${fileHref(r.path)}">${esc(r.label)}</a><small>${esc(r.model)} · ${esc(r.date.slice(0, 10))}${cqCorrected(r) ? '' : ' · old prompts'}</small></td><td><span class="pill">${esc(cqGroup(r))}</span></td><td class="n"><b>${r.pass}</b>/${r.total}</td>${tasks.map(t => cell(r, t)).join('')}</tr>`).join('')}</tbody></table></div>` : '<div class="empty">No runs match.</div>';
      const miss = {}, avg = {};
      for (const r of rows) for (const x of r.tasks) { for (const c of x.missed) miss[`${x.task}.${c}`] = (miss[`${x.task}.${c}`] || 0) + 1; (avg[x.task] ??= []).push(x.pass / x.total); }
      const top = Object.entries(miss).sort((a, b) => b[1] - a[1]).slice(0, 14);
      const mc = $('#c-miss'); mc._bound = false; mc.replaceWith(mc.cloneNode()); // reset listeners
      const tc = $('#c-taskavg'); tc.replaceWith(tc.cloneNode());
      redraws.length = 0;
      if (top.length) hbar($('#c-miss'), top.map(([k, v]) => ({ label: k, value: v, text: `${v} of ${rows.length}`, tip: tipRows(k, [['missed in', `${v} runs`], ['share', Math.round(v / rows.length * 100) + '%']]) })), { labW: 190, dec: 0 }); else $('#c-miss').innerHTML = '<div class="empty">No misses.</div>';
      if (rows.length) hbar($('#c-taskavg'), tasks.filter(t => avg[t]).map(t => { const v = avg[t].reduce((a, b) => a + b, 0) / avg[t].length * 100; return { label: t, value: v, text: Math.round(v) + '%', tip: tipRows(t, [['mean pass rate', v.toFixed(1) + '%'], ['runs', avg[t].length]]) }; }).sort((a, b) => a.value - b.value), { max: 100, step: 25, tickFmt: v => v + '%' });
      if (pre !== m) history.replaceState(null, '', '#/code' + (m ? '/' + m : ''));
    };
    bindTips($('#heat'), s => { const [l, t, p, n, mi, note] = JSON.parse(s); return tipRows(`${l} · ${t}`, [['passed', `${p}/${n}`], ['missed', mi.join(', ') || 'none']]) + (note ? `<div style="margin-top:6px;color:var(--ink-2);font-family:var(--mono);font-size:11px">${esc(note)}</div>` : ''); });
    $('#cm').onchange = draw; $('#cq').oninput = draw; $('#cfull').onchange = draw; draw();
  }

  // ------------------------------------------------------------------ KLD
  function kldPage() {
    setTitle('Quant fidelity');
    const rows = D.m.kld.filter(r => r.kld > 0);
    app.innerHTML = `<div class="wrap">
      <div class="page-h"><h1>Quantization fidelity</h1><p>KL divergence of each GGUF quant's next-token distribution against an unquantised reference, over 200 × 512-token chunks of wiki.test. Mean KLD is the headline; the 99th percentile shows how bad the tail gets; "same top" is how often the quant picks the reference's argmax token. BF16 stopped fitting the 32 GB host, so later runs use a Q8_0 reference, which reproduces BF16 figures within 1.5% (<a href="#/doc/gsq-rco">gsq-rco.md</a>).</p></div>
      <div class="filters"><div class="seg" id="kr"><button data-r="bf16" class="on">vs BF16</button><button data-r="q8_0">vs Q8_0</button><button data-r="">All</button></div><span class="count" id="kcount"></span></div>
      <div class="grid2"><div class="card"><h3>Mean KLD</h3><p class="sub">Log scale; lower is closer to the reference.</p><div id="c-k1"></div></div>
      <div class="card"><h3>Top-token agreement</h3><p class="sub">Share of positions where the quant's top token matches the reference's.</p><div id="c-k2"></div></div></div>
      <div id="kt" style="margin-top:16px"></div>
      <div class="note">The BF16-control row (KLD 0) confirms the harness: BF16 scored against itself is identical. Excluded from charts.</div>
      ${footer()}</div>`;
    let ref = 'bf16';
    const draw = () => {
      const rs = rows.filter(r => !ref || r.ref === ref).sort((a, b) => a.kld - b.kld);
      $('#kcount').textContent = `${rs.length} measurements`;
      const lab = r => (r.folder === 'raw' ? r.model.replace('raw/', '') : r.model).replace('qwen3.8-27B-', 'Q3.8-27B ').replace('qwen3.6-35B-A3B-', 'Q3.6-35B ');
      redraws.length = 0;
      for (const id of ['#c-k1', '#c-k2']) { const c = $(id); c.replaceWith(c.cloneNode()); }
      const tipOf = r => tipRows(r.model, [['reference', r.ref], ['mean KLD', r.kld.toFixed(6)], ['median KLD', r.median], ['99th pct KLD', r.kld99], ['same top token', r.same_top + '%'], ['PPL(Q)/PPL(base)', r.ppl_ratio], ['RMS Δp', r.rms_dp + '%'], ['date', r.date.slice(0, 10)]]);
      hbar($('#c-k1'), rs.map(r => ({ label: lab(r) + (ref ? '' : ` (${r.ref})`), value: r.kld, text: r.kld.toFixed(4), href: fileHref(r.path), tip: tipOf(r) })), { log: true, labW: 200, tickFmt: v => String(v) });
      const rs2 = [...rs].sort((a, b) => b.same_top - a.same_top);
      hbar($('#c-k2'), rs2.map(r => ({ label: lab(r) + (ref ? '' : ` (${r.ref})`), value: r.same_top, text: r.same_top.toFixed(1) + '%', href: fileHref(r.path), tip: tipOf(r) })), { max: 100, step: 20, labW: 200, tickFmt: v => v + '%' });
      sortableTable($('#kt'), [
        { key: 'model', label: 'Quant', html: r => `<a href="${fileHref(r.path)}">${esc(r.model)}</a>` },
        { key: 'ref', label: 'Reference', html: r => `<span class="pill">${esc(r.ref)}</span>` },
        { key: 'kld', label: 'Mean KLD', n: 1, html: r => r.kld.toFixed(6) },
        { key: 'median', label: 'Median', n: 1, html: r => r.median?.toFixed(6) ?? '—' },
        { key: 'kld99', label: '99% KLD', n: 1, html: r => r.kld99?.toFixed(4) ?? '—' },
        { key: 'same_top', label: 'Same top', n: 1, html: r => r.same_top != null ? r.same_top.toFixed(2) + '%' : '—' },
        { key: 'ppl_ratio', label: 'PPL ratio', n: 1, html: r => r.ppl_ratio?.toFixed(4) ?? '—' },
        { key: 'rms_dp', label: 'RMS Δp', n: 1, html: r => r.rms_dp != null ? r.rms_dp.toFixed(2) + '%' : '—' },
        { key: 'date', label: 'Date', html: r => `<span class="mono">${esc(r.date.slice(0, 10))}</span>` },
      ], rs, { key: 'kld', dir: 'asc' });
    };
    $$('#kr button').forEach(b => b.onclick = () => { $$('#kr button').forEach(x => x.classList.toggle('on', x === b)); ref = b.dataset.r; draw(); });
    draw();
  }


  // ------------------------------------------------------------------ projects
  function projectCards() {
    return `<div class="projcards">${projects().map(p => {
      const ds = D.docs.filter(d => d.project === p.id);
      const words = ds.reduce((a, d) => a + d.words, 0);
      return `<div class="projcard"><div class="eyebrow">${esc(p.name)}</div><h3><a href="#/doc/${ds[0]?.slug || ''}">${esc(p.title)}</a></h3><p>${esc(p.blurb)}</p>
        <div class="pstats"><span><b>${ds.length}</b> write-ups</span><span><b>${fmtInt(Math.round(words / 1000))}K</b> words</span><span><b>${fmtInt(p.files)}</b> files</span><span><b>${fmtInt(p.commits)}</b> commits${p.subdir ? ` to ${esc(p.subdir)}/` : ''}</span></div>
        <div class="pact"><a class="btn" href="#/doc/${ds[0]?.slug || ''}">Read</a><a class="btn" href="#/files/${esc(p.prefix || 'benchmarks/')}">Files</a><a class="btn" href="${p.url}" target="_blank" rel="noopener">${GH} ${esc(p.repo)}</a></div>
        <div class="plast">Last change ${esc((p.commit_date || '').slice(0, 10))}: <a href="${p.url}/commit/${p.commit}" target="_blank" rel="noopener">${esc(p.commit_msg.length > 90 ? p.commit_msg.slice(0, 90) + '…' : p.commit_msg)}</a></div></div>`;
    }).join('')}</div>`;
  }
  function projectsPage() {
    setTitle('Projects');
    app.innerHTML = `<div class="wrap">
      <div class="page-h"><h1>Projects</h1><p>${['Zero','One','Two','Three','Four','Five','Six','Seven','Eight','Nine'][projects().length] || projects().length} public repositories, one machine (Ryzen 7 9800X3D, RX 9070 XT + Radeon AI PRO R9700). Each write-up below is rendered from its repository; every file links back to GitHub.</p></div>
      ${projectCards()}
      ${projects().map(p => `<div class="section-h"><h2>${esc(p.title)}</h2><a href="${p.url}" target="_blank" rel="noopener">${GH} ${esc(p.repo)}</a></div>
        <div class="tbl"><table><thead><tr><th>Write-up</th><th>File</th><th class="n">Words</th><th></th></tr></thead><tbody>${D.docs.filter(d => d.project === p.id).map(d => `<tr><td><a href="#/doc/${d.slug}">${esc(d.title)}</a></td><td class="mono">${esc(d.path.slice(p.prefix.length))}</td><td class="n">${fmtInt(d.words)}</td><td>${d.gh ? `<a href="${esc(d.gh)}" target="_blank" rel="noopener">${GH}</a>` : ''}</td></tr>`).join('')}</tbody></table></div>`).join('')}
      ${footer()}</div>`;
  }

  // ------------------------------------------------------------------ strata
  function strataPage() {
    setTitle('Strata');
    const S = D.m.strata || { tuning: [], cards: [], modes: [], adapt: [] };
    const cq = D.m.code.filter(r => r.model.endsWith('-strata') && r.total === 50).sort((a, b) => b.pass - a.pass);
    const avg = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : null;
    const base = S.tuning.find(a => a.arm === 'base');
    const prod = S.tuning.find(a => a.arm === 'pw2+trim');
    app.innerHTML = `<div class="wrap">
      <div class="page-h"><div class="eyebrow">Separate inference engine</div><h1>Strata: Qwen3.8-Flash-Next</h1>
      <p>Strata is an engine built only for Qwen3.8-Flash-Next: the hottest experts stay on the GPUs, the rest in RAM, the per-layer n-gram table on the SSD. These are its own measurements: a settings sweep, one card against two, and per-task expert-cache profiles. Write-up: <a href="#/doc/strata">strata.md</a> · evidence: <a href="#/files/benchmarks/strata-tuning/">strata-tuning/</a>, <a href="#/files/benchmarks/strata-expert-modes/">strata-expert-modes/</a>.</p></div>
      <div class="tiles">
        <div class="tile"><div class="v">${prod ? fmt(prod.decode, 1) : '—'}<small>tok/s</small></div><div class="k">Generation, production config</div><div class="s">${prod && base ? `+${fmt((prod.decode / base.decode - 1) * 100, 1)}% over defaults (${fmt(base.decode, 1)})` : ''}</div></div>
        <div class="tile"><div class="v">${prod ? fmtInt(Math.round(prod.prefill)) : '—'}<small>tok/s</small></div><div class="k">Prompt reading, cold 29K</div><div class="s">${prod && base ? `${fmt((prod.prefill / base.prefill - 1) * 100, 1)}% vs defaults` : ''}</div></div>
        <div class="tile"><div class="v">${prod ? fmt(avg(prod.code), 0) : '—'}<small>tok/s</small></div><div class="k">Code answers (mean of 3)</div><div class="s">prose ${prod ? fmt(avg(prod.prose), 0) : '—'} tok/s</div></div>
        <div class="tile"><div class="v">${cq[0] ? cq[0].pass : '—'}<small>/ 50</small></div><div class="k">Best code-quality run</div><div class="s">${esc(cq[0]?.label || '')}</div></div>
      </div>
      <div class="section-h"><h2>Settings sweep (2026-10-12)</h2><a href="#/files/benchmarks/strata-tuning/README.md">README →</a></div>
      <div class="grid2">
        <div class="card"><h3>Generation by setting</h3><p class="sub">6 fresh prompts (3 code, 3 prose), temp 0, 1,000 tokens; all generated tokens over all generation time. A fresh server per setting.</p><div id="s-dec"></div><div class="foot">Darker bars: defaults and the chosen production config.</div></div>
        <div class="card"><h3>Prompt reading by setting</h3><p class="sub">One cold 29,408-token prompt, the size of Claude Code's first turn (tok/s).</p><div id="s-pre"></div><div class="foot">Defaults ran first and last: drift under 0.3%.</div></div>
      </div>
      <div id="s-tbl"></div>
      <div class="section-h"><h2>One card or two (2026-10-16)</h2></div>
      <div class="grid2">
        <div class="card"><h3>Generation</h3><p class="sub">Same prompts and method, 200K context. R9700 alone runs without the two split-only settings.</p><div id="s-cards"></div></div>
        <div class="card"><h3>Code vs prose answers</h3><p class="sub">Mean tok/s of the 3 code and 3 prose prompts.</p><div class="legend"><span><i style="background:var(--s1)"></i>code</span><span><i style="background:var(--s2)"></i>prose</span></div><div id="s-cp"></div></div>
      </div>
      <div class="section-h"><h2>Expert-cache "modes"</h2><a href="#/files/benchmarks/strata-expert-modes/README.md">README →</a></div>
      <p class="sub" style="color:var(--ink-2);margin:-6px 0 12px">The R9700 alone (64% of expert pairs fit). Each profile seeds the cache and pins it; 6 held-out test prompts per domain, 400 tokens. Cells: generation tok/s, share of expert lookups served from VRAM.</p>
      <div id="s-modes"></div>
      ${S.adapt.length ? `<div class="card" style="margin-top:16px"><h3>Switching domains mid-session</h3><p class="sub">12 requests in a row with Strata's adaptive tier on: the cache follows the conversation.</p><div id="s-adapt"></div></div>` : ''}
      <div class="section-h"><h2>Code quality on Strata (${cq.length} runs)</h2><a href="#/code">Task matrix →</a></div>
      <div class="card"><div id="s-cq"></div></div>
      ${footer()}</div>`;

    const hiArm = a => a.arm === 'base' || a.arm === 'pw2+trim';
    const tipArm = a => tipRows(a.label, [['generation', fmt(a.decode, 1) + ' tok/s'], ['prefill', fmtInt(Math.round(a.prefill)) + ' tok/s'], ['code prompts', a.code.map(x => fmt(x, 0)).join(' / ')], ['prose prompts', a.prose.map(x => fmt(x, 0)).join(' / ')], ['VRAM hit rate', a.hit != null ? a.hit + '%' : null], ['load', a.load_s + ' s']]);
    const dec = [...S.tuning].sort((a, b) => b.decode - a.decode);
    hbar($('#s-dec'), dec.map(a => ({ label: a.label, value: a.decode, dim: !hiArm(a), href: fileHref(a.path), tip: tipArm(a) })), { labW: 220, max: 110, step: 20 });
    const pre = [...S.tuning].sort((a, b) => b.prefill - a.prefill);
    hbar($('#s-pre'), pre.map(a => ({ label: a.label, value: a.prefill, text: fmtInt(Math.round(a.prefill)), dim: !hiArm(a), href: fileHref(a.path), tip: tipArm(a) })), { labW: 220, max: 2000, step: 500 });
    sortableTable($('#s-tbl'), [
      { key: 'label', label: 'Setting', html: a => `${hiArm(a) ? '<b>' : ''}${esc(a.label)}${hiArm(a) ? '</b>' : ''}` },
      { key: 'prefill', label: 'Prefill tok/s', n: 1, html: a => fmtInt(Math.round(a.prefill)) + (base && a !== base ? ` <span class="pill">${a.prefill >= base.prefill ? '+' : ''}${fmt((a.prefill / base.prefill - 1) * 100, 0)}%</span>` : '') },
      { key: 'decode', label: 'Generation tok/s', n: 1, html: a => fmt(a.decode, 1) + (base && a !== base ? ` <span class="pill">${a.decode >= base.decode ? '+' : ''}${fmt((a.decode / base.decode - 1) * 100, 1)}%</span>` : '') },
      { key: 'code', label: 'Code ×3', sort: a => avg(a.code), html: a => `<span class="mono">${a.code.map(x => fmt(x, 0)).join(' / ')}</span>` },
      { key: 'prose', label: 'Prose ×3', sort: a => avg(a.prose), html: a => `<span class="mono">${a.prose.map(x => fmt(x, 0)).join(' / ')}</span>` },
      { key: 'hit', label: 'VRAM hits', n: 1, html: a => a.hit != null ? a.hit + '%' : '—' },
    ], S.tuning, { key: 'decode', dir: 'desc' });
    hbar($('#s-cards'), S.cards.map(a => ({ label: a.label, value: a.decode, href: fileHref(a.path), tip: tipArm(a), cls: a.arm.startsWith('r9700') ? 'alt' : '' })), { labW: 190, max: 110, step: 20 });
    const cp = $('#s-cp');
    const cpRows = [];
    for (const a of S.cards) { cpRows.push({ label: a.label + ' · code', value: avg(a.code), tip: tipArm(a) }); cpRows.push({ label: a.label + ' · prose', value: avg(a.prose), cls: 'alt', tip: tipArm(a) }); }
    hbar(cp, cpRows, { labW: 230, max: 150, step: 25 });

    const profs = [...new Set(S.modes.map(m => m.profile))], doms = [...new Set(S.modes.map(m => m.domain))];
    const mx = Math.max(...S.modes.map(m => m.tok_s));
    $('#s-modes').innerHTML = S.modes.length ? `<div class="tbl heat"><table><thead><tr><th>Profile ↓ / test domain →</th>${doms.map(d => `<th style="text-align:center">${esc(d)}</th>`).join('')}</tr></thead><tbody>${profs.map(p => `<tr><td class="run"><b>${esc(p)}</b><small>${p === 'shipped' ? "Strata's general profile" : `built from ${esc(p)} routing`}</small></td>${doms.map(d => { const m = S.modes.find(x => x.profile === p && x.domain === d); if (!m) return '<td class="c l0">—</td>'; const l = Math.max(1, Math.min(6, Math.round(m.tok_s / mx * 6))); return `<td class="c l${l}" data-tip="${esc(JSON.stringify(m))}">${fmt(m.tok_s, 1)} tok/s<br><small>${m.hit}% VRAM</small></td>`; }).join('')}</tr>`).join('')}</tbody></table></div>` : '<div class="empty">No expert-mode results.</div>';
    bindTips($('#s-modes'), s => { const m = JSON.parse(s); return tipRows(`${m.profile} profile · ${m.domain} prompts`, [['generation', m.tok_s + ' tok/s'], ['expert lookups in VRAM', m.hit + '%'], ['SSD read / request', m.ssd_mb + ' MB']]); });
    if (S.adapt.length) {
      const rows = [];
      for (const a of S.adapt) for (const r of a.runs) rows.push({ label: `${a.seq} #${r.i} (${r.domain})`, value: r.tok_s, cls: r.domain === 'code' ? '' : 'alt', tip: tipRows(`${a.seq}, request ${r.i}`, [['domain', r.domain], ['generation', r.tok_s + ' tok/s'], ['VRAM hits', r.hit + '%']]) });
      $('#s-adapt').insertAdjacentHTML('beforebegin', '<div class="legend"><span><i style="background:var(--s1)"></i>code prompt</span><span><i style="background:var(--s2)"></i>other domain</span></div>');
      hbar($('#s-adapt'), rows, { labW: 240, rowH: 20, max: 130, step: 25 });
    }
    hbar($('#s-cq'), cq.map(r => ({ label: `${r.model.replace('qwen3.8-flash-next-', '')} · ${r.label.replace(/^qwen3\.8-flash-next-[^-]+(-[^-]+)?-strata-?/, '') || 'baseline'}`, value: r.pass, text: `${r.pass}/50`, href: fileHref(r.path), dim: !cqCorrected(r), tip: tipRows(r.label, [['score', `${r.pass}/50`], ['clean tasks', `${r.clean}/7`], ['prompts', cqCorrected(r) ? 'corrected' : 'old (≤2 low)'], ...r.tasks.map(t => [t.task, `${t.pass}/${t.total}`])]) })), { labW: 300, max: 50, step: 10 });
  }

  // ------------------------------------------------------------------ files
  function buildTree() {
    const root = { dirs: {}, files: [] };
    for (const f of D.files) {
      const parts = f.p.split('/'); let n = root;
      for (const p of parts.slice(0, -1)) n = n.dirs[p] ??= { dirs: {}, files: [] };
      n.files.push(f);
    }
    return root;
  }
  let TREE = null, viewTok = 0;
  function treeHtml(n, prefix, open) {
    let s = '';
    for (const [name, d] of Object.entries(n.dirs).sort((a, b) => a[0].localeCompare(b[0], undefined, { numeric: true }))) {
      const p = prefix + name + '/';
      s += `<details ${open.startsWith(p) ? 'open' : ''} data-p="${esc(p)}"><summary>${esc(name)}</summary><div class="kids">${treeHtml(d, p, open)}</div></details>`;
    }
    for (const f of [...n.files].sort((a, b) => a.p.localeCompare(b.p, undefined, { numeric: true }))) s += `<a href="${fileHref(f.p)}" data-p="${esc(f.p)}" title="${esc(f.p)}">${esc(f.p.split('/').pop())}</a>`;
    return s;
  }
  async function filesPage(path, same) {
    TREE ??= buildTree();
    const isDir = !path || path.endsWith('/');
    setTitle(path || 'Files');
    if (!same || !$('#tree')) {
      app.innerHTML = `<div class="files"><aside class="tree"><input type="search" id="tf" placeholder="Filter ${fmtInt(D.files.length)} files…"><div id="tree">${treeHtml(TREE, '', path)}</div></aside><section class="viewer" id="viewer"></section></div>`;
      $('#tf').oninput = e => {
        const q = e.target.value.toLowerCase();
        $$('#tree a').forEach(a => a.style.display = !q || a.dataset.p.toLowerCase().includes(q) ? '' : 'none');
        $$('#tree details').forEach(d => { const any = $$('a', d).some(a => a.style.display !== 'none'); d.style.display = any ? '' : 'none'; if (q) d.open = any; });
      };
    } else {
      $$('#tree details').forEach(d => { if (path.startsWith(d.dataset.p)) d.open = true; });
    }
    $$('#tree a.on').forEach(a => a.classList.remove('on'));
    const cur = $(`#tree a[data-p="${CSS.escape(path)}"]`); if (cur) { cur.classList.add('on'); cur.scrollIntoView({ block: 'nearest' }); }
    const v = $('#viewer'); v.scrollTop = 0;
    const crumbs = path.replace(/\/$/, '').split('/').filter(Boolean);
    const crumbHtml = `<a href="#/files/">root</a>` + crumbs.map((c, i) => ` / ${i === crumbs.length - 1 && !isDir ? `<b>${esc(c)}</b>` : `<a href="#/files/${esc(crumbs.slice(0, i + 1).join('/'))}/">${esc(c)}</a>`}`).join('');
    if (isDir) {
      let n = TREE; for (const c of crumbs) n = n?.dirs[c];
      if (!n) { v.innerHTML = `<div class="vhead"><div class="crumbs">${crumbHtml}</div></div><div class="empty">No such folder.</div>`; return; }
      const sub = Object.entries(n.dirs).sort((a, b) => a[0].localeCompare(b[0], undefined, { numeric: true }));
      const count = d => d.files.length + Object.values(d.dirs).reduce((a, x) => a + count(x), 0);
      const readme = n.files.find(f => /(^|\/)(README\.md|SUMMARY\.txt)$/.test(f.p));
      const mname = crumbs[0] === 'benchmarks' && crumbs.length === 2 ? crumbs[1] : null;
      const isModel = mname && models().some(m => m.model === mname);
      v.innerHTML = `<div class="vhead"><div class="crumbs">${crumbHtml}</div><div class="vmeta"><span class="pill">${sub.length} folders</span><span class="pill">${n.files.length} files</span><span class="sp">${isModel ? `<a class="btn" href="#/model/${esc(mname)}">Model summary →</a>` : ''}${crumbs.length && projOf(path) && path !== projOf(path).prefix ? `<a class="btn" href="${esc(ghFile(path, true))}" target="_blank" rel="noopener">${GH} GitHub</a>` : ''}</span></div></div>
        <div class="vbody"><div class="wrapin">
        ${sub.length ? `<div class="tbl"><table class="dirlist"><thead><tr><th>Folder</th><th class="n">Files</th></tr></thead><tbody>${sub.map(([k, d]) => `<tr><td><a href="#/files/${esc(path + k)}/">${esc(k)}/</a></td><td class="n">${count(d)}</td></tr>`).join('')}</tbody></table></div>` : ''}
        ${n.files.length ? fileTable(n.files) : ''}
        ${readme ? `<div class="card" style="margin-top:16px"><h3>${esc(readme.p.split('/').pop())}</h3><pre class="code wrap" id="rd"></pre></div>` : ''}
        </div></div>`;
      if (readme) { const t = await (await fetch('raw/' + readme.p)).text(); const el = $('#rd'); if (el) el.innerHTML = lines(t); }
      return;
    }
    const f = D.files.find(x => x.p === path);
    if (!f) { v.innerHTML = `<div class="vhead"><div class="crumbs">${crumbHtml}</div></div><div class="empty">File not published.</div>`; return; }
    const ext = (path.match(/\.([a-z0-9]+)$/i)?.[1] || '').toLowerCase();
    const parsed = parsedFor(path);
    const doc = D.docs.find(d => d.path === path);
    v.innerHTML = `<div class="vhead"><div class="crumbs">${crumbHtml}</div><div class="vmeta">
      <span class="pill">${bytes(f.s)}</span>${Object.entries(f.h || {}).filter(([k]) => ['model', 'ctx', 'date', 'flags', 'base', 'build'].includes(k)).map(([k, x]) => `<span class="pill" title="${esc(k)}">${esc(k)}: <code>${esc(x.length > 60 ? x.slice(0, 60) + '…' : x)}</code></span>`).join('')}
      ${parsed}
      <span class="sp">${doc ? `<a class="btn" href="#/doc/${doc.slug}">Rendered</a>` : ''}${ghFile(path) ? `<a class="btn" href="${esc(ghFile(path))}" target="_blank" rel="noopener">${GH} GitHub</a>` : `<span class="pill" title="Not committed to GitHub yet">local only</span>`}<button class="btn" id="wrapbtn">Wrap</button><button class="btn" id="copybtn">Copy</button><a class="btn" href="raw/${esc(path)}" target="_blank" download>Download</a></span></div></div>
      <div class="vbody" id="vb"><div class="loading">Loading…</div></div>`;
    const vb = $('#vb');
    if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext)) { vb.innerHTML = `<div class="wrapin"><img src="raw/${esc(path)}" alt="${esc(path)}"></div>`; return; }
    const tok = ++viewTok;
    const res = await fetch('raw/' + path); let text = await res.text();
    if (tok !== viewTok) return; // navigated away while loading
    if (ext === 'json') { try { text = JSON.stringify(JSON.parse(text), null, 2); } catch (e) { /* jsonl or invalid */ } }
    const lang = { html: 'xml', js: 'javascript', css: 'css', toml: 'ini', py: 'python', sh: 'bash', json: 'json', c: 'c', ini: 'ini', md: 'markdown', jinja: 'django', yaml: 'yaml', yml: 'yaml', toml: 'ini' }[ext];
    let wrapped = store.get('wrap') === '1';
    if (lang && window.hljs && text.length < 400000) {
      const hl = hljs.highlight(text, { language: lang, ignoreIllegals: true }).value;
      vb.innerHTML = `<pre class="code ${wrapped ? 'wrap' : ''} hljs" style="background:transparent">${splitHl(hl)}</pre>`;
    } else {
      vb.innerHTML = `<pre class="code ${wrapped ? 'wrap' : ''}">${lines(text)}</pre>`;
    }
    $('#wrapbtn').onclick = () => { wrapped = !wrapped; store.set('wrap', wrapped ? '1' : '0'); $('.code', vb).classList.toggle('wrap', wrapped); };
    $('#copybtn').onclick = async () => { try { await navigator.clipboard.writeText(text); $('#copybtn').textContent = 'Copied'; setTimeout(() => { const b = $('#copybtn'); if (b) b.textContent = 'Copy'; }, 1200); } catch (e) { /* no clipboard */ } };
  }
  function lines(t) { return t.replace(/\n$/, '').split('\n').map(l => `<span class="ln">${esc(l) || ' '}</span>`).join(''); }
  // split highlighted html into lines, re-opening spans that cross line breaks
  function splitHl(html) {
    const out = []; let open = []; let line = '';
    const re = /(<span[^>]*>)|(<\/span>)|(\n)|([^<\n]+|<)/g; let m;
    while ((m = re.exec(html))) {
      if (m[1]) { open.push(m[1]); line += m[1]; }
      else if (m[2]) { open.pop(); line += m[2]; }
      else if (m[3]) { out.push(line + '</span>'.repeat(open.length)); line = open.join(''); }
      else line += m[4];
    }
    out.push(line + '</span>'.repeat(open.length));
    return out.map(l => `<span class="ln">${l || ' '}</span>`).join('');
  }
  function parsedFor(path) {
    const c = D.m.code.find(r => r.path === path), k = D.m.kld.find(r => r.path === path), t = D.m.throughput.find(r => r.path === path), u = D.m.cdn.find(r => r.path === path), tl = D.m.tools.find(r => r.path === path);
    const p = [];
    if (c) p.push(`<span class="pill ok">score ${c.pass}/${c.total} · ${c.clean}/${c.ntasks} clean</span>`);
    if (k) p.push(`<span class="pill ok">mean KLD ${k.kld.toFixed(5)} · same top ${k.same_top}%</span>`);
    if (t) p.push(`<span class="pill ok">tg ${fmt(t.tg, 1)} tok/s${t.pp ? ` · pp ${fmt(t.pp, 0)}` : ''}${t.draft ? ` · draft ${t.draft}%` : ''}</span>`);
    if (u) p.push(`<span class="pill ok">${u.ok}/${u.total} URLs resolve</span>`);
    if (tl) p.push(`<span class="pill ${tl.ok ? 'ok' : 'bad'}">tool calls ${tl.ok ? 'correct' : 'wrong'}</span>`);
    return p.join('');
  }

  // ------------------------------------------------------------------ search
  const pal = $('#palette'), qi = $('#q'), res = $('#results');
  let hits = [], sel = 0;
  async function openSearch() {
    pal.hidden = false; qi.focus(); qi.select();
    if (!searchIdx) {
      res.innerHTML = '<div class="empty">Loading index…</div>';
      const secs = await (await fetch('search.json')).json();
      searchIdx = [
        ...D.docs.map(d => ({ k: 'doc', t: d.title, p: d.path, x: '', h: `#/doc/${d.slug}`, l: d.title.toLowerCase() + ' ' + d.path.toLowerCase() })),
        ...secs.filter(s => s.i).map(s => { const d = docBySlug(s.d); return { k: 'section', t: s.t, p: `${projById(d.project)?.name} · ${d.title}`, x: s.x, h: `#/doc/${s.d}/${s.i}`, l: (s.t + ' ' + s.x).toLowerCase(), tl: s.t.toLowerCase() }; }),
        ...models().map(m => ({ k: 'model', t: m.model, p: m.family, x: [m.tput && `gen ${fmt(m.tput.tg, 1)} tok/s`, m.kldv && `KLD ${m.kldv.kld.toFixed(4)}`, m.base && `code ${m.base.pass}/50`].filter(Boolean).join(' · '), h: `#/model/${m.model}`, l: m.model.toLowerCase() + ' ' + m.family.toLowerCase() })),
        ...D.files.map(f => ({ k: 'file', t: f.p.split('/').pop(), p: f.p, x: f.h?.model || '', h: fileHref(f.p), l: f.p.toLowerCase() + ' ' + (f.h?.model || '').toLowerCase() })),
      ];
    }
    doSearch();
  }
  function closeSearch() { pal.hidden = true; }
  function doSearch() {
    if (!searchIdx) return;
    const q = qi.value.trim().toLowerCase();
    const toks = q.split(/\s+/).filter(Boolean);
    if (!toks.length) {
      hits = D.docs.map(d => ({ k: 'doc', t: d.title, p: d.path, x: '', h: `#/doc/${d.slug}` }));
    } else {
      const w = { doc: 30, model: 25, section: 10, file: 4 };
      hits = [];
      for (const it of searchIdx) {
        let s = 0, ok = true;
        for (const t of toks) {
          const i = it.l.indexOf(t); if (i < 0) { ok = false; break; }
          s += (it.tl || it.t.toLowerCase()).includes(t) ? 20 : 1;
          if (it.k === 'section') { let c = 0, j = i; while (j >= 0 && c < 8) { c++; j = it.l.indexOf(t, j + t.length); } s += c; }
        }
        if (ok) hits.push({ ...it, s: s + w[it.k] });
      }
      hits.sort((a, b) => b.s - a.s); hits = hits.slice(0, 60);
    }
    sel = 0; renderHits(toks);
  }
  function snippet(x, toks) {
    if (!x) return '';
    const l = x.toLowerCase(); let i = -1;
    for (const t of toks) { i = l.indexOf(t); if (i >= 0) break; }
    const s = Math.max(0, i - 70), part = (s ? '…' : '') + x.slice(s, s + 220);
    let h = esc(part);
    for (const t of toks) if (t.length > 1) h = h.replace(new RegExp(esc(t).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), m => `<mark>${m}</mark>`);
    return h;
  }
  function renderHits(toks) {
    res.innerHTML = hits.length ? hits.map((h, i) => `<a class="res ${i === sel ? 'on' : ''}" href="${esc(h.h)}" data-i="${i}"><div class="rt">${esc(h.t)} <span class="pill">${h.k}</span></div><div class="rp">${esc(h.p)}</div>${h.x ? `<div class="rs">${snippet(h.x, toks)}</div>` : ''}</a>`).join('') : '<div class="empty">No matches.</div>';
  }
  function moveSel(d) {
    sel = Math.max(0, Math.min(hits.length - 1, sel + d));
    $$('.res', res).forEach((a, i) => a.classList.toggle('on', i === sel));
    $('.res.on', res)?.scrollIntoView({ block: 'nearest' });
  }
  qi.addEventListener('input', doSearch);
  qi.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown') { e.preventDefault(); moveSel(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); moveSel(-1); }
    else if (e.key === 'Enter' && hits[sel]) { e.preventDefault(); location.hash = hits[sel].h; closeSearch(); }
    else if (e.key === 'Escape') closeSearch();
  });
  res.addEventListener('click', e => { if (e.target.closest('.res')) closeSearch(); });
  pal.addEventListener('mousedown', e => { if (e.target === pal) closeSearch(); });
  $('#searchbtn').onclick = openSearch;
  addEventListener('keydown', e => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName);
    if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) { e.preventDefault(); openSearch(); }
    else if (e.key === 'Escape' && !pal.hidden) closeSearch();
  });

  // ------------------------------------------------------------------ chrome
  $('#navtoggle').onclick = () => $('#mainnav').classList.toggle('open');
  $('#themebtn').onclick = () => {
    const cur = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next; store.set('theme', next); syncHl();
  };
  function syncHl() {
    const t = document.documentElement.dataset.theme;
    $('#hl-light').media = t ? (t === 'light' ? 'all' : 'not all') : '(prefers-color-scheme: light)';
    $('#hl-dark').media = t ? (t === 'dark' ? 'all' : 'not all') : '(prefers-color-scheme: dark)';
  }
  syncHl();

  fetch('data.json').then(r => r.json()).then(d => { D = d; addEventListener('hashchange', route); route(); })
    .catch(e => { app.innerHTML = `<div class="wrap"><div class="note">Couldn't load data.json: ${esc(e.message)}</div></div>`; });
})();
