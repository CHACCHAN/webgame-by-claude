# CLAUDE.md — TOUGE NOCTURNE (朧峠)

Browser 3D downhill touge racing game. Read `docs/PROGRESS.md` first: it is the
running log of what is done, verified and pending. `docs/PLAN.md` holds the design.

## Layout
- `backend/` Laravel 13 JSON API (players, runs, leaderboard, ghosts, online rooms) + Laravel Reverb WebSocket server. Tests: `php artisan test` (sqlite in-memory).
- `frontend/` Vite + React 19 + three.js 0.186 + @react-three/fiber + postprocessing + Rapier (compat).
  - `src/game/` engine code, DOM-free where possible so it runs in Node for headless sims:
    `track/` (course design, Track centerline, terrain, road geometry), `vehicle/` (PhysicsWorld, VehicleSim, specs),
    `ai/` (RacingLine, AIDriver), `race/Ghost.ts` (record/playback/codec), `render/` (scenery, environment, car models),
    `camera/`, `audio/` (WebAudio synth), `fx/`, `Game.ts` (orchestrator, phases).
  - `src/ui/` React screens + HUD; `src/store/` zustand stores; `src/api/client.ts`.
  - `tools/` dev scripts run with `npx tsx` (sim-run, plot-track, plot-terrain, gen-bot-ghosts).
- `e2e/` Playwright tests. `docker/` Dockerfiles + nginx. `docs/` plan, progress, assets ledger.

## Commands
- Stack: `docker compose up --build` → http://localhost:8080
- Dev with HMR: `docker compose --profile dev up` → http://localhost:5173 (proxies /api to web)
- Backend tests: `cd backend && php artisan test` or `docker compose --profile test run --rm backend-test`
- Frontend: `cd frontend && npx tsc -b && npm run build && npx vitest run`
- Headless driving sim: `cd frontend && npx tsx tools/sim-run.ts [cars] [levels]`
- E2E: `docker compose --profile test run --rm e2e` (stack must be up)

## Environment notes (cloud sessions)
- dockerd is not running by default: `nohup dockerd > /tmp/dockerd.log 2>&1 &`.
  Docker Hub rate-limits: `/etc/docker/daemon.json` → `{"registry-mirrors":["https://mirror.gcr.io"]}`.
- TLS is intercepted by a proxy: put its CA into `docker/certs/*.crt` (gitignored) before `docker compose build`
  (`cp /root/.ccr/ca-bundle.crt docker/certs/proxy-ca.crt`).
- npm, packagist, pypi, raw.githubusercontent.com, Ubuntu apt and ambientcg.com (CC0 textures) work;
  dl.polyhaven.org, kenney, sketchfab and jsdelivr are blocked. Most assets are procedural; photo textures
  in `public/textures/` and owner-supplied images/music are listed in docs/ASSETS.md.
- Headless Chromium renders WebGL with SwiftShader (~1–6 fps): use quality `low` for automated UI checks and
  the Node headless sim for driving/physics checks. Never `pkill -f` a pattern contained in your own command line.

## Gotchas
- Cars load from `frontend/public/models/cars/*.glb` at runtime. After editing `CarModel.ts`, rebuild and run
  `npm run assets:cars` (with `vite preview` on :4173 and `PW_MODULE=<path to playwright>`), or delete the GLBs
  to fall back to the procedural builder.
- Courses live in `track/courses.ts` (design + `Landform` from `track/landforms.ts` + rivals, medals, music, art).
  After changing a course design, regenerate the CPU ghosts (`npm run seed:bots`) and re-check medals with the sim.
- Online battle (≤3 players): lobby/start/results via `RoomController`; car states are presence-channel client events
  (`client-state`, ~12 Hz) relayed by Reverb, which runs inside the `app` container (entrypoint, `START_REVERB`), proxied by
  nginx at `/app/`. Reverb key/secret are generated per container; never commit them. Client: `store/online.ts`,
  engine side `game/net/RemoteRacers.ts`. Online race time = max(physics clock, wall clock since the shared green light).
- Race timing/splits/AI run per physics step (`Game.raceStep`, `driveAI`); keep frame-time logic out of timing.

## Conventions
- Units: meters, seconds, radians. +Y up, +Z south (towards the bay). Heading 0 = +Z; car local +Z forward, +X left.
- Physics fixed step 120 Hz (`PHYSICS_DT`); visuals interpolate. Vehicle forces are applied as impulses.
- Keep engine modules free of React; UI reads `game.hud` each animation frame (no per-frame React state).
