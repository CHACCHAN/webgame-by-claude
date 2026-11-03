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
In cloud sessions the Sketchfab search API answers but downloads and images (`media.sketchfab.com`) are blocked, so
the owner downloads the glTF zips and attaches them (attachments up to ~20 MB have worked). On the owner's PC the
owner puts the zips into `~/Downloads` (2026-11-02).

| Game id | Model | Author | Source | Licence | Status |
|---|---|---|---|---|---|
| `shiden` | Mazda RX-7 FD | Lexyc16 | https://sketchfab.com/3d-models/d35ff630df614771b82e7b2f59035b1e | CC BY 4.0 | **in game** (37 k tris, 0.65 MB) |
| `s15` | Nissan Silvia (S15) | Mona x Supercars (@Car2022) | https://sketchfab.com/3d-models/20a8388a009e4a7aae61a9bb50ad8945 | CC BY 4.0 | **in game** (49 k tris, 1.9 MB) |
| `raijin` | Subaru Impreza WRX STi 2004 Custom | Mac CGI (@MACCGI) | https://sketchfab.com/3d-models/08296bc950364621b6174a3078bb19e0 | CC BY 4.0 | **in game** (53 k tris, 0.57 MB) |
| `r34` | Nissan Skyline R34 GT-R | Lexyc16 | https://sketchfab.com/3d-models/ff8fb2251dfa4bb9979e7022c5a6666c | CC BY 4.0 | **in game** (50 k tris, 0.52 MB) |
| `supra` | Toyota Supra mk4 | Black Snow (@BlackSnow02) | https://sketchfab.com/3d-models/8bebdee25b774067929bb33e648533ac | CC BY 4.0 | **in game** (82 k tris, 1.1 MB), modified — see below |
| `hayate` | Toyota Corolla AE86 Trueno | Lexyc16 | https://sketchfab.com/3d-models/fe02fba6302e450ea8424591493341ea | CC BY 4.0 | **in game** (26 k tris, 0.2 MB), modified — see below |

