# Project: realistic pagoda garden

## Goal

A single web page (`index.html`, ES modules in `src/`, Three.js r187 vendored) showing a **photoreal-leaning
Japanese garden on a floating island**: a five-tier pagoda, cherry blossom trees, a koi pond with an arched
bridge, a torii gate, stone lanterns, bamboo, rocks, moss and a raked zen gravel bed, with falling petals,
wind, and a full day/night cycle. It reimagines an earlier voxel version of the same scene (see the reference
list below) as a realistic one: no blocky geometry, no flat-shaded boxes.

Real-time, interactive, smooth: orbit camera, a controls panel, 60 fps on the dev machine.

## Scene contents (all required)

| Element | Realistic means |
|---|---|
| Floating island | Organic rounded top surface with gentle terrain, a rocky craggy underside tapering to a point, hanging roots/vines, soil and rock strata visible at the edge. Floats in sky with soft clouds/haze below. |
| Pagoda | Five tiers, dark timber with vermilion or natural wood accents, white plaster walls, tiled roofs with **curved, upturned eaves** and visible roof tile ridges (geometry or normal map), bracket detail under eaves, stone plinth with steps, bronze sōrin spire with rings on top. Proportions of a real Japanese pagoda (each tier slightly smaller). |
| Cherry trees (5-8) | Procedural branching trunks with bark texture, dense blossom clusters (instanced cards or small meshes) with pink/white variation and translucency feel, some petals on the ground. Each tree different (seeded). |
| Falling petals | Instanced, curved/twisting petals drifting with wind, settling on ground and pond surface. Count controllable 0-3000. |
| Koi pond | Irregular natural edge with stones, reflective/refractive water with ripples and fresnel, visible depth (darker centre), lily pads, 5+ koi swimming with body wiggle (orange/white/black patterns). |
| Arched bridge | Wooden arched (taiko) bridge over the pond with railings, vermilion or weathered wood. |
| Torii gate | Vermilion with black kasagi top beam, proper curved top, stone bases. |
| Stone lanterns (3+) | Tōrō shape (base, pillar, light box, roof, finial), stone texture with moss, emissive warm light at night that lights the surroundings. |
| Vegetation | Instanced grass that sways in wind, moss patches, bamboo grove with segmented stalks and leaves, trimmed shrubs/hedges, small ferns or flowers. |
| Rocks | Natural rounded/angular rocks with stone texture, moss on top faces, partly embedded in ground. |
| Zen garden | Raked gravel bed with parallel/concentric rake lines (normal or displacement), a few placed rocks. |
| Stone path | Stepping stones or flagstone path linking torii, bridge and pagoda. |
| Sky and light | Physical sky with sun position from time of day, environment lighting that follows the sky (PMREM), soft shadows from the sun, fog/aerial perspective, sunset colours, night with moon light, stars, lantern glow and fireflies. |
| Post-processing | Tone mapping (ACES or AgX), ambient occlusion (GTAO/SSAO), bloom for lanterns and sun, anti-aliasing (SMAA/FXAA or MSAA), mild vignette. Toggleable. |

## Controls panel (top-left, collapsible)

Time of day slider (0-24), play/pause day cycle, cycle speed, petals count, wind strength, toggles
(auto-rotate, shadows, post-processing, fireflies, water animation, wireframe), quality (low/high),
camera presets (Overview, Pagoda, Pond, Torii, Underside), regenerate seed, reset view, FPS and draw-call
readout. Keyboard: 1-5 presets, Space auto-rotate, N jump day/night, R regenerate. Title in the top right:
`桜の庭`.

## URL parameters (for testing and the shot tool)

`seed=<int>` (deterministic layout), `time=<0-24>`, `paused=1` (freeze the day cycle and animations that
would make screenshots differ), `preset=<1-5>`, `quality=low|high`, `petals=<n>`, `wind=<0-3>`,
`post=0|1`, `ui=0` (hide panel for clean screenshots).

## Test contract: `window.__diag`

After the first rendered frame the page sets and keeps updating:

```js
window.__diag = { ready: true, seed, time, preset, quality, drawCalls, triangles, geometries, textures,
                  frameMs /* avg over last 60 frames */, petals, koi, trees, lights }
```

`tools/shot.mjs` reads it; `tools/views.json` lists the review views.

## Acceptance checks (all must pass for goal_complete)

1. `node tools/shot.mjs --all` exits 0: zero console errors, page errors or failed requests in every view.
2. FPS >= 55 in every view at 1600x900 with `quality=high` (headless caps near 60), and `drawCalls` < 600.
3. Every element in "Scene contents" is present and recognisable in at least one review screenshot
   (list which screenshot shows which element in the final handoff).
4. Realism rubric scores >= 4 on every line, judged by looking at the screenshots (see below).
5. Day cycle works: screenshots at time 9, 18.5 and 23 differ as expected (daylight, sunset, night with
   lantern glow, stars, fireflies).
6. All controls in the panel work (checked through URL params and by evaluating the handlers, see T14).
7. Total repo size of assets <= 80 MB; every downloaded asset listed in `assets/CREDITS.md`.
8. Page loads from a plain static server with no build step; works from `python3 -m http.server`.

## Realism rubric (score each 1-5 while looking at screenshots)

- **Materials**: surfaces read as wood, stone, plaster, water, bark, moss; roughness/normal variation;
  no flat single-colour surfaces in the foreground. 5 = could pass for a stylised offline render.
- **Lighting**: soft shadows, contact shadows/AO under objects, sky light tints shadows, believable sunset
  and night. No pitch-black or blown-out areas.
- **Shape**: organic silhouettes, curved roofs, no visible low-poly faceting on close objects, no blockiness.
- **Composition**: island fills the overview frame, pagoda is the focal point, depth via fog/haze, pleasing
  from every preset.
- **Motion**: grass, leaves, petals, water and koi move naturally; nothing jitters or pops.
- **Cleanliness**: no z-fighting, floating objects, clipping through the ground, shadow acne, or banding.

Write the scores into `.ai/handoff.md` each time you review.

## Reference

- The earlier voxel version: `~/code/Strata/docs/media/pagoda-preview.webp` (read it once to see layout:
  pagoda at the back centre, pond with bridge in front, torii at front-left, cherry trees around the edges,
  controls panel top-left). Match the layout and features, not the voxel look.
- Three.js r187 examples worth using: `webgl_shaders_sky` (Sky), `webgl_water` / `Water.js` / `Water2`,
  `webgl_postprocessing_gtao`, `UnrealBloomPass`, `SMAAPass`, `OutputPass`, `InstancedMesh`,
  `BufferGeometryUtils.mergeGeometries`, `SimplexNoise`.
- CC0 textures: ambientCG (https://ambientcg.com) or Poly Haven (https://polyhaven.com). 1K-2K maps
  (color, normal, roughness, AO) as JPG; KTX2 optional.
