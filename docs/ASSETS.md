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
| Fonts: Saira (variable), Zen Kaku Gothic New, Shippori Mincho | npm `@fontsource/*` | Google Fonts via Fontsource | SIL OFL 1.1 | Bundled, unmodified |
| Libraries | `frontend/package.json`, `backend/composer.json` | three.js (MIT), React (MIT), R3F (MIT), postprocessing (Zlib), Rapier (Apache-2.0), zustand (MIT), pusher-js (MIT), Laravel (MIT), Laravel Reverb (MIT) | See packages | |
| Upscaler (WebGPU): FSR 3's upscaling | npm `@pmndrs/upscaler` 0.5.0 (exact version in `frontend/package.json`), used by `frontend/src/game/render/sceneUpscale.ts` | https://github.com/pmndrs/upscaler, by Dennis Smolek (Poimandres): the FSR 2 / 3 temporal upscaling pass graph and FSR 1's EASU / RCAS as raw WGSL compute passes for three.js' `WebGPURenderer`. No frame generation (the package leaves it out: browsers give no frame pacing). An independent implementation, not AMD's SDK: its EASU / RCAS shaders are ports of AMD's `ffx_fsr1.h`, the temporal path follows FidelityFX Super Resolution 2 / 3's architecture | MIT: © 2026 Dennis Smolek; the shaders derived from FidelityFX Super Resolution © 2021-2023 Advanced Micro Devices, Inc., MIT (both notices in `frontend/node_modules/@pmndrs/upscaler/LICENSE`) | Code dependency, unmodified; added 2026-11-12 at the owner's request. "FSR" and "FidelityFX" are AMD's names |
| Upscaler (WebGL 2 backend): FSR 1 | three.js `examples/jsm/tsl/display/FSR1Node.js` (`fsr1()`), unmodified | Part of three.js (EASU + RCAS after AMD's FidelityFX FSR 1) | MIT (three.js authors; AMD's FSR 1 is MIT) | |

## 3D model pipeline (glTF / GLB)
1. Every car is our own Blender model: a Python script per car (`frontend/tools/blender/cars/<id>.py`, headless
   Blender 5.2), fitted to photos (measuring only) with the data in `fitdata/<id>/`.
2. `node tools/blender-models.cjs cars [ids]` builds and optimises them with glTF-Transform (meshopt, WebP).
3. At runtime `loadCarTemplates()` loads `public/models/cars/<id>.glb`; if a file is missing or broken the
   procedural builder (`buildProceduralCar`) is used instead.

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

### Layers of the ground and the roadside (2026-11-11)
For the layered materials of quality medium and up (`render/terrainMaterial.ts`, `render/roadMaterial.ts`,
`render/structureMaterials.ts`). ambientCG 1K-JPG packages (CC0 1.0), downloaded 2026-11-11 and built by
`node tools/surface-textures.cjs` (sharp) into `frontend/public/textures/terrain/{1024,512}/`: `<layer>_c.webp` =
Color with the Displacement map in alpha (from 96 to 255), `<layer>_n.webp` = NormalGL.

| Layer | ambientCG asset | Used for |
|---|---|---|
| `rock` | Rock030 | steep faces and cuttings (textured from the sides) |
| `floor` | Ground023 | the forest's floor |
| `moss` | Ground037 | gentle open ground of the mountain courses |
| `grass` | Grass004 | meadows, the land above the tree line, the autobahn's verges |
| `gravel` | Gravel040 | the verge along the road, towns |
| `shotcrete` | Concrete035 (Color and Displacement only) | sprayed slopes |
| `concrete` | Concrete034 | kerbs, gutters, copings, slope frames, rock shed, bridge, the autobahn's structures |

