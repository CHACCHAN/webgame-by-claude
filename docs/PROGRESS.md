# Progress log

Newest first. "Verified" means actually executed in this environment; anything else is marked as unverified.

## Session 4 (2026-11-02) — real-GPU performance pass on the owner's PC

Worked directly on the owner's PC this time, with the owner's approval (`ubuntu-dev`: i7-6950X, Radeon RX 5700 XT,
Ubuntu; the public Docker stack + tunnel run on the same machine and were left untouched). Headless Google Chrome 155
renders on the real GPU through ANGLE/Vulkan (RADV). New `tools/perf-gpu.cjs` drives the built game and records per
frame: main-thread time of the animation-frame callbacks, `Game.update`, draw calls / triangles and the GPU time
(EXT_disjoint_timer_query_webgl2) split into shadow maps / main pass / post-processing; plus a scene census, a draw
tally per scene group and feature A/B on frozen frames. Setup: 1920×1080 at DPR 1, uncapped (no vsync), rival race
on the autopilot (R34 vs the course's ace). Caution found on the way: `vite preview` inherits the dev proxy, so on
this PC `/api` would reach the live server on :8080 (players, runs); serve with `API_PROXY=http://127.0.0.1:9`.

### Found & fixed
- **A refractive lens rendered the whole scene twice.** The Impreza GLB (`raijin`) keeps KHR_materials_transmission
  on its turn-signal lenses (their material name matches no game material, so it was cloned as is). While one is in
  view, three.js draws every opaque object a second time into a refraction buffer: ~2× draw calls and main-pass GPU
  time. The Impreza is the ace rival on 朧峠 and 霧降湖 and a player car. (The R34 and RX-7 GLBs carry transmission on
  lamp/glass materials too, but those are replaced by game materials.) `CarModel.withoutTransmission` now turns
  leftover transmissive materials into plain see-through ones; the lens looks the same in the garage (screenshot).
- **Curve mirrors stood in rows.** The placement tested every 1 m sample for a local curvature peak with ≥, which
  every sample of a constant-radius arc passes: a mirror every metre along each bend tighter than 30 m (203 / 98 /
  176 mirrors, 3 meshes each → 609 draw calls on 朧峠), seen as an orange fence on the inside of the hairpins. Now one
  mirror per bend at its apex (`curveMirrorSpots`, unit test), instanced in 2 draw calls: 4 / 2 / 4 mirrors.
  Before/after screenshots at the tightest hairpin of each course and a close-up of one mirror.
- The old note "lamp posts are individual meshes (~650 draw calls)" was stale: lamps are instanced; those draw calls
  were the mirrors.

### Measurements (paired runs: pre-fix `3fbaa93` vs fixed build, alternating; GPU clock sampled)
| run | fps | main thread ms p50 | GPU ms p50 / p95 | draw calls p50 / max | frame p99 ms |
|---|---|---|---|---|---|
| 朧峠 full race, high/night | 128 → 260 | 5.1 → 3.2 | 5.2/16.9 → 3.0/5.7 | 312/2043 → 332/509 | 31.3 → 8.0 |
| 霧降湖 full race, high/night | 144 → 255 | 5.7 → 3.0 | 6.2/9.9 → 3.2/6.2 | 565/1225 → 351/411 | 31.5 → 9.9 |
| 天狼 full race, high/night | 129 → 256 | 7.1 → 3.2 | 6.4/12.0 → 3.1/6.0 | 1069/1970 → 382/551 | 14.2 → 8.8 |
| 朧峠 first 30 s, low/night | 103 → 369 | 9.4 → 2.1 | 4.3/4.9 → 1.2/2.0 | 1729/1889 → 292/349 | 15.6 → 6.0 |
| 〃 medium/night | 122 → 287 | 7.9 → 2.7 | 7.5/12.0 → 2.7/5.8 | 1811/1996 → 376/454 | 14.2 → 8.3 |
| 〃 high/night | 111 → 245 | 8.7 → 3.2 | 8.3/13.2 → 3.0/6.9 | 1879/2045 → 437/509 | 14.3 → 8.7 |
| 〃 ultra/night | 94 → 286 | 9.3 → 3.1 | 9.1/18.2 → 3.1/4.4 | 1907/2049 → 434/512 | 32.3 → 6.1 |

After the fix rain and dawn cost the same as night (GPU p50 within 0.3 ms at every quality level). Shadow-map passes cost ~0.3 ms and
post-processing ~0.6 ms of GPU time; `Game.update` 0.1–0.2 ms. Course load ~3–5 s (local preview).
Remaining per-feature GPU cost (A/B medians on frozen frames, high/night, measured before the fix, ±2 ms noise per
point): headlight shadows 0.7–2.3 ms, trees 1.6–2.4 ms, sun shadow 0.3–1.5 ms, rocks/bushes 0.7–0.9 ms (all instances
drawn every frame, no culling), street-lamp point lights 0.4–0.7 ms.
- **GPU clock caveat**: amdgpu moves the core clock between 800 and 2100 MHz under this load and frame costs change
  ~2× with it. That first looked like a slowdown building up over race restarts and like rain/dawn being heavier;
  checked and ruled out (scene objects, lights, physics bodies, programs, particles and rAF loops constant over
  restarts; fresh-page night/rain/dawn identical at the same clock). Hence the paired runs and the clock column.
- Verified: vitest 26/26; builds; no page errors in any measured run; screenshots above.
  Not verified: frame pacing with vsync in a windowed browser (headless only), other GPUs / Windows (ANGLE D3D11),
  the rare single-frame hitches (max 12–75 ms, a few per run in both builds) — not investigated yet. E2E not re-run.

## Session 3 (2026-11-01) — owner playtest on a real GPU (60 fps, Cloudflare tunnel)

### Second playtest report (lamps, flicker, pop-ups, tail lamps) + exhaust
- **Street lamps faced away from the road**: the arm/head are modelled along local −X and the yaw formula turned
  −X onto *minus* the direction to the road (θ = π − atan2(−dz, −dx)); now θ = atan2(dz, −dx) (`lampArmYaw`,
  unit-tested for every direction). The light sources and baked light pools moved with the heads, so the pools
  now lie on the road instead of beside it.
- **Whole-screen flicker near lights** (not reproducible without a GPU; causes found by measurement):
  the pooled real-time lamp lights hung at the lamp head — with the heads turned outward that was right against
  cuttings, and in the rock shed 0.15 m under the concrete ceiling. With the lights' 1/d^1.7 falloff a surface
  that close gets ~25× (shed: ~4000 units) the brightness of one 1 m away: far over the bloom threshold, and
  the pool hands lights over between lamps every few metres, so the hot spots faded in and out under bloom.
  Lights now hang 0.9 m below the fixture and over the road. The light pool itself was traced over 3,581
  frames: hand-overs only, no oscillation.
  Measured per lamp (light → nearest terrain within 3 m, rock-shed lamps separately): before, Kirifuri had 4
  lights within 1.5 m of the slope (closest *inside* it), Tenrou 1 inside, Oboro closest 3.2 m, plus 32 shed
  lights 0.15 m under the ceiling; after, ≥ 6.2 m from terrain on all courses and shed lights 1.05 m under the
  ceiling. Needs confirmation by the owner on a real GPU.
- **Pop-up headlamps lit while closed (RX-7)**: the model's "headlight" parts were the bumper lamps, the
  pop-ups are modelled shut. Cars with `popUpLamps` in their spec now get runtime pods (raycast onto the bonnet,
  hinged at the lid's rear edge, paint-coloured shell, bezel, lens) that open in 0.6 s when the lights come on at
  night and fold away at dawn; main beam and spot light only once they are up, the bumper lamps become dim
  parking lamps. Procedural fallback bodies keep their own fixed pods. AE86: to set when its model arrives.
- **Tail lamps not lit at night**: tail lamps were a fixed 1.6 unless braking, and on the RX-7 the red lamp
  emitters sat under a smoked cover that the import had mapped to the window glass. Now: position-lamp level
  3.4 whenever the headlights are on (0.9 by day), brake 9; lamp lenses of imported models glow through their
  own texture (emissive map); RX-7 re-imported with emitter + cover as tail lamps.
- **Exhaust** (new): `fx/Exhaust.ts` — puffs from the tailpipe anchor (idle trickle, more under load, thinned at
  speed), backfire flames (additive, blooming) when the throttle is snapped shut at high revs (turbo cars more
  often) with a crack/pop sound when the camera is close. Player, rival and attract car.
- Robustness: an unknown time-of-day value (e.g. corrupted saved settings) fell through to NaN sky/fog values
  and a black screen for the rest of the session; it now falls back to night.
- Scenery models proposed to the owner (Sketchfab, CC BY): see docs/ASSETS.md.
  Further bug found while checking: none of the imported car GLBs carried their anchor empties (the optimiser
  prunes empty nodes), so the exhaust came out from under the middle of the car and imported cars had no
  headlight beam cones; anchors are now derived from the geometry at load (lamp meshes, muffler mesh or the rear
  corner). Also the Supra's dashboard trim shared the tail-lamp material and would have glowed red (pattern fixed,
  re-imported); every car's lamp materials checked to sit only at the front/rear.
  Verified (browser, medium quality, night): RX-7 pods up with lit lenses at night, folded and dark at dawn
  (state + screenshot); lamp arms over the road; tail lamps lit without braking on RX-7 (was black), S15 (lens
  gain 2.5), Impreza, AE86 (procedural), Supra, R34; exhaust plume and a backfire flame behind the car (60 fps
  simulated through the real emitter, then frozen for the shot); no page errors. vitest 25/25.
  E2E on the rebuilt Docker stack: 9/9 passed (22.9 min), including the 3-player online race.
  Not verified: the flicker fix and the backfire/pop sound on real hardware; backfire timing in real driving.

### Reported & fixed
- **Mound across the road (drive-through)** on 天狼's last hairpin: the coarse far terrain mesh (24 m grid, no
  collider) was only lowered by a fixed 30 m under the near grid, but roads cut deeper than that into the ridge
  and caldera walls — it rose up to 16 m (天狼), 44 m (朧峠) and 227 m (霧降湖) above road/near terrain in places.
  Inside the near area it now sits 8 m below the *lowest* near-grid height within one far cell. Also fixed: on
  banked hairpins the near terrain covered the inner road edge by up to 0.32 m (the road bed now accounts for the
  bank), and other-leg grid points are kept out of every road corridor. Regression test for all courses:
  near terrain below the asphalt at 5 points across the road every 2 m, far mesh ≥ 1 m below both.
  Screenshot at the reported spot: road clear.
