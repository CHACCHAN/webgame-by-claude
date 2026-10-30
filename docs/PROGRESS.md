# Progress log

Newest first. "Verified" means actually executed in this environment; anything else is marked as unverified.

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

## Known issues / next
- Real-GPU performance pass (frame time budget, shadow map cost, draw calls) — still unmeasured. Known
  candidate: lamp posts are individual meshes (~650 draw calls on 朧峠 before culling) and could be instanced.
- Owner assets requested for courses 2/3 (docs/ASSET_REQUESTS.md): six rival portraits, two course key arts,
  two race BGMs, optional defeat jingle. Fallbacks: silhouettes, 