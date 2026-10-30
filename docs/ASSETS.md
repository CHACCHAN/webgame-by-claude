# Asset ledger

Every asset in the game is listed here with its source, licence and modifications.

## Environment constraint
The cloud environment's network policy blocks the usual free asset hosts (polyhaven.com, kenney.nl,
quaternius.com, sketchfab.com, ambientcg.com, cdn.jsdelivr.net, unpkg.com). Visual assets are therefore
generated procedurally in code (original work of this project, same licence as the code).

| Asset | Where | Source / method | Licence | Notes |
|---|---|---|---|---|
| Car bodies (HAYATE TR-S, RAIJIN GT-X, SHIDEN RS) | `src/game/render/CarModel.ts` | Procedural lofted cross-sections, original designs | Project | Fictional cars; no real makes/logos |
| Wheels, tyres, brakes | `CarModel.ts` | Lathe/extrude geometry | Project | |
| Number plates | `CarModel.ts` | Canvas-drawn, fictional "朧" region | Project | |
| Terrain heightfields | `src/game/track/terrain.ts` | Noise + road-driven interpolation | Project | |
| Road, guardrails, walls, rock shed, bridge | `TrackScenery.ts`, `roadGeometry.ts` | Swept profiles along the centerline | Project | |
| Asphalt, concrete, lattice, ground textures | `src/game/render/textures.ts` | Canvas noise generators | Project | |
| Road signs (chevrons, hairpin, speed, pass board) | `textures.ts` | Canvas-drawn, generic Japanese road-sign style | Project | Generic symbols only |
| Trees, bushes, rocks | `TrackScenery.ts` | Instanced procedural meshes | Project | |
| Sky, moon, stars, clouds, sea of clouds | `Environment.ts` | GLSL shaders | Project | |
| City lights, traffic, ferris wheel | `Environment.ts` | Points shader | Project | |
| Engine / tyre / wind / UI sounds, menu pad | `src/game/audio/AudioEngine.ts` | WebAudio synthesis | Project | No samples |
| Fonts: Zen Kaku Gothic New, Shippori Mincho, Rajdhani | npm `@fontsource/*` | Google Fonts via Fontsource | SIL OFL 1.1 | Bundled, unmodified |
| Libraries | `frontend/package.json`, `backend/composer.json` | three.js (MIT), React (MIT), R3F (MIT), postprocessing (Zlib), Rapier (Apache-2.0), zustand (MIT), Laravel (MIT) | See packages | |

## 3D model pipeline (glTF / GLB)
1. Cars are authored procedurally (`buildProceduralCar`).
2. `tools/export-cars.cjs` exports them to GLB through a headless browser (three.js GLTFExporter).
3. `npm run assets:cars` optimises them with the glTF-Transform CLI (dedup, weld, meshopt compression).
4. At runtime `loadCarTemplates()` loads `public/models/cars/<id>.glb`; if a file is missing or broken the
   procedural builder is used instead.

**Replacing a car with an artist-made model** — export a GLB that follows this contract:
- metres, +Z = forward, +Y = up, ground at y = 0, origin between the axles;
- a node `body` (pitch/roll is applied to it) and wheel pivots `wheel_fl`, `wheel_fr`, `wheel_rl`, `wheel_rr`
  placed at the wheel centres, each with a child `spin_*` holding the rotating parts;
- optional empties `anchor_headlight_0..n`, `anchor_taillight_0..n`, `anchor_exhaust`, `headlight_target`;
- material names `paint`, `accent`, `glass`, `trim`, `chrome`, `headlight`, `taillight`, `tire`, `rim`, `brake`
  (these are swapped for tweakable runtime materials: paint colour, light emission).

## Requested external assets
See `docs/ASSET_REQUESTS.md` (race BGM, menu BGM, loading key art). Not delivered yet; the game falls back to
a synthesised ambient pad and the live 3D scene.