- Rocks looked like floating discs on steep cuttings: they are now tilted to the slope normal, less flat and half
  buried; bushes sink with the slope.
- **Screen flicker** (not reproducible without a GPU; causes removed): camera passing through the intruding far
  mesh (fixed above), z-fighting where near and far terrain overlap at the near grid border (polygon offset on the
  far mesh), tree chunks flapping between LOD meshes at the switch distance (60 m hysteresis), street-lamp lights
  jumping between lamps when the nearest set changed (lights now keep their lamp and fade out/in when they move).
  Needs confirmation by the owner on a real GPU.
- **Improvement**: controls guide (keyboard, or gamepad labels when a pad is connected) during the countdown and
  the first 8 s of every race, bottom-left; settings toggle「操作ガイド（スタート時）」.

### Car-to-car contact (owner request: 「車同士がぶつけて競争する」)
- Player vs AI rival: both were already Rapier bodies in the same world (chassis colliders in group CAR), now
  covered by a unit test (a car running into a parked one shoves it, bodies never interpenetrate).
- Online: other players' cars become `ProxyCar` stand-ins in each client's physics world — dynamic, real mass,
  no gravity, group PROXY (touches only real cars, not the ground, walls or other proxies), steered toward the
  network pose extrapolated ≤ 0.25 s by velocity blending (0.15 s) + spring, so a hit shoves them and they
  settle back onto their line. Teleports (> 8 m) and the local player's respawn ghost them for 1.5 s until 5 m
  clear. The local car stays authoritative on its own screen (each client simulates its own hits).
  Unit test: an S15 rams a Supra stand-in → pushed, slows the rammer, returns within 0.3 m, no overlap.
