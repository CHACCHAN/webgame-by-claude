# Progress log

Newest first. "Verified" means actually executed in this environment; anything else is marked as unverified.

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
- Real-GPU performance pass (frame time budget, shadow map cost, draw calls).
- Optional owner-provided assets (docs/ASSET_REQUESTS.md): race/menu BGM and a key art image.
- Car models could be replaced by artist GLBs following the contract in docs/ASSETS.md.
- Engine sound is synthesised and unverified by ear in this environment.
- Touch controls (mobile) are not implemented (PC is the target).