Our own, drawn in code by the same tool (no source images): `blockwall_c/n` (the wall of sloped blocks with its weep
holes), `shotcrete_n` (the sprayed concrete's lumps), `roadmarks` (cracks, cells, grit for the road's wear),
`terrain/macro.webp` (slow noises), `terrain/wiremesh.webp` (the rockfall fence's net).

## Car models (all our own since 2026-11-10; Sketchfab models before)
Since 2026-11-10 every car is our own Blender model (table below); no third-party car model is left in the game.
History: the owner first asked to replace the cars with Sketchfab models for a private game played by friends and family. The car
names and designs are trademarks / designs of their manufacturers (private, non-commercial use decided by the
owner). Attribution below is required by the licences and is also shown in the garage under each car.
In cloud sessions the Sketchfab search API answers but downloads and images (`media.sketchfab.com`) are blocked, so
the owner downloads the glTF zips and attaches them (attachments up to ~20 MB have worked). On the owner's PC the
owner puts the zips into `~/Downloads` (2026-11-02).

| Game id | Model | Author | Source | Licence | Status |
|---|---|---|---|---|---|
| `shiden` | Mazda RX-7 FD3S (late Type RS) | **own** (Blender, `tools/blender/cars/shiden*.py`) | — | own | **in game** since 2026-11-08 (57 k tris, 0.33 MB); rebuilt 2026-11-12 with `car_common.py` (71 k tris, 0.54 MB, 9 materials: tyres, brakes, underside, two atlases, baked sky share); fitted to 10 Commons photos (measuring only, `fitdata/shiden/ref/list.json`) Round two 2026-11-18: the cabin's furniture from the shared kit (77 k tris, 0.58 MB); shape untouched, precision gate: nothing worse. |
| `s15` | Nissan Silvia S15 spec-R | **own** (Blender, `tools/blender/cars/s15*.py`) | — | own | **in game** since 2026-11-10 (48 k tris, 0.29 MB); rebuilt 2026-11-18 with `car_common.py` (64 k tris, 0.52 MB, 8 materials: profiled tyres, vented discs with four-pot calipers ahead of the front axle, cabin furniture, underside with the silencer across the tail, two atlases, baked sky share; the shape is unchanged); fitted to 7 Commons photos (measuring only, `fitdata/s15/ref/list.json`) |
| `raijin` | Subaru Impreza WRX STI (GDB-C, 2004) | **own** (Blender, `tools/blender/cars/raijin*.py`) | — | own | **in game** since 2026-11-10 (49 k tris, 0.44 MB); rebuilt 2026-11-18 with `car_common.py` (67 k tris, 0.57 MB, 9 materials: profiled tyres, vented discs and gold four-pot calipers, cabin furniture, underside with the silencer across the tail, two atlases, baked sky share; arch lips 4.5 mm proud instead of 10, their saw-toothed inner edge mended; the shape is otherwise unchanged); fitted to 5 of the 20 listed Commons photos (measuring only, `fitdata/raijin/ref/list.json`) |
| `r34` | Nissan Skyline GT-R (BNR34, V-spec look) | **own** (Blender, `tools/blender/cars/r34*.py`) | — | own | **in game** since 2026-11-10 (57 k tris, 0.56 MB); rebuilt 2026-11-12 with `car_common.py` (75 k tris, 0.80 MB, 9 materials: tyres, brakes, underside, two atlases, baked sky share); fitted to 6 of the 39 listed Commons photos (measuring only, `fitdata/r34/ref/list.json`) Round two 2026-11-18: tail panel 6 cm further back, rear wing swelling out of the door, bonnet table, arch lips (width over them 1,786 mm), cabin (87 k tris, 0.91 MB); the rear silencer across the car behind the axle and the tank ahead of it (it hung under the diffuser); precision gate: nothing worse, tail-lamp anchor 23 mm further back. |
| `cybertruck` | Tesla Cybertruck (Cyberbeast) | **own** (Blender, `tools/blender/cars/cybertruck*.py`) | — | own | **in game** since 2026-11-10 (39 k tris, 0.27 MB); fitted to 6 of the 10 listed Commons photos (measuring only, `fitdata/cybertruck/ref/list.json`) |
| `supra` | Toyota Supra RZ (JZA80, late, factory wing) | **own** (Blender, `tools/blender/cars/supra*.py`) | — | own | **in game** since 2026-11-10 (73 k tris, 0.47 MB); rebuilt 2026-11-18 with `car_common.py` (93 k tris, 0.73 MB, 8 materials: profiled tyres, vented discs and four-pot calipers, cabin furniture, underside with the silencer across the tail, two atlases, baked sky share; the shape is unchanged); fitted to 7 Commons photos (measuring only, `fitdata/supra/photos.json`) |
| `hayate` | Toyota Sprinter Trueno AE86 GT-APEX (late) | **own** (Blender, `tools/blender/cars/hayate*.py`) | — | own | **in game** since 2026-11-07 (42 k tris, 0.27 MB); rebuilt 2026-11-12 with `car_common.py` (51 k tris, 0.51 MB, 10 materials: tyres, brakes, underside, two atlases, baked sky share, sill steps, wiper, antenna, plate and reverse lamps); fitted to 6 Commons photos (measuring only, `fitdata/hayate/ref/list.json`) Round two 2026-11-18: front bumper face 46 mm lower (measured against the traced lamps), arch lips inside 1,625 mm, aerial stub, cabin (57 k tris, 0.56 MB); precision gate: nothing worse, traced-lens IoU 0.23 -> 0.39. |

Notes on the replaced Sketchfab models (none is in the game any more):

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

Processing (the import tools `import-cars.cjs`, `car-import.json` and `render/carImport.ts` were removed on 2026-11-10 once every car was our own): the glTF was
loaded with three.js in a headless browser, oriented to +Z forward (front detected from the headlamp parts), scaled
so the wheelbase matches the physics spec, ground at y = 0; wheel parts (merged meshes split by corner) become
`wheel_*`/`spin_*` pivots (calipers steer but do not spin) and are fitted to the physics wheel radius; paint /
glass / headlamp / taillamp materials are renamed to the game's swap names (paint colour selectable in the
garage, brake lights, headlights); hidden engine-bay parts of the S15 are dropped; optional per-part `restyle`
(colour / emissive / metalness / roughness) and error-bounded `reduce` (decimation of dense untextured parts such
as tyre tread). Then glTF-Transform `optimize`
(simplify where needed, WebP textures ≤ 1024 px — 512 px for the S15 —, meshopt; palette merge off so the
material names survive). The resulting GLBs are adaptations under the same licences.