- Feedback: contact pairs are read every physics step (`Game.detectCarContact`, real contacts only); a thud scaled
  by the impulse (≤ 4/s), a camera shake and a looping metal scrape while the cars stay together. Bug found in the
  browser check: the feedback ran inside the audio block, so without an audio context there was no shake and the
  contact flags never reset — moved out.
- AI: the rubber-banded chaser rear-ended the leader at corner entry (headless duel: up to 15 m/s Δv, 9–16 s of
  contact per race, leader lost 13 s). It now caps its speed behind a car in its lane (closes to a car length plus
  reaction distance at 4 m/s², then pulls out to pass); ace/legend lean towards the side a close chaser attacks
  (door-to-door contact). Duel after the fix: 1–4 light hits (≤ 1.6 m/s) per race, both cars finish, the faster
  car still gets past. Second bug found by the duel: a finished rival held the brake at a standstill, which
  engages reverse — it drove back up the course into the field (and was respawned every 3 s as "stuck"). It now
  pulls over to its side and parks (handbrake + a foot brake below the reverse threshold), and the player's
  post-finish autopilot steers round it. Browser check (timescale 8): rival finished, moved to the road edge
  (lateral 3.65 m), speed never negative, parked at 0.003 m/s 11 m before the course end, no respawn.
- Verified: vitest 24/24 (incl. contact, stand-in, no-rear-end tests); `tools/sim-duel.ts` on all three courses
  (legend vs legend, rookie vs legend, ace vs ace, legend vs legend in other cars: all finish, 0 respawns);
  browser (low quality): bump into the rival at +8 m/s → rival shoved from 0.5 to 18 m/s, shake 0.5, no errors.
  E2E (Docker stack rebuilt with this code): 9/9 passed in 24.5 min, including the 3-player online race, which now
  also checks that every client holds two solid stand-ins riding on the road.
