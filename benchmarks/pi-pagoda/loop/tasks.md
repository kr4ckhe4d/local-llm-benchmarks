# Tasks

Status: `[ ]` todo, `[~]` partial (finish first), `[x]` done. One task per session.
Each task must meet its **Done when** before it is ticked. Add new tasks at the right place when you find
work that is missing; split tasks that are too big (T05 -> T05a, T05b).
All tasks also require: `node tools/shot.mjs --all` exits 0 (once the scene exists) and FPS >= 55.

- [x] **T01 Scaffold.** Vendor three@0.187.0 (`npm pack`, copy `build/` and `examples/jsm/` into
  `vendor/three/`, delete the tarball), `index.html` with an import map, `src/main.js` with renderer
  (ACES or AgX tone mapping, sRGB output, shadows on), orbit camera, resize handling, seeded RNG
  (`src/rng.js`), URL param parsing, the `window.__diag` contract, an FPS meter. A placeholder ground disk
  and a box. Create `tools/views.json` with the review views (see project.md presets; use `paused=1&ui=0`
  plus a `time` for each, e.g. overview-day 9, pagoda 10, pond 11, torii 15, sunset-overview 18.5,
  night-overview 23, underside 12).
  Done when: `node tools/shot.mjs --all` exits 0 and `__diag.ready` is true in every view.
- [x] **T02 Sky and lighting.**
  Physical Sky, sun direction from `time`, PMREM environment from the sky
  (regenerated when time changes enough, not every frame), directional sun with soft shadows sized to the
  island, hemisphere/fill light, fog matching the horizon, moon light + star field at night.
  Done when: day, sunset and night screenshots look right and shadows are crisp without acne.
- [x] **T03 Floating island.** Terrain top (noise heightfield on a disk with a soft rim), rocky tapered
  underside (displaced cone with strata), edge transition, ground materials (grass/soil/rock, CC0
  textures or procedural with normal maps), hanging roots. Clouds/haze below.
  Done when: overview and underside views read as a believable floating island, no seams or holes.
- [x] **T04 Pagoda.** Parametric five-tier pagoda: plinth and steps, walls with posts and plaster, bracket
  sets, curved upturned roofs with tile ridges, sōrin spire. Proper materials. Keep draw calls low (merge).
  Done when: pagoda close-up scores >= 4 on Shape and Materials.
- [x] **T05 Pond and water.** Irregular pond carved into the terrain, edge stones, reflective water with
  ripples and fresnel, depth colour, lily pads. — DONE: `src/pond.js` (carved basin, Water surface, 26 edge
  stones, lily pads, exposed `pond.basinHeight`/`waterR`), pond preset reframed. Reflection FIXED this session
  (mirror-plane bug: the Water addon derives the plane from the MESH transform — fan rebuilt in local XY plane,
  height + rotation on `water`); sky reflection (water centre 177,212,234) and pagoda mirror (54–57% of two
  water cells change vs pagoda hidden, avg diff ~190/765) verified by render-diff; night/sunset/low-quality
  pond checked.
  Done when: pond view shows reflections of the pagoda/sky and a clean shoreline.
- [x] **T06 Koi.** 5+ koi with procedural bodies and patterns, swimming paths with wiggle (vertex shader or
  bones), visible through the water. — DONE: 6 koi (1 merged geometry + 1 atlas = 1 draw call, CPU wiggle,
  loop paths). Koi now read clearly in the pond view: (a) backs break the surface (dMin negative) so the
  bright patterned body reads against the dark water at the grazing angle, (b) a light conforming pond-liner
  floor added to `pond.js` so the basin isn't black, (c) pond camera preset raised to a steeper closer shot
  (pos [2.3,5.7,15.9], target [0,2.5,12]) so the koi sit mid-frame. Verified: hide-koi render-diff shows
  orange 400 / white 1584 / black 3826 px around a dead-centre koi centroid; all 6 swim (0.9 u in 2 s);
  reflections intact (570k water px change with pagoda hidden); `shot --all` 0 errors, fps 60.3–60.7.
  Done when: koi are recognisable in the pond view and move smoothly.