## Scenery models (own, Blender)
Since 2026-11-03 every scenery model is our own: built from numbers by Python scripts in Blender 5.2 LTS
(`frontend/tools/blender/props/<id>.py`, headless) and optimised by `node tools/blender-models.cjs props`
(meshopt, WebP) into `frontend/public/models/props/*.glb`; size, facing and origin are set in `PROPS`
(`src/game/render/props.ts`), placement in `TrackScenery.ts`. Each model falls back to its procedural shape when it
fails to load. No third-party geometry or textures; dimensions from public figures and photos (used for measuring
only). Street light, wind turbine (rotor turns), curve mirror, vending machine (front lit at night; generic drinks,
no brands or logos), torii, stone lantern, bus stop, traffic cone.
Re-modelled 2026-11-12 (all thirteen, the AUTOBAHN's five included): real construction (footings, base plates and
anchor bolts, brackets, hinges, gutters, wedges, window reveals) and used surfaces. The surfaces are made in the
scripts too: `prop_bake.py` describes each material as a procedural node graph (paint, galvanised steel, concrete,
timber, granite, clay tiles… with dirt, rain runs, rust, moss, worn edges driven by baked occlusion and edge masks)
and bakes them with Cycles into one atlas per model (base colour, occlusion / roughness / metalness, normal, glow),
so every prop is one material = one draw call. What is written on them (price tags, timetable, the shrine's name
board, number plates, warning signs) is painted by `paint.py` / `paint_autobahn.py` with PIL and the system's Noto
Sans / Serif CJK fonts (invented names and numbers, no brands). No third-party geometry, textures or photos.
The roadside's modules (2026-11-11; `frontend/tools/blender/roadside/<id>.py` → `node tools/blender-models.cjs roadside`
→ `frontend/public/models/roadside/*.glb`, laid along the road by `render/roadside.ts`): guardrail span (W-beam, splice,
post), its end terminal, delineator, gutter grating, rockfall fence bay. Own geometry, no textures; dimensions from the
published standard sections (used for measuring only).
The AUTOBAHN course (2026-11-06) adds a sign gantry, an emergency phone, a village house, a farmhouse and a church.
Its sign atlas `textures/autobahn_signs.webp` is painted procedurally by `tools/blender/props/paint_autobahn.py` (invented
place names, no real road signs copied). Its noise-wall, anti-glare and fence textures are generated in code
(`render/autobahnTextures.ts`). Course art `img/courses/autobahn.webp`: generated (see "Generated by Claude" below; an in-game screenshot until 2026-11-11).

