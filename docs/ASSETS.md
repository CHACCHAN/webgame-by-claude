# Asset ledger

Every asset in the game is listed here with its source, licence and modifications.

## Environment constraint
At the start the cloud network policy blocked the free asset hosts, so the first assets were generated
procedurally in code (original work of this project, same licence as the code). The owner later allowed some
domains: `ambientcg.com` downloads work, `api.polyhaven.com` works but `dl.polyhaven.org` (the file host) is
still blocked, so Poly Haven files cannot be fetched. Every photo texture has a procedural fallback.

| Asset | Where | Source / method | Licence | Notes |
|---|---|---|---|---|
| Car bodies, procedural fallback | `src/game/render/CarModel.ts` | Procedural lofted cross-sections | Project | Used until / if the Sketchfab models below are missing |
| Wheels, tyres, brakes | `CarModel.ts` | Lathe/extrude geometry | Project | |
| Number plates | `CarModel.ts` | Canvas-drawn, fictional "朧" region | Project | |
| Terrain heightfields | `src/game/track/terrain.ts` | Noise + road-driven interpolation | Project | |
| Road, guardrails, walls, rock shed, bridge | `TrackScenery.ts`, `roadGeometry.ts` | Swept profiles along the centerline | Project | |
| Asphalt, concrete, lattice, ground textures (fallback) | `src/game/render/textures.ts` | Canvas noise generators | Project | Used when a photo texture below is missing |
| Road signs (chevrons, hairpin, speed, pass board) | `textures.ts` | Canvas-drawn, generic Japanese road-sign style | Project | Generic symbols only |
| Trees, bushes, rocks | `TrackScenery.ts` | Instanced procedural meshes | Project | |
| Sky, moon, stars, clouds, sea of clouds | `Environment.ts` | GLSL shaders | Project | |
| City lights, traffic, ferris wheel | `Environment.ts` | Points shader | Project | |
| Engine / tyre / wind / UI sounds, menu pad | `src/game/audio/AudioEngine.ts` | WebAudio synthesis | Project | No samples |
| Fonts: Zen Kaku Gothic New, Shippori Mincho, Rajdhani | npm `@fontsource/*` | Google Fonts via Fontsource | SIL OFL 1.1 | Bundled, unmodified |
| Libraries | `frontend/package.json`, `backend/composer.json` | three.js (MIT), React (MIT), R3F (MIT), postprocessing (Zlib), Rapier (Apache-2.0), zustand (MIT), pusher-js (MIT), Laravel (MIT), Laravel Reverb (MIT) | See packages | |

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