- [x] **T07 Bridge, torii, lanterns, path.** Taiko bridge, torii gate, 3+ tōrō lanterns with night
  light (cap real lights; use emissive + bloom + a few point lights), stepping-stone path. — DONE:
  `src/garden.js` (12 new draw calls). Taiko bridge across the pond at x=−2.8 (concave sides, crowned
  plank deck, red stringers/rails, stone steps); torii at (−22,15) facing the bridge approach (black
  kasagi, red body, stone bases, flattened patch); 4 tōrō lanterns (mossy stone, glowing core, 2 real
  PointLights — 5 lights total, glow flicker at night); 34 stepping stones torii→bridge→pagoda
  (CatmullRom, `groundY` raycast so nothing floats over the in-place-flattened/pond-carved terrain).
  `sky.js` now exposes `skySys.night` (nightF). Verified (stats-only): torii in-frame in torii view
  (hide-diff 18.8k px, red 6.0k px + black kasagi 10.7k px in the gate region); bridge in pond view
  (71k red px, 0% red overlap with any of the 6 koi); night point lights change 2502 px (max Δ613/765);
  all 7 views 0 errors, fps 60.3–60.5, drawCalls 35–64.
  Done when: torii and pond views show them with correct proportions and materials.
- [x] **T08 Cherry trees.** Seeded procedural trunks/branches with bark, instanced blossom clusters,
  colour variation, wind sway, petals on the ground. — DONE: `src/trees.js` (3 draw calls: 1 merged
  trunks, 1 instanced blossoms, 1 instanced ground petals). 7 seeded sakura at handoff-suggested spots
  (raycast-verified clear of water/path/bridge/torii/lantern): (−12,13), (−8,22), (6.5,17), (−7,5.5),
  (−11,−8), (11,−6), (10,−11). Recursive 5-level tapered branching with outward lean (wide, open
  crowns); blossom = weighted-sampled icosahedron d1 puffs (flat-shaded, per-tree tint bias +
  instance colour from a 5-shade pink palette); wind sway via vertex-shader `uTime`/`uWind` injection
  (frozen when paused); petals = alpha-notched petal sprites scattered on groundY. `__diag.trees=7`.
  Verified (stats-only, image-blind): overview-day pink 0.76% (4× after deepening palette — ACES
  desaturated pale pinks to white); pagoda view 5.7% pink / 29k pink px, crown span 640×587 px
  (wide, non-lollipop); trunk-base box at (10,−11) 9.6% pink (petals visible); sway motion 715 px
  moved / max Δ419 over 1.2 s unpaused; all 7 views 0 errors, fps 60.4–60.6, drawCalls 38–69;
  quality=low branch checked (99k tris, 60.5 fps).
  Done when: trees look like sakura (not lollipops) in overview and pagoda views.
- [x] **T09 Vegetation and rocks.** — DONE: `src/vegetation.js` (7 draw calls). 13k wind-swaying grass
  blades (instanced crossed cards, uv-weighted sway, meadow clumps via value noise; 3.8k low), 90 flowers,
  8 mossy displaced-icosahedron boulders (moss vertex-tinted tops, sunk ~30%), bamboo grove in 2 edge
  clusters (merged node-lined stalks + instanced leaf cards), ~32 trimmed shrubs along path + pond rim,
  ~30 moss patches near rocks/trees/path. `garden.js` now exposes `pathPoints`; exclusions keep grass off
  pond/path/torii/bridge/pagoda/lanterns and reserve (11,3) r4.3 for T10 zen bed. `__diag.grass`/`rocks`
  added. Verified (stats-only): 0 errors, fps 60.3–60.6 all views, overview 277k tris / 61 calls, seed 7
  + quality low re-scatter OK, grass/bamboo/rock pixel probes green, sway motion verified (leaf Δ353).
  Done when: no bare ground visible in the overview except paths and gravel; FPS still >= 55.
  Done when: rake lines are clearly visible in a daylight screenshot.