### Vegetation and rocks (own, Blender; 2026-11-11)
Trees, bushes, undergrowth and rocks are our own too: Python scripts in `frontend/tools/blender/nature/` grow each
plant from a recipe (`nature_kit.py`), model its twigs needle by needle and leaf by leaf (`twigs.py`), make its bark
from noise (`barks.py`) and bake everything with Cycles: the twigs into sprites (colour, normal, a thickness mask in
the normal map's alpha), a whole bough wearing those sprites into bough sprites, and the finished tree from eight
sides into an impostor atlas (colour + normal). `node tools/blender-models.cjs nature [ids]` builds
`frontend/public/models/nature/<id>.glb` (every level of detail a node, the textures as WebP, meshopt) and
`<id>.lite.glb` for the medium quality (no lod0, textures at half size). No third-party geometry, textures or scans;
the species' proportions are from botanical descriptions and photographs used for looking only.

| id | what | on |
|---|---|---|
| `sugi` | Japanese cedar (杉) | the three passes |
| `hinoki` | hinoki cypress (檜) | the three passes |
| `buna` | beech (ブナ; stands for the European beech on the autobahn) | all courses |
| `akamatsu` | Japanese red pine (赤松) | the three passes |
| `fichte` | Norway spruce | autobahn |
| `birke` | silver birch | autobahn |
| `yabu` | an evergreen thicket shrub | all courses |
| `sasa` | bamboo grass (笹) | the three passes (thickets and undergrowth) |
| `shida` | fern | the three passes |
| `kusa` | grass tufts | all courses |
| `susuki` | pampas grass / tall weeds | all courses |
| `iwa` | four boulders (`iwa.py`: the shape, its three levels and its octahedral colour / normal map all come from one function; no bake) | the three passes |

The old procedural cedar (`treeGeometry`, `makeFoliageTexture`) and the bush / rock lumps (with the ambientCG
`rock_albedo` / `rock_normal` above) remain for the low quality only.

The Sketchfab models used before (KloWorks, Glowbox 3D, guru2fifa, ditovirnantio, Sahir Virmani, Jamie McFarlane,
Mikail Karaca; CC BY 4.0) and their import tool were removed.

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

### Films of a run for the course select (own footage, 2026-11-12)
`frontend/public/video/courses/<course id>.mp4` (+ `.jpg` still, `.json` track of the car's progress): the game
itself, recorded frame by frame on the GPU with `tools/course-clip.cjs` (the AI driver in the hayate, chase view,
no HUD; 30 pictures a second of game time) and encoded with `tools/course-clip-encode.sh` (1280×720, H.264 CRF 34,
no sound, 10–20 MB each). Nothing third-party in them. oboro-downhill night, kirifuri-lakeside dawn, tenrou-skyline
night, autobahn dawn. To be made again after a change of a course's design or of the look.

### Generated by Claude through the owner's browser (ChatGPT for images, Gemini for music / video)
The owner's instruction of 2026-11-11: generate assets freely, images with ChatGPT, both services opened in the
browser. Prompts follow `docs/ASSET_REQUESTS.md`'s common style; an existing portrait is attached as the style reference.

| File (`frontend/public/`) | Source | Processing | Used in |
|---|---|---|---|
| `audio/bgm_race_autobahn.mp3` | Gemini (3.8 Flash, 音楽を作成, instrumental), 2026-11-11: "Instrumental hard trance / uptempo hardcore techno, 175 BPM, minor key …" | MP4 (AAC 44.1 kHz) → gain −2.3 dB to −15.4 LUFS, MP3 160 kbps 48 kHz; 150 s, measured 168 bpm; loop 59.05–133.31 s (52 bars, `tools/music-loop.cjs`) | アウトバーン time attack / online, night (tenrou's track until then). **Not heard by anyone yet when it went in**: the owner listens |
| `img/courses/autobahn.webp` | ChatGPT, 2026-11-11 (style reference: `courses/tenrou`) | 1536×1024 PNG → WebP q84 | アウトバーン course card, loading screen |
| `img/rivals/autobahn-{rookie,ace,legend}.webp` | ChatGPT, 2026-11-11 (style reference: `kirifuri-ace`) | 1024×1536 PNG with alpha → 768×1152 WebP (q85, alpha q90, alpha stretched 254 → 255) | アウトバーン rival cards (早瀬 ユリア, 神崎 ルカ, ファルケ), battle HUD |

### Train models (joke entries; own, Blender)
Every train is our own model since 2026-11-04 (the Sketchfab trains — E231 by own.guest, 銀座線1000 by
ditovirnantio, N700 by Layo, 117 and 京成3300 — and their import tool were removed). Built from numbers by Python
scripts in Blender 5.2 LTS (headless): one assembly script per train (`frontend/tools/blender/<id>.py`) with its part
modules (`tools/blender/parts/<id>_*.py`: body, bogies, roof gear, underfloor, couplers), shared helpers
(`train_kit.py`, the Keikyu's part modules) and a texture painter (`<id>_textures.py` → `tools/blender/textures/<id>/`:
numpy / PIL, Noto Sans CJK for the LED displays and car numbers, no photo pixels). `node tools/blender-models.cjs
trains [ids]` builds and optimises `frontend/public/models/trains/<id>.glb` and each line variant
(`--variant <name>` → `<id>-<name>.glb`: the same train painted and signed for another line). Dimensions and layout
from public figures (Japanese Wikipedia) and photos, used for measuring only; no drawings. Company marks and service
logos (JR mark, KEIKYU logotype, the Hayabusa and H5 logos) are drawn by our scripts as shapes, never cut from photos
(owner's choice, 2026-11-04; to be removed if a rights holder objects). The displays show the line's name, not a station.

| Train | Lines (model files) |
|---|---|
| E231系 (`e231`) | 武蔵野線 (`e231.glb`), 中央・総武緩行線 (`e231-sobu.glb`), 常磐線快速 (`e231-joban.glb`), 地下鉄東西線直通 800番台 (`e231-tozai.glb`), 上野東京ライン 近郊型1000番台 (`e231-kinkou.glb`) |
| E235系 (`e235`) | 山手線 (`e235.glb`), 横須賀・総武快速線 E235系1000番台 (`e235-sobu.glb`), 総武線各駅停車 (`e235-chuosobu.glb`) |
| 京急新1000形 (`keikyu1000`) | 京急本線 (`keikyu1000.glb`) |
| 東武30000系 (`tobu30000`) | 東上線 (`tobu30000.glb`), 伊勢崎線 1996–2011 (`tobu30000-isesaki.glb`: 3-colour LED of that era) |
| E5系 はやぶさ (`e5`) | 東北新幹線 (`e5.glb`: 26.5 m end cars, `TrainInfo.consist`), 北海道新幹線 H5系 (`e5-h5.glb`) |
| L0系 超電導リニア (`l0`) | JR東海 (`l0.glb`: 28 m end cars and a 24.3 m middle car on shared bogies, `TrainInfo.consist`; fitted to Commons photos listed in `tools/blender/fitdata/l0/ref/list.json`) |

Train performance figures (vehicle/trains.ts) are from Japanese Wikipedia; masses marked as estimates in the game
where no per-car figure is published.

### Train sounds (VVVF patterns; the running noise is ours)
No recorded audio is shipped for the trains. The running noise (wheels, rail joints, wind, the motors' hum, flange
squeal, brakes; `frontend/src/game/audio/running.ts`) is synthesised from noise and filters, its levels fitted to
measurements of two Wikimedia Commons recordings the game used to loop (223-2000 coasting by 321keiHIKARI, CC BY-SA
3.0; 700 series on board by spaceaero2, CC BY 3.0). Those files and the earlier motor recordings (117, 京成3300) were
deleted; only band levels measured from them are kept (`RECORDED` in `frontend/tools/train-run-wav.ts`).

Motor, VVVF trains (all of them): the in-train sound calculated by a port of **VVVF Simulator**
(VvvfGeeks, https://github.com/VvvfGeeks/VVVF-Simulator; terms: free for non-commercial use only, link to the
project; the owner approved the port on 2026-11-03): the inverter's PWM, the induction motor's torque ripple and the
simulator's in-train impulse response (`Generation/Audio/TrainSound/Filter.wav` → `frontend/public/audio/vvvf-filter.wav`,
unchanged). Code: `frontend/src/game/audio/vvvf/` (sim.ts, data.ts, math.ts are the port; checked sample by sample
against the simulator's own C# files, `frontend/tools/vvvf-ref/`). Control patterns in the simulator's YAML format,
`frontend/tools/vvvf/` → JSON in `audio/vvvf/patterns/`. CHM patterns also need the simulator's switching-angle
tables (`Vvvf/SwitchAngle/*.bin`, solved by the simulator's authors; copied unchanged to
`frontend/public/audio/vvvf-tables/`, the ones the patterns list: L2Chm3Alt1 … L2Chm15Default, 365 KB):

| Train | Pattern | Source |
|---|---|---|
| E231 武蔵野線 (renewed Mitsubishi 2-level IGBT) | `JRE_E233_1000_MITSUBISHI` | VvvfGeeks / YAML-Files (https://github.com/VvvfGeeks/YAML-Files, fans' recreations, "not exactly the same as the original"; no licence file, used with credit and link, non-commercial) |
| E231 総武線各駅停車, 常磐線, 東西線直通 (3-level IGBT) | `JRE_E231_MITSUBISHI` | VvvfGeeks / YAML-Files |
| E231 上野東京ライン (近郊型, Hitachi 2-level IGBT) | `JRE_E231_HITACHI` | VvvfGeeks / YAML-Files |
| 京急新1000 | `N1000_SIEMENS_GTO` (the "ドレミファインバータ": asynchronous carrier in steps 175…400 Hz, then CHM 15 … 3, sync) | VvvfGeeks / YAML-Files |
| E235 | `E235_ESTIMATE` (ours) | an estimate in the simulator's format from public facts (full-SiC 2-level, asynchronous ~1200 Hz then 27 pulses; ja.wikipedia, VVVF名鑑) |
| 東武30000 | `TOBU30000_ESTIMATE` (ours) | an estimate from public facts (Hitachi 3-level IGBT) |
| E5 | `N700_ESTIMATE` (ours) | an estimate from public facts (3-level IGBT, ~1.5 kHz switching, ~25 s asynchronous after a start: Nagoya Univ. OCW lecture, Wikipedia) |

The other YAML files in `frontend/tools/vvvf/` (JRE_E231 kept as a port test reference, JRW_207, JRW_223, Meitetsu
100) are VvvfGeeks / YAML-Files recreations used only by the tests.

Credits also in the settings screen.

### The rivals' voice: a speech model (2026-11-11, owner's request)
Not in the repository and not in the build: fetched once per server into the `tts` volume
(`docker compose --profile tts run --rm tts-fetch`, `docker/tts/fetch.sh`) and served at `/tts/supertonic-3/`; a
player's browser downloads it only after they said yes.

| What | Source | Licence | Notes |
|---|---|---|---|
| **Supertonic 3** text-to-speech model: `onnx/{duration_predictor,text_encoder,vector_estimator,vocoder}.onnx` (398 MB), `onnx/tts.json`, `onnx/unicode_indexer.json`, `voice_styles/{F1…F5,M1…M5}.json` | Supertone Inc., https://huggingface.co/Supertone/supertonic-3 at revision `3cadd1ee6394adea1bd021217a0e650ede09a323` (SHA-256 of every file in `docker/tts/fetch.sh`) | **OpenRAIL-M** (the model; its `LICENSE` is served next to it and linked from the game: the use restrictions go to whoever receives the model) | Files unchanged. Ten preset voices; which rival speaks with which: `RivalInfo.voice` in `track/courses.ts` |
| The steps that run it (`game/audio/speech/speech.worker.ts`, `text.ts`) | written after the publisher's browser example (`web/helper.js`, repository `supertone-oss-archive/supertonic`) | MIT (the sample code) | not a copy: the same normalisation, tags and order of the four graphs |
| `onnxruntime-web` 1.31.1 (the runtime, with its WebAssembly part in the build) | Microsoft, npm | MIT | |

### Cockroach model (joke entry; own, Blender)
Our own model since 2026-11-04 (`frontend/tools/blender/creatures/roach.py`: body, legs and antennae from numbers,
skinned, with a scuttle cycle; the texture painted by the script) built by `node tools/blender-models.cjs creatures`
into `frontend/public/models/roach/roach.glb`; scaled and tinted at runtime (`render/RoachModel.ts`). The Sketchfab
model used before (CK / xcellf, CC BY 4.0) was removed.

### Motorcycle models (own, Blender; 2026-11-10)
Honda NSR250R (MC21), Kawasaki Ninja H2 and Suzuki GSX1300R 隼 (first generation), each with its rider:
`frontend/tools/blender/bikes/<id>.py` + shared `bike_parts.py` / `bike_logos.py` / `bike_textures.py` (lamp lenses and
disc rings drawn by the script, no photo pixels) → `node tools/blender-models.cjs bikes` →
`frontend/public/models/bikes/<id>.glb` (contract in `render/BikeModel.ts`). Fitted to Wikimedia Commons photos, used
for measuring only; the photos' credits are in `tools/blender/bikes/fitdata/<id>/photos.json`, the fit tools in
`fitdata/tools/`. The makers' logos and the Hayabusa kanji are our own block shapes (owner's choice on logos).

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