## Photo textures (CC0)
Downloaded from ambientCG (https://ambientcg.com, CC0 1.0 — no attribution required, credited here anyway) on
2026-10-30, 1K-JPG packages. Converted to WebP with ImageMagick; loaded by `render/surfaceTextures.ts`.

| File (`frontend/public/textures/`) | ambientCG asset | Map | Processing |
|---|---|---|---|
| `asphalt_albedo.webp` | Asphalt025C | Color | ×1.7 brightness (matches the lamp lightmap balance); tiled 2.7 m into the road canvas under the markings |
| `asphalt_normal.webp` | Asphalt025C | NormalGL | quality 90 |
| `asphalt_rough.webp` | Asphalt025C | Roughness | grey, remapped `0.8 + (v − 0.44) × 3`, 512 px |
| `ground_detail.webp` | Ground037 | Color | greyscale, remapped `0.78 + (v − 0.56) × 1.3` (multiplied with the terrain vertex colours) |
| `ground_normal.webp` | Ground037 | NormalGL | quality 90 |
| `rock_albedo.webp` / `rock_normal.webp` | Rock030 | Color / NormalGL | 512 px, colour ×1.35 |
| `concrete_albedo.webp` / `concrete_normal.webp` | Concrete034 | Color / NormalGL | 512 px, colour ×0.82; lattice frames and weathering are drawn on top |

## Car models from Sketchfab (owner request, private use) — files pending
The owner asked to replace the cars with these models for a private game played by friends and family. All six
are **CC Attribution 4.0** (free download); attribution below must stay in the game credits and here. The car
names and designs are trademarks / designs of their manufacturers (private, non-commercial use decided by the
owner). Files are not in the repository yet: `api.sketchfab.com` is blocked in this environment and Sketchfab
downloads need a logged-in account, so the owner provides them (see PROGRESS).

| Game id | Model | Author | Source | Licence |
|---|---|---|---|---|
| `hayate` | Toyota AE86 Sprinter Trueno Zenki | Martin Trafas (@TinoD2) | https://sketchfab.com/3d-models/a5737bf3cc9b4179a6e5ebe173ff70d9 | CC BY 4.0 |
| `supra` | Toyota Supra Mk4 | MiguelG19 | https://sketchfab.com/3d-models/7b814545bf7148aba70b7af03b0f2817 | CC BY 4.0 |
| `r34` | 1999 Nissan Skyline GTR R34 | 007 (@tangwang920) | https://sketchfab.com/3d-models/facbb68395044ac3a22de327d72da9ea | CC BY 4.0 |
| `shiden` | Mazda RX-7 FD | Lexyc16 | https://sketchfab.com/3d-models/d35ff630df614771b82e7b2f59035b1e | CC BY 4.0 |
| `raijin` | Subaru Impreza WRX STi 2004 Custom | MAC ULT ARTS (@MACULTARTS) | https://sketchfab.com/3d-models/08296bc950364621b6174a3078bb19e0 | CC BY 4.0 |
| `s15` | Nissan Silvia (S15) | Mona x Supercars (@Car2022) | https://sketchfab.com/3d-models/20a8388a009e4a7aae61a9bb50ad8945 | CC BY 4.0 |

Planned processing (to be recorded per file when done): glTF-Transform (dedup, simplify to a web budget —
the AE86 and Supra are ~0.7 M faces —, textures resized to ≤ 2048 px WebP, meshopt), re-rooted to the game's
car contract (wheel pivots, paint/light materials), scaled to the real dimensions.

## Owner-supplied generated assets
Generated by the owner with ChatGPT (images) and Gemini (music, video) from the prompts in
`docs/ASSET_REQUESTS.md`, and delivered through the chat on 2026-10-30. The owner checks those services' terms
for commercial use.

| File (`frontend/public/`) | Source | Processing | Used in |
|---|---|---|---|
| `audio/bgm_menu.mp3` | Gemini | loudnorm −16 LUFS, 144 kbps; loop 0–149 s, 4 s crossfade | title / menus |
| `audio/bgm_race.mp3` | Gemini | loudnorm −16 LUFS, 144 kbps; loop 39–164.5 s, 1.5 s crossfade | races (all courses until per-course tracks arrive) |
| `audio/jingle_finish.mp3` | Gemini | last 8.3 s of the delivered 63 s track (from 55.3 s) | finish line (synth chime fallback) |
| `video/loading_loop.mp4`, `video/loading_poster.webp` | Gemini | ping-pong loop to 20 s, audio removed, H.264 CRF 30; poster frame | boot / loading screen, dimmed |
| `img/rivals/oboro-{rookie,ace,legend}.webp` | ChatGPT | 768×1152 WebP with alpha | rival cards, battle HUD |
| `img/keyart.webp`, `img/og.jpg` | ChatGPT | 1600 px WebP; 1200×630 crop for social cards | course card / loading art, `og:image` |
| `img/rivals/tenrou-{rookie,ace,legend}.webp` | ChatGPT (batch 2) | 1024×1536 PNG with alpha → 768×1152 WebP (q85, alpha q90) | 天狼スカイライン rival cards, battle HUD |
| `img/rivals/kirifuri-rookie.webp` | ChatGPT (batch 2, re-sent) | 1024×1536 PNG with alpha → 768×1152 WebP (q85, alpha q90) | 霧降湖 rival card (椎名 ほのか), battle HUD |
| `img/rivals/kirifuri-ace.webp` | ChatGPT (batch 2, re-sent) | same processing | 霧降湖 rival card (九条 迅), battle HUD |
| `img/rivals/kirifuri-legend.webp` | ChatGPT (batch 2, re-sent) | same processing | 霧降湖 rival card (霧姫), battle HUD |
| `img/courses/kirifuri.webp` | ChatGPT (batch 2, re-sent) | 1672×941 PNG → 1600×900 WebP q84 | 霧降湖 course card, loading screen |
| `img/courses/tenrou.webp` | ChatGPT (batch 2) | 1536×1024 WebP q84 | 天狼 course card, loading screen |
| `audio/bgm_race_kirifuri.mp3` | Gemini (batch 2) | 172 s; two-pass loudnorm −15 LUFS, 128 kbps; loop 72.37–159.63 s (matching end-of-chorus points found by spectral comparison), 1.5 s crossfade | 霧降湖 races |
| `audio/bgm_race_tenrou.mp3` | Gemini (batch 2) | 174 s; same processing; loop 94.25–145.46 s | 天狼スカイライン races |
| `audio/jingle_lose.mp3` | Gemini (batch 2) | delivered as a 61.6 s track: the final phrase from 52.92 s (bar-aligned at 123 BPM) through the release, 8.0 s, fades in/out, −17 LUFS | results after losing a rival battle (synth fallback) |

Caution noted to the owner: the coupe in the delivered key art looks close to a real 1980s production car.
It is used only as a background illustration; replacing it with a more clearly fictional car is recommended
before any public release.

## Still requested
Nothing outstanding. Every course has its portraits, key art and race music.