- Not verified: how the thud/scrape sound by ear; online contact between two real players over the internet (the
  E2E run covers three clients with solid stand-ins on one machine; the shove itself is covered by the unit test).

### Real cars (owner request, private use) — in progress
- Six cars from Sketchfab (all CC BY 4.0, attribution in ASSETS.md). Roster is now six: the three existing ids keep
  their physics, records, medals and CPU ghosts and take the closest real car (hayate → AE86, raijin → Impreza
  WRX STI, shiden → RX-7 FD); three new ids `supra`, `r34`, `s15` with game-tuned specs. Headless sim: all six
  finish all three courses at legend level with 0 respawns (legend laps — Oboro: AE86 106.9 s, S15 100.0 s,
  RX-7 96.0 s, Supra 96.7 s, Impreza 93.3 s, R34 93.5 s); medals for the new cars from the per-course ratios of
  the existing ones. Backend accepts the new ids. Title footer no longer claims fictional cars.
- Model files arrived as zips (5 of 6). Converter + import tool written (see ASSETS.md). **In game: RX-7 (shiden),
  S15, Impreza (raijin)** — checked in the garage and while driving (orientation, wheels in the arches and on the
  ground, wheel spin/steer, taillights), paint recolour verified (red RX-7), every car carries its paint, glass,
  headlamp and taillamp materials; 37–53 k triangles per car. Bugs found & fixed in the converter: the optimiser's
  palette step renamed the materials (paint colour ignored), a material shared by window and headlamp glass took
  only one role, three.js turns spaces in node names into underscores (patterns), stray unreferenced vertices broke
  the RX-7 bounds.
- R34 and Supra: the first files (signs of extraction from a commercial game) were replaced by models I proposed
  from a Sketchfab API search and the owner delivered: **R34 by Lexyc16 and Supra mk4 by Black Snow, both CC BY 4.0,
  now in game.** R34: 50 k tris, wheelbase/length/height 2.665/4.61/1.34 m straight from the spec scale. Supra: a
  modded show car — purple self-lit rims and exhaust tips, red self-lit front strips and red front indicators
  restyled (new importer options `restyle`, error-bounded `reduce`); 226 k → 82 k tris (tyre tread was 44 k: the
  optimiser's per-part error bound skips small dense parts; a first unbounded decimation filled the tyre holes and
  hid the rims — caught in the garage shot, replaced by an error-bounded one). Exhaust tip shared the rim material
  and was taken for a wheel (wheel radius 0.57 m) — pattern fixed. Checked in the browser: garage (default and
  recoloured paint), driving, all four wheel pivots, paint/glass/headlamp/taillamp materials, no console errors.