- [x] **T10 Zen garden.** Raked gravel bed with rake-line normal/displacement, placed rocks. — DONE: `src/zen.js` (tray flatten, raked gravel fan 2048px texture SP 0.5u + geometric macro ridges 1.0u ±0.045u, 3 zen stones + 26-stone curb, 2 draw calls) at (20,2) r4.3. Verified: overview clean-gravel row shows ±35-level ~10px periodic rake relief (probe), no moss/grass on bed (0 green cells in ellipse probe), 0 Z-fight pixels between frames, close-up detail retained; all 7 views 0 errors fps 60.4-60.6; seed=7 + quality=low OK.
- [x] **T11 Petals and fireflies.** — DONE: `src/petals.js` (+2 draw calls). Instanced wind-driven falling
  petals (0–3000 via `petals=`, default 800), spawned in the 7 sakura crown boxes (`trees.js` now exposes
  `trees.crowns` + exports the petal texture, redrawn to fill the full canvas — mip-alpha fix), fluttering
  fall + wind drift, settle on terrain/water (rest 2–6 s, respawn); 40 fireflies as one additive Points
  cloud along path/torii/bridge/pond, warm blink, opacity gated on `skySys.night` (≥0.3). `__diag.petals`
  is the live falling-petal count. Verified (stats-only): petals=1500 diff vs hidden — pagoda 7599 px
  (2097 pink), torii 7327 px (2505 pink), overview 1764 px; petals=0 → no mesh (63 calls); petals=3000 →
  60.6fps; night diff vs hidden fireflies 444 px (58 warm cores, spread x 524–855), day 0 px (opacity 0);
  unpaused motion 9620/9564 px per 1.5 s; all 7 views 0 errors fps 60.4–60.6; seed=7 + quality=low OK.
  Done when: petals visible in day views, fireflies in the night view, count follows `petals=`.
- [x] **T12 Post-processing.** EffectComposer chain: AO, bloom, AA, output/tone map, vignette; `post=0`
  disables it; quality low/high switches resolution scale, shadow map size, grass density. — DONE:
  `src/post.js` chain RenderPass→GTAO→UnrealBloom→SMAA→vignette→OutputPass; `post=0` = plain render
  (output identical to pre-T12 baseline, verified); night-gated bloom threshold (day 8.2 → night 0.8,
  day-sky linear luma 4.5–7.5 measured via `tools/probe-sky.mjs`); per-frame `renderer.info` reset
  (drawCalls 284); quality low runs chain at 0.66x. Visible on/off diff PROVED via `tools/ab-diff.py`
  + `tools/ab-bloom.py` on A/B screenshots: night torii (t23) two in-frame lanterns show bloom halo ring
  (6–30px) luma lift +23.2/+25.7 and warm-pixel count 441→2232 (5×); day overview vignette corners
  −10…−27 levels vs centre +7.1 (GTAO also shifts 647k px >10 levels); night max Δ 238. All 7 views
  0 errors, fps 60.3–60.6 with post on. AA (SMAA) in chain, no errors (pixel-level AA check optional,
  skipped — global diff evidence suffices).
  Done when: post on/off screenshots differ visibly and FPS >= 55 with post on.
