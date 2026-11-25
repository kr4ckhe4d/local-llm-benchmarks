2026-11-25T13:43:33.162Z
All 8 acceptance checks verified this session (image-blind; stats-only judgment per AGENTS.md, as noted in handoff):
1. `node tools/shot.mjs --all` exit 0 — 8/8 views, zero console/page errors, zero warnings.
2. FPS 60.3–60.5 in every view at 1600x900 quality=high (≥55); drawCalls 180–288 (<600); diag grass 13000/petals 800/koi 6/trees 7/lights 6.
3. Every scene-content element mapped to a committed screenshot in .ai/handoff.md (island→overview-day+underside, pagoda→pagoda, sakura+petals→overview/pagoda/torii, pond+koi→pond, bridge→pond, torii→torii, lanterns→torii+night, vegetation/rocks/path/zen→overview+torii, sky/light→day/sunset/night views, post→all views (post=1), panel→ui-panel). Final screenshots committed to docs/shots/ (8 files, 8.6 MB).
4. Realism rubric all ≥4 in handoff (Materials 4, Lighting 4, Shape 4, Composition 4, Motion 4, Cleanliness 4); no scene code changed since T15 and this session's `--all` numbers match T15's final numbers (e.g. overview-day lum 0.635/edge 7.8/col 264, sunset dark 21.4, night edge 6.1, underside edge 15.4).
5. Day cycle: probed PNGs at t9 (lum 0.629, 52% px >190 luma, green/sky palette), t18.5 (lum 0.298, 300,803 warm px, red 42.7%), t23 (lum 0.147, 274 warm px = lanterns/fireflies, 111 bright star specks in top third); day-vs-night 86% of pixels differ >30.
6. `node tools/check-controls.mjs`: 24/24 PASS, exit 0 (every panel control, presets, keyboard, reload-type quality/seed).
7. Repo size ≈26 MB committed (working tree excl. git-ignored shots/ ≈17 MB + docs/shots 8.6 MB) ≤ 80 MB; assets/CREDITS.md written — grep confirmed no texture loaders or downloaded files in src (all textures procedural), only third-party code is vendored three.js r187 (MIT, vendor/three/LICENSE).
8. `python3 -m http.server`: `/`, `/src/main.js`, `/vendor/three/build/three.module.js`, `/vendor/three/examples/jsm/objects/Sky.js` all 200 with JavaScript content type; no build step (import map → vendored three).
Committed as eb20112; all 16 tasks [x] in .ai/tasks.md; handoff rewritten with the element map.
