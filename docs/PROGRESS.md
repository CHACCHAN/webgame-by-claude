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

### Known issues / next
- Night visuals: balance still being tuned; terrain readability; lamp light pools on the road.
- Car models are procedural — readable but low-detail. A GLB override path would allow dropping in better models.
- Driving feel not yet tuned with scripted manoeuvre tests; drift assist values are first guesses.
- No e2e Playwright suite yet; no seeded bot ghosts yet.
- Performance on a real GPU unmeasured (cloud VM has no GPU; SwiftShader gives ~1–6 fps).