- AE86: the linked model is 71.7 MB / 706 k tris (too large to attach); two light CC BY replacements proposed
  (ASSETS.md). Until one arrives `hayate` keeps the procedural body.

## Session 2 (2026-10-30, continued)

### Done & verified
- **3 courses** (owner request): 朧峠 (bay, 3.11 km), 霧降湖 (caldera lake, 2.60 km), 天狼スカイライン (ridge,
  2.37 km). Each course = turtle-style design + `Landform` (base terrain, water, towns, moon direction, cloud
  level, features such as the ferris wheel, onsen town, wind turbines) + its own rivals, medals, music and art
  (`track/courses.ts`, `track/landforms.ts`). Course select screen with route maps, length/drop/best; course
  switching rebuilds the world behind a loading screen; per-course local bests, leaderboards and CPU ghosts.
- Headless sim: all 3 cars × 3 AI levels finish courses 2 and 3 with 0 respawns; medals derived from those laps.
  Legend cars on the new courses run a tuned engine (power 1.18) so the legend stays distinct.
- Backend: 3 tracks in `config/game.php`, CPU ghosts regenerated for all courses (oboro 7, kirifuri 6, tenrou 6
  seeded runs, checked via the API after `docker compose up --build`); 9 backend tests pass in Docker.
- Owner assets integrated (menu/race BGM with loop points, finish jingle, boot loop video, 朧峠 rival portraits,
  key art, `og:image`); ledger in ASSETS.md.
- Photo textures (ambientCG, CC0) for asphalt (albedo + full-res normal/roughness at real scale), ground,
  rock and concrete, with the procedural textures kept as fallback. Screenshots checked dry and wet.
- **Corner pace notes** (owner idea): a few seconds before every tight bend a warning sign (hairpin / sharp /
  bend, left/right, distance countdown) appears top-centre with 1–3 warning beeps; medium bends are only called
  when arriving too fast. Toggle in settings (コーナー予告). Verified in an autodriven race screenshot
  (「右ヘアピン 90m」) and unit tests (`findCorners`).
- Bugs found & fixed: every sample of a constant-radius bend counted as a corner peak, stacking dozens of
  chevrons/warning/speed signs at each hairpin (now one sign group per bend, shared detector); far-terrain edge
  cliffs; the sky below the horizon showed through past the terrain edge as an orange slab on the ridge course
  (sky now fades to fogged ground below the horizon + a fogged ground skirt); lake normal-map tiling.
- GPU resource leaks on course switch / time-of-day change found via `renderer.info.memory` (counts grew on
  every switch): undisposed instanced-mesh buffers, shadow-map render targets, environment-map render targets
  and the temporary meshes used to bake them. After the fix, switching back and forth returns to identical
  counts (e.g. 朧峠 63 geometries / 23 textures every time). Found because the E2E course-switch test hit
  shader link failures late in a long-lived browser.
- Keyboard selection on menus could be overridden by the synthetic mouse events browsers send when a screen
  appears under a resting cursor; hover-to-select now ignores events without movement.
- vitest 15 tests pass; E2E now covers course select and course switching (8 tests).
- Owner assets batch 2: 天狼 rival portraits + key art, race BGMs for 霧降湖/天狼 (loop points from spectral
  matching of "end of chorus" moments), defeat jingle (final phrase of the delivered track). Checked in the browser:
  portraits load (768×1152) on the 天狼 rival screen, the course card shows the art, all three audio files decode.
- 霧降湖 rival portraits ×3 and key art re-sent one by one and integrated (all 9 rivals and 3 course arts now in
  place); checked on the course select, course loading and 霧降湖 rival screens.