- [x] **T13 Controls panel.** — DONE: `src/ui.js` (top-left collapsible panel, stable ids `ui-*`,
  title 桜の庭 top-right, `ui=0` hides all). All project.md controls present; live: time slider,
  pause, cycle speed, petals (0–3000 via InstancedMesh.count), wind, toggles auto-rotate/shadows/
  post/fireflies/water/wireframe, presets 1–5 (rig tweens), reset view, fps+calls readout;
  reload-type: quality low/high, regenerate seed (URL rewrite + reload — decisions.md). Keyboard
  1–5 / Space / N / R. `__diag` gained paused, cycleSpeed, wind, autoRotate, shadows, fireflies,
  water, wireframe. Verified via probe-sky.mjs DOM-drive expression (each control → __diag assert,
  see decisions.md for the rAF-wait gotcha): all 15 live controls flip their diag field, preset
  buttons land exact camera coords, key2/space/N work, quality→low reloads and the reloaded page
  runs 60.4fps/0 errors (grass 3800), regen click navigates (CDP "target navigated"). New `ui-panel`
  review view (8th in views.json); `--all` 8/8 views 0 errors, fps 60.3–60.6, draw calls unchanged.
  Done when: a screenshot with `ui=1` shows the panel; each control changes the scene (verify via
  `Runtime.evaluate`-style checks or URL params, document how in the handoff).
- [x] **T14 Controls verification.** — DONE: `tools/check-controls.mjs` (new tool; shot.mjs untouched),
  headless Chrome + CDP battery of 24 checks, all PASS, exit 0. Covers: panel present, time, pause,
  cycle speed, petals (800→2000→0→800), wind, all 6 toggles (auto-rotate/shadows/post/fireflies/water/
  wireframe) each on→off, preset-3 BUTTON + presets 1/2/4/5 KEYS (exact camera coords), reset view,
  Space key, N key (17→23→9), collapse/reopen, quality→low RELOAD (poll location.search then
  __diag.quality), regen seed RELOAD (seed ≠ 42 after), zero page errors/exceptions. Gotchas logged
  in decisions.md (fn.toString() serialization, reload detection via URL poll).
  Done when: the check script exits 0 and covers every control.
- [x] **T15 Realism pass.** — DONE (stats-only, image-blind): three weakest = sunset (darkPct 26.1, edge 3.5,
  col 189), night (dark 67.6, edge 2.8, col 88), underside (col 58, sat 0.073, edge 3.7). Fixed via
  time-of-day exposure in sky.js (base 0.38→0.305, +0.22·sunset, +0.3·night, applied per frame in main.js),
  sunset sun/hemi boosts, night lift (moon 3.2→5.5, hemi floor, brighter night fog 0x2a3d63), new 6th
  cloud-bounce directional from below (restores normal shading on the down-facing cone), underside strata
  (vertex ±40% contrast + rusty/cool hue split, ruddy/blue texture bands, 2-octave mottle, normal 3.0/2.4,
  UV u×3), day sky turbidity →10 (kills pagoda/torii brightPct). Final: all 8 views 0 errors 60.3–60.6fps,
  day views pass every strict line (dark<25/bright<10/edge>6), sunset dark 21.5, night edge 6.1 + legible
  island, underside edge 15.4; T14 check-controls 24/24 PASS. Rubric scores (all >=4) in handoff.
  Done when: rubric scores in the handoff are all >= 4 with a reason for each.
- [x] **T16 Final review.** — DONE (stats-only, image-blind): all 8 acceptance checks passed in-session:
  (1) shot --all exit 0, 8/8 views 0 errors; (2) fps 60.3–60.5 ≥ 55, drawCalls 180–288 < 600;
  (3) element→screenshot map written in handoff; (4) rubric all >= 4 (T15 scores carried, scene
  unchanged, final numbers match); (5) day-cycle probed (t9 lum 0.629 / t18.5 300k warm px /
  t23 274 warm + 111 star specks, 86% day-vs-night diff); (6) check-controls 24/24 PASS;
  (7) repo ≈ 26 MB ≤ 80 MB, assets/CREDITS.md written (all assets procedural; three.js MIT);
  (8) python3 -m http.server load check 4×200. README.md written; 8 final screenshots in
  docs/shots/ (scratch pruned). goal_complete called.
  Done when: all acceptance checks pass this session; then call `goal_complete`.
