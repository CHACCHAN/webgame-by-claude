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

## Car models from Sketchfab (owner request, private use)
The owner asked to replace the cars with Sketchfab models for a private game played by friends and family. The car
names and designs are trademarks / designs of their manufacturers (private, non-commercial use decided by the
owner). Attribution below is required by the licences and is also shown in the garage under each car.
The Sketchfab search API answers here, but downloads and images (`media.sketchfab.com`) are blocked, so the owner
downloads the glTF zips and attaches them (attachments up to ~20 MB have worked).

| Game id | Model | Author | Source | Licence | Status |
|---|---|---|---|---|---|
| `shiden` | Mazda RX-7 FD | Lexyc16 | https://sketchfab.com/3d-models/d35ff630df614771b82e7b2f59035b1e | CC BY 4.0 | **in game** (37 k tris, 0.65 MB) |
| `s15` | Nissan Silvia (S15) | Mona x Supercars (@Car2022) | https://sketchfab.com/3d-models/20a8388a009e4a7aae61a9bb50ad8945 | CC BY 4.0 | **in game** (49 k tris, 1.9 MB) |
| `raijin` | Subaru Impreza WRX STi 2004 Custom | Mac CGI (@MACCGI) | https://sketchfab.com/3d-models/08296bc950364621b6174a3078bb19e0 | CC BY 4.0 | **in game** (53 k tris, 0.57 MB) |
| `r34` | Nissan Skyline R34 GT-R | Lexyc16 | https://sketchfab.com/3d-models/ff8fb2251dfa4bb9979e7022c5a6666c | CC BY 4.0 | **in game** (50 k tris, 0.52 MB) |
| `supra` | Toyota Supra mk4 | Black Snow (@BlackSnow02) | https://sketchfab.com/3d-models/8bebdee25b774067929bb33e648533ac | CC BY 4.0 | **in game** (82 k tris, 1.1 MB), modified — see below |
| `hayate` | Toyota AE86 Sprinter Trueno Zenki | Martin Trafas (@TinoD2) | https://sketchfab.com/3d-models/a5737bf3cc9b4179a6e5ebe173ff70d9 | CC BY 4.0 | not delivered: 71.7 MB / 706 k tris, too large to attach (procedural car still used) |

AE86 replacements proposed to the owner (2026-11-01, both CC BY 4.0, picked with the Sketchfab search API by size,
licence and the author's other uploads): "Toyota Trueno AE86 (Initial D)" by Flamestroke
(https://sketchfab.com/3d-models/40c0a445f8fa42568c7ecf208b6d97bd, 4.5 MB, 157 k tris) and "Toyota Corolla AE86
Trueno" by Lexyc16 (https://sketchfab.com/3d-models/fe02fba6302e450ea8424591493341ea, 0.9 MB, 26 k tris).

Replaced and not used: the first R34 (@tangwang920) and Supra ("Versus 2F2F", Ddiaz Design, CC BY-NC-SA) files used
a commercial racing game's internal naming for meshes, materials and textures (`…SkylineGTRR34F2_1999…`,
`FnF_SupraMKIVF2_1994…`, "3DWheel Front L"), which suggests they were extracted from that game. The owner then
supplied the two models above instead.

Supra notes: a modified show car (Varis body kit, Chargespeed wheels, wing); its part and material names
(`esta80_*`, `sdd_*`) look like a car-mod author's naming, not a commercial game's, and the uploader licenses it
CC BY 4.0. Changes made for the game (the licence allows adaptation): the purple self-lit rims and exhaust tips
turned dark gunmetal, the red self-lit strips in the front bumper/headlamps turned off or made part of the white
headlamps, front indicators amber, tyre tread decimated (25 k → ~6 k triangles per axle), hidden duplicate interior
parts and invisible helper meshes dropped.

Processing (`tools/import-cars.cjs` + `tools/car-import.json`, converter `src/game/render/carImport.ts`): the glTF is
loaded with three.js in a headless browser, oriented to +Z forward (front detected from the headlamp parts), scaled
so the wheelbase matches the physics spec, ground at y = 0; wheel parts (merged meshes split by corner) become
`wheel_*`/`spin_*` pivots (calipers steer but do not spin) and are fitted to the physics wheel radius; paint /
glass / headlamp / taillamp materials are renamed to the game's swap names (paint colour selectable in the
garage, brake lights, headlights); hidden engine-bay parts of the S15 are dropped; optional per-part `restyle`
(colour / emissive / metalness / roughness) and error-bounded `reduce` (decimation of dense untextured parts such
as tyre tread). Then glTF-Transform `optimize`
(simplify where needed, WebP textures ≤ 1024 px — 512 px for the S15 —, meshopt; palette merge off so the
material names survive). The resulting GLBs are adaptations under the same licences.

## Scenery models proposed to the owner (2026-11-01, not delivered yet)
Picked with the Sketchfab search API (downloadable, CC BY 4.0, ≤ 10 MB glTF, author's own work going by the
description and uploads). Not used until delivered; integration would load them as instanced props.

| Use | Model (author) | Source | glTF size / tris |
|---|---|---|---|
| Road lights (sodium heads over the road) | Street Light (kloworks) | https://sketchfab.com/3d-models/2d44b333f56c4faaab1bd2007868cc37 | 9.4 MB / 0.6 k |
| — alternative, untextured set incl. sodium highway heads | Various Low-Poly Street Lights (kmb_jr) | https://sketchfab.com/3d-models/1173b0c4d9b0400bbeaafbee0e94ca59 | 0.2 MB / 11 k |
| Wind turbines (天狼スカイライン) | Animated Wind Turbine (glowbox3d) | https://sketchfab.com/3d-models/e0678e6615a74ed29c1376a591262159 | 3.7 MB / 3 k |
| Curve mirrors on blind corners | Blind spot traffic mirror (guru2fifa) | https://sketchfab.com/3d-models/6b7baf381f6c45ef8d92411e0467492b | 0.1 MB / 7.6 k |
| Roadside vending machine | Japan Vending Machine Soft Drink (ditovirnantio) | https://sketchfab.com/3d-models/431394ee886141349e187fb8dcc2307a | 3.1 MB / 12 |
| Roadside shrine | Japanese Torii Gate (sahirvirmani) | https://sketchfab.com/3d-models/2027a248de1b4b70985ff97e708fb50d | 5.6 MB / 1.3 k |
| Roadside shrine | Stone Lantern (jamiemcfarlane) | https://sketchfab.com/3d-models/4e674d91b33a450781aebd9c490b0f05 | 3.0 MB / 1.2 k |
| Rural bus stop | Kyoto Cityscene: Bus Stop (Xavaltir) | https://sketchfab.com/3d-models/5eb07fc3b28f474dbf15b1bbac814c82 | 2.4 MB / 6.6 k |
| Start-line props | Traffic Cone (jamiemcfarlane) | https://sketchfab.com/3d-models/66b282e65d3b4da8a883ae8579bfb33c | 2.4 MB / 0.7 k |

Looked at and left out: a "Jizo Mitama" upload that is a sword from a commercial game, a cartoon-style Japanese
street lamp (style clash), a wind turbine whose author asks not to redistribute it.

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