- Quality review at the High preset (driving views on all courses, rain, dawn, car close-up). Weakest items were the
  low-poly vegetation and the car bodies. Reworked: trees are now layered cedars (trunk + 7 drooping, ragged tiers,
  procedural alpha-tested branch/needle texture, volume-style normals, darker inner tiers) with a darker far LOD;
  rocks and bushes are smooth noise-displaced lumps (rocks with the scanned texture, sunk into the ground). Found &
  fixed: the canvas foliage texture was mapped upside down (flipY). Before/after screenshots checked.
  Still the main gap: procedural car bodies look boxy in close-ups (needs a dedicated modelling pass or artist GLBs).
- **Online battle (owner request, up to 3 players)**: Laravel rooms API (create with a 4-character code, join, car
  choice, leave with host hand-over, host start with a server-chosen green-light time, finish times, rematch;
  max 3 / min 2 players enforced in a transaction; per-player rate limit) + Laravel Reverb presence channel per
  room (signed by our own auth endpoint with the player token) for room updates and ~12 Hz car-state client
  events. Reverb runs inside the `app` container, credentials generated per container, nginx proxies `/app/`.
  Client: lobby / room / results screens, interpolated remote cars (no contact) with name tags, slot colours,
  live standings in the HUD, polling fallback when the socket is down, online pause = menu only.
  Race clock = max(physics clock, wall clock since the green light) so low frame rates gain nothing.
  Verified: 13 backend tests (4 new: join limits, lifecycle, host hand-over, channel auth signature); WebSocket
  handshake through nginx (101 + connection_established); E2E `online.spec.ts` with three browser contexts:
  create → join by code ×2 → 4th refused (API) → host start → all racing on the shared green light → car
  states flow between all three, live standings list 3 → finish (shortcut near the line after the course
  minimum) → shared results with three times → rematch back to the room; no console errors. Full E2E 9/9.
  Not verifiable here: play over the internet between real machines (needs a publicly reachable deployment).
- Perf follow-up of the vegetation pass: the Low preset had become ~1.84 M triangles (from ~1.2 M); rocks/bushes
  back to 80-triangle meshes and the near-tree distance is now per preset (240/380/560/720 m) → ~1.5 M at Low.
- Fixed: the end of this log had been cut off by a write while the disk was full; the known-issues list is restored.
- Bug found & fixed: on 天狼 the garage camera dipped into the steep bank beside the start and glided in from the
  title camera through the hill (rival select showed the road from underneath). The camera and its glide are now
  kept above ground, and the camera side is chosen by a sight-line test (uphill side kept on all three courses).

## Session 1 (2026-10-30)

### Environment survey
- Tools: Docker 29 + Compose v5 (daemon started manually; Docker Hub 429 → mirror.gcr.io), PHP 8.3, Composer,
  Node 22, Python 3.13 (numpy, PIL), ffmpeg, ImageMagick, Playwright 1.63 + Chromium (SwiftShader WebGL).
- Network: npm, Packagist, PyPI, GitHub raw, mcr.microsoft.com, Ubuntu apt OK. Asset sites blocked (see ASSETS.md).

### Done & verified
- Laravel API (players/runs/leaderboard/ghosts) — 8 feature tests pass (`php artisan test`).
- Docker Compose stack (db/app/web) builds and runs; `/api/health`, player registration, run submission and
  leaderboard verified with curl through nginx → PHP-FPM → PostgreSQL.
- Course + terrain generation; layout checked with top-down/hillshade renders (no overlapping legs).
- Vehicle physics + AI: headless sim — all 3 cars × 3 AI levels finish the course with 0 respawns
  (legend: HAYATE 117.4 s, RAIJIN 98.6 s, SHIDEN 105.0 s).
- Frontend builds (`tsc -b`, `vite build`). Headless browser screenshots verified: title, menu, garage,
  countdown/HUD, driving, environment views (city lights, bridge, vista, hairpins).
- Bugs found & fixed via screenshots: sky shader used reserved GLSL word `flat`; road mesh and roadside
  sweeps had inverted winding (road invisible, black curb lines).

### Done & verified (continued)
- Handling rework after scripted manoeuvre tests (`npm run handling`): fixed speed-proportional rolling
  resistance (cars topped out ~110 km/h), added an arcade drift state machine (handbrake / feint / power entry,
  rear grip release, throttle-modulated angle) and true sliding friction for locked wheels.
  Results: 0–100 km/h HAYATE 7.6 s, RAIJIN 4.0 s, SHIDEN 4.8 s; 100–0 braking 36–37 m; a closed-loop
  "skilled driver" holds an 18–45° drift ~80 % of the time with assist, no spins under abusive input.
