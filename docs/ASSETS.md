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

## Requested external assets
None yet. Requests to the owner (ChatGPT/Gemini generated art/music) will be listed here with the prompt,
file name, usage and licence notes once delivered.