AE86 notes: chosen over the other delivered candidate, "Toyota Trueno AE86 (Initial D)" by Flamestroke
(https://sketchfab.com/3d-models/40c0a445f8fa42568c7ecf208b6d97bd, 157 k tris at 1/10 scale; delivered, not used),
and the first link (Martin Trafas, 71.7 MB, never delivered). Changes for the game: the anime tie-ins are taken
out — the tofu-shop door decal is dropped and the number plates (the film car's registration) are blank white —,
the yellow rear lens no longer glows, and the pop-up headlamps, modelled raised, are cut out at import into hinged
pods (`CarImportConfig.popUps`) that fold flush into the bonnet by day and rise and light up at night. The model's
bonnet is the black carbon look of the original upload.

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

## Scenery models (Sketchfab, CC BY 4.0, delivered by the owner 2026-11-02)
Picked with the Sketchfab search API (downloadable, CC BY 4.0, ≤ 10 MB glTF, author's own work going by the
description and uploads). Optimised with `tools/import-props.cjs` (+ `tools/props-import.json`: meshopt, WebP
textures ≤ 256–1024 px) into `frontend/public/models/props/*.glb` (1.1 MB together); size, orientation and origin
are set at load (`PROPS` in `src/game/render/props.ts`) and they are drawn instanced. The GLBs are adaptations under
the same licence. Credits (as the licence files give them):

| Use in game | Model | Author | Source | Tris |
|---|---|---|---|---|
| every street light (glass tinted sodium / LED, lit at night) | Street Light | KloWorks | https://sketchfab.com/3d-models/2d44b333f56c4faaab1bd2007868cc37 | 0.6 k |
| wind turbines on 天狼 (rotor turns) | Animated Wind Turbine | Glowbox 3D | https://sketchfab.com/3d-models/e0678e6615a74ed29c1376a591262159 | 3 k |
| curve mirrors at the tight bends | Blind spot traffic mirror | guru2fifa | https://sketchfab.com/3d-models/6b7baf381f6c45ef8d92411e0467492b | 7.6 k |
| vending machines at the summit (front lit at night) | Japan Vending Machine Soft Drink | ditovirnantio | https://sketchfab.com/3d-models/431394ee886141349e187fb8dcc2307a | 12 |
| roadside shrine, one per course | Japanese Torii Gate | Sahir Virmani | https://sketchfab.com/3d-models/2027a248de1b4b70985ff97e708fb50d | 1.3 k |
| roadside shrine (two lanterns) | Stone Lantern | Jamie McFarlane | https://sketchfab.com/3d-models/4e674d91b33a450781aebd9c490b0f05 | 1.2 k |
| bus shelter, one per course (its utility pole, crossarm and lamp are left out at load: `PropDef.drop`) | Kyoto Cityscene: Bus Stop | Mikail Karaca (Xavaltir) | https://sketchfab.com/3d-models/5eb07fc3b28f474dbf15b1bbac814c82 | 6.6 k |
| cones at the start and finish gantries | Traffic Cone | Jamie McFarlane | https://sketchfab.com/3d-models/66b282e65d3b4da8a883ae8579bfb33c | 0.7 k |

Delivered, not used: Various Low-Poly Street Lights (KMB3D, https://sketchfab.com/3d-models/1173b0c4d9b0400bbeaafbee0e94ca59)
— mostly park-style lamps; the KloWorks road light fits the pass. The vending machine texture is a photo of a
real machine (drink and maker logos visible).

Looked at and left out: a "Jizo Mitama" upload that is a sword from a commercial game, a cartoon-style Japanese
street lamp (style clash), a wind turbine whose author asks not to redistribute it.

## Owner-supplied generated assets
Generated by the owner with ChatGPT (images), Gemini (video) and Suno (music, see below) from the prompts in
`docs/ASSET_REQUESTS.md`, and delivered through the chat on 2026-10-30. The owner checks those services' terms
for commercial use.

| File (`frontend/public/`) | Source | Processing | Used in |
|---|---|---|---|
| `video/loading_loop.mp4`, `video/loading_poster.webp` | Gemini | ping-pong loop to 20 s, audio removed, H.264 CRF 30; poster frame | boot / loading screen, dimmed |
| `img/rivals/oboro-{rookie,ace,legend}.webp` | ChatGPT | 768×1152 WebP with alpha | rival cards, battle HUD |
| `img/keyart.webp`, `img/og.jpg` | ChatGPT | 1600 px WebP; 1200×630 crop for social cards | course card / loading art, `og:image` |
| `img/rivals/tenrou-{rookie,ace,legend}.webp` | ChatGPT (batch 2) | 1024×1536 PNG with alpha → 768×1152 WebP (q85, alpha q90) | 天狼スカイライン rival cards, battle HUD |
| `img/rivals/kirifuri-rookie.webp` | ChatGPT (batch 2, re-sent) | 1024×1536 PNG with alpha → 768×1152 WebP (q85, alpha q90) | 霧降湖 rival card (椎名 ほのか), battle HUD |
| `img/rivals/kirifuri-ace.webp` | ChatGPT (batch 2, re-sent) | same processing | 霧降湖 rival card (九条 迅), battle HUD |
| `img/rivals/kirifuri-legend.webp` | ChatGPT (batch 2, re-sent) | same processing | 霧降湖 rival card (霧姫), battle HUD |
| `img/courses/kirifuri.webp` | ChatGPT (batch 2, re-sent) | 1672×941 PNG → 1600×900 WebP q84 | 霧降湖 course card, loading screen |
| `img/courses/tenrou.webp` | ChatGPT (batch 2) | 1536×1024 WebP q84 | 天狼 course card, loading screen |

### Train models (joke entries, Sketchfab)
Downloaded by the owner on 2026-11-03; three cars (leading, middle, trailing) cut out of each with
`frontend/tools/import-trains.cjs` (`tools/train-import.json`: cuts at the gangways found from the bogie spacing,
triangles crossing a cut clipped, materials collapsed to vertex colours + one mesh per texture, glass made dark,
E231 converted from spec-gloss to metal-rough, N700 simplified to 35 %), scaled to the real car length / width,
written to `frontend/public/models/trains/<id>.glb`. Credits also in the car list (CarSpec.model).

| Train | Model | Author | License |
|---|---|---|---|
| E231 (`e231`) | [JR東日本E231系電車](https://sketchfab.com/3d-models/98d47a9e4aca454d9c02eb2c690fdaee) | own.guest | CC BY 4.0 |
| 117 (`jr117`) | [117系 サンライナー](https://sketchfab.com/3d-models/6434932c06974d10927c2fe36c2c7f8e) | own.guest | CC BY 4.0 |
| 京成3300 (`keisei3300`) | 京成3300形(赤電) [先頭車1](https://sketchfab.com/3d-models/366d6c3ecfc5415ab21627a5c1165a7d)・[中間車1](https://sketchfab.com/3d-models/8e8c924b5ce145e99738b9a23c73c685)・[先頭車2](https://sketchfab.com/3d-models/86b11eb7639642e897cc2ef5ae2ad23f) | V3B4 | CC BY-NC 4.0 (non-commercial: the owner confirmed the site is non-commercial) |
| 銀座線1000 (`ginza1000`) | [Japan Train Tokyo Metro Ginza Line (low poly)](https://sketchfab.com/3d-models/dc622d519f8d4b7ab1fd478815d129f8) | ditovirnantio | CC BY 4.0 |
| N700 (`n700`) | [N700-3000 Series Shinkansen](https://sketchfab.com/3d-models/f70820be44e0467d8b1614f2aa3045bd) | Layo (bciarfello) | CC BY 4.0 |

Train performance figures (vehicle/trains.ts) are from Japanese Wikipedia (2026-11-03); masses marked as estimates
in the game where no per-car figure is published.

### Train sounds (Wikimedia Commons recordings, VVVF patterns)
Found by searches of Commons / Freesound / Japanese free sound sites / VVVF simulators (2026-11-03; Freesound needs
a login, the Japanese sites only have generic train sounds and forbid redistribution, BVE sound sets have no open
licence). Downloaded from Commons (no login), cut, mono 32 kHz, MP3 96 kbps, `frontend/public/audio/`. Credits
also in the settings screen. The files cut from CC BY-SA recordings are themselves CC BY-SA 3.0.

Motor (under power / braking), resistor-control trains: a recording of a start followed by speed
(`TrainInfo.motorSound`, speed from a motor tone line or the real acceleration):

| Train | Recording (Commons file) | Author | License | Clip |
|---|---|---|---|---|
| 117 | [JR_west_117_shinkaisoku_moha117-15_akashi.ogg](https://commons.wikimedia.org/wiki/File:JR_west_117_shinkaisoku_moha117-15_akashi.ogg) (on board MoHa 117-15) | spaceaero2 | CC BY 3.0 | `motor_jr117`: 700–862 s |
| 京成3300 (stand-in: Keikyu's first 1000 series) | [Keikyu_kyu1000kei_rokuon.ogg](https://commons.wikimedia.org/wiki/File:Keikyu_kyu1000kei_rokuon.ogg) | toshinori baba | Public domain | `motor_keisei3300`: 198–248 s |

Motor, VVVF trains (E231, 銀座線1000, N700): the in-train sound calculated by a port of **VVVF Simulator**
(VvvfGeeks, https://github.com/VvvfGeeks/VVVF-Simulator; terms: free for non-commercial use only, link to the
project; the owner approved the port on 2026-11-03): the inverter's PWM, the induction motor's torque ripple and the
simulator's in-train impulse response (`Generation/Audio/TrainSound/Filter.wav` → `frontend/public/audio/vvvf-filter.wav`,
unchanged). Code: `frontend/src/game/audio/vvvf/` (sim.ts, data.ts, math.ts are the port; checked sample by sample
against the simulator's own C# files, `frontend/tools/vvvf-ref/`). Control patterns in the simulator's YAML format,
`frontend/tools/vvvf/` → JSON in `audio/vvvf/patterns/`:

| Train | Pattern | Source |
|---|---|---|
| E231 | `JRE_E231_MITSUBISHI` | VvvfGeeks / YAML-Files (https://github.com/VvvfGeeks/YAML-Files, fans' recreations, "not exactly the same as the original"; no licence file, used with credit and link, non-commercial) |
| 銀座線1000 | `JRW_207-2000_TOSHIBA_IGBT` (stand-in: no PMSM pattern published) | VvvfGeeks / YAML-Files |
| N700 | `N700_ESTIMATE` (ours) | an estimate in the same format from public facts (3-level IGBT, ~1.5 kHz switching, ~25 s asynchronous after a start: Nagoya Univ. OCW lecture, Wikipedia) |

Credits also in the settings screen.

Running noise (always while moving; `TrainInfo.runningSound`, a seamless loop played faster or slower with speed):

| Trains | Recording (Commons file) | Author | License | Loop |
|---|---|---|---|---|
| E231, 銀座線1000 | [TOSHIBA_Omi_imazu-Shin_asahi_M'_222-3031Dasei.ogg](https://commons.wikimedia.org/wiki/File:TOSHIBA_Omi_imazu-Shin_asahi_M%27_222-3031Dasei.ogg) (223-2000 coasting) | 321keiHIKARI (ja.wikipedia) | CC BY-SA 3.0 | `run_emu`: 22–88 s, ~110 km/h |
| 117, 京成3300 | the 117 recording above | spaceaero2 | CC BY 3.0 | `run_jr117`: 898–962 s, ~105 km/h |
| N700 | [JR_central_700series_nozomi_387_717-53_shinosaka.ogg](https://commons.wikimedia.org/wiki/File:JR_central_700series_nozomi_387_717-53_shinosaka.ogg) (700 series, on board) | spaceaero2 | CC BY 3.0 | `run_n700`: 338–402 s, ~203 km/h |

### Cockroach model (joke entry, Sketchfab)
Downloaded by the owner on 2026-11-03 (the owner asked for it; picked from a shortlist of CC models). Optimised with
the glTF-Transform CLI (meshopt, WebP textures at 1024 px, skin and the "Take 001" scuttle cycle kept) to
`frontend/public/models/roach/roach.glb` (9.9 MB → 0.5 MB); scaled and tinted at runtime (`render/RoachModel.ts`).
Credit also in the car list (CarSpec.model).

| Vehicle | Model | Author | License |
|---|---|---|---|
| ゴキブリ (`roach`) | [Cockroach](https://sketchfab.com/3d-models/cockroach-cead55b8aa8643d48d67240bad028592) | CK (xcellf) | CC BY 4.0 |

### Music: Suno Pro (batch 3)
All music was remade by the owner with Suno (Pro plan, which grants commercial use of songs made while subscribed)
from the prompts in `docs/ASSET_REQUESTS.md` (batch 3: frenchcore / uptempo hardcore / speedcore), generated and
delivered on 2026-11-02 as 48 kHz AAC (`.m4a`), replacing the Gemini tracks. Every file: gain-only loudness match
(BGM −15.4 LUFS, jingles −16.4 LUFS, no limiter), MP3 160 kbps CBR 48 kHz. Loop points (`MUSIC` in
`AudioEngine.ts`): the pair of moments whose next 8 s sound most alike (mel-spectrum self-similarity), moved onto the
same beat phase; a seam preview was sent to the owner.

| File (`frontend/public/audio/`) | Length | Loop (crossfade) | Used in |
|---|---|---|---|
| `bgm_menu.mp3` | 204 s | 55.77–184.62 s (4 s) | title, menus, course select |
| `bgm_garage.mp3` | 167 s | 9.57–141.8 s (2 s) | car select |
| `bgm_race.mp3` | 199 s | 59.49–176.79 s (1.5 s) | 朧峠 time attack / online, night |
| `bgm_race_kirifuri.mp3` | 202 s | 4.5–184.83 s (2 s) | 霧降湖 time attack / online, night |
| `bgm_race_tenrou.mp3` | 200 s | 50.43–185.33 s (1.5 s) | 天狼 time attack / online, night |
| `bgm_race_rain.mp3` | 176 s | 49.69–145.98 s (1.5 s) | time attack / online in the rain |
| `bgm_race_dawn.mp3` | 188 s | 59.26–159.83 s (2 s) | time attack / online at dawn |
| `bgm_rival.mp3` | 182 s | 71.14–163.75 s (2 s) | rival battles |
| `bgm_ghost.mp3` | 198 s | 73.84–184.94 s (1.5 s) | ghost battles |
| `bgm_results.mp3` | 167 s | 18.76–136.51 s (3 s) | results, replay, online results (after the jingles) |
| `bgm_online.mp3` | 120 s | 23.59–99.38 s (2 s) | online lobby and room |
| `jingle_finish.mp3` | 4.8 s | – | finish line |
| `jingle_lose.mp3` | 4.4 s | – | losing to the rival or an online opponent |
| `jingle_rival_win.mp3` | 6.4 s | – | beating the rival |
| `jingle_medal.mp3` | 4.4 s | – | results: a new medal |
| `jingle_record.mp3` | 4.8 s | – | results: a new local record (not the first run) |

Caution noted to the owner: the coupe in the delivered key art looks close to a real 1980s production car.
It is used only as a background illustration; replacing it with a more clearly fictional car is recommended
before any public release.

## Still requested
Sound effects (Suno Sounds, WAV): generated, waiting for download (see HANDOVER §3).