- AI grip-drives with strong assist; full-course times (rivals): rookie/HAYATE ~121 s, ace/RAIJIN ~100 s,
  legend/SHIDEN ~95 s. All 9 car×level combinations finish without respawns.
- vitest: 13 tests (track geometry/projection/overlap/terrain carve, ghost codec round-trip, vehicle behaviour,
  full AI lap) — pass.
- Seed data: 7 CPU drivers with real ghosts generated from the simulation (`npm run seed:bots`), loaded by
  Laravel's seeder; verified via the API after `docker compose down -v && up --build`.
- Visual fixes verified by screenshots: baked lamp-light pools (road + terrain lightmaps), brighter moonlit
  night, roadside bushes/rocks, LED lamps at the summit, car trim/headlight/mirror fixes.
- Race timing moved onto the fixed physics step (it previously drifted when the frame rate dropped below
  the physics budget); AI now updates every physics step.
- Replay: cinematic replay of the player's run (and the rival's) from the recorded ghost data.

- Weather/time presets: 深夜（夜景）, 深夜（雨）(wet glossy road, rain streaks, spray, rain ambience, 14 % less
  grip, AI recalibrated), 夜明け（雲海）(sea of clouds with soft terrain fade). Screenshots checked for all three.
- Terrain reworked to tilted-plane interpolation: roads are now cut into real hillsides (uphill +15–30 m,
  valley side −5…−18 m within 30 m) instead of nearly flat surroundings.
- Medals (bronze/silver/gold per car, from simulated AI laps) and per-car personal bests in the garage.
- GLB pipeline: procedural cars → GLTFExporter (headless browser) → glTF-Transform (dedup + meshopt) →
  loaded at runtime with procedural fallback; node/material contract documented in ASSETS.md.
- E2E (Playwright, against the Docker stack): boot/title, menus + settings persistence, ranking from the
  API, full autodriven time attack → results → online submission → appears in ranking, ghost battle vs CPU
  ghost, rival battle + pause, API validation. Found & fixed: garage CTA offscreen at 720p, rival card
  click starting the wrong rival.
- Containerised backend tests (`docker compose --profile test run --rm backend-test`): 9 passed.

## Quality self-assessment (end of session 1)
- Playable end to end: yes (all modes, ranking, ghosts, replay) — verified by E2E and headless sims.
- Driving feel: tuned by measurement only (no human playtest possible here). Drift entry is deliberately
  easy (handbrake / brake+steer / power+steer) with assists; needs real-player feedback.
- Visuals: strongest in night aerials (city + lamp pools), wet night and dawn sea of clouds. Weakest: close-up
  car detail (procedural) and ground clutter (low-poly bushes/rocks).
- Performance: unmeasured on a real GPU. Tree LOD and quality presets exist; ~1.2 M triangles at low.

## Public access (Cloudflare Tunnel)
- `cloudflared` compose service (profile `tunnel`), token-only remotely-managed tunnel, on a dedicated `edge`
  network that reaches nginx but not app/db. nginx restores the visitor IP from `CF-Connecting-IP` so per-IP
  throttles do not become one global bucket; the header is trusted from cloudflared's fixed IP only.
- Verified on a disposable stack with a client at the trusted/untrusted address: 12 visitor IPs → no 429, same IP
  → 429 after 10, spoofed header from another address ignored, Reverb upgrade through nginx → 101.
  Not yet verified end to end against Cloudflare (needs the owner's token and hostname).

## Known issues / next
- Real-GPU performance pass: done in session 4 (RX 5700 XT). Open: rare single-frame hitches; roadside rocks/bushes
  are not culled (one instanced mesh per kind for the whole course).
- The delivered 朧峠 key art's coupe resembles a real 1980s car; replacing it is recommended before a public release.
- Car models could be replaced by artist GLBs following the contract in docs/ASSETS.md.
- Engine sound, corner warning beeps and the music loop points are unverified by ear in this environment.
- Touch controls (mobile) are not implemented (PC is the target).
