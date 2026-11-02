# CLAUDE.md — TOUGE NOCTURNE (朧峠)

Browser 3D downhill touge racing game. Read `docs/HANDOVER.md` first (current state, owner rules, what the
owner is to deliver, how to verify), then `docs/PROGRESS.md`: the running log of what is done, verified and
pending. `docs/PLAN.md` holds the design.

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
  the Node headless sim for driving/physics checks. Browser checks: `node tools/probe.cjs <quality> <script.cjs>`
  (`PW_MODULE=/opt/node-tools/node_modules/playwright`, `vite preview` on :4173). Never `pkill -f` a pattern contained in your own command line.

## Gotchas
- Cars load from `frontend/public/models/cars/*.glb` at runtime. After editing `CarModel.ts`, rebuild and run
  `npm run assets:cars` (with `vite preview` on :4173 and `PW_MODULE=<path to playwright>`), or delete the GLBs
  to fall back to the procedural builder.
- Third-party car models: unpack each glTF zip into a folder, describe it in `frontend/tools/car-import.json`
  (patterns for wheels / calipers / paint / glass / lamps / drop), then with `vite preview` on :4173:
  `node tools/import-cars.cjs preview <srcRoot> <outDir> <ids>` (orientation renders) and
  `node tools/import-cars.cjs import <srcRoot> <ids>` → `public/models/cars/<id>.glb`. Attribution: CarSpec.model + docs/ASSETS.md.
  Patterns match `"<mesh name> <material name>"` (three.js strips `.` from node names, keeps material names). Optional
  `restyle` (recolour / un-glow parts) and `reduce` (error-bounded decimation of dense untextured parts, e.g. tyres).
  Rebuild (`npx vite build`) after an import before checking in `vite preview` — it serves `dist/`.
  The optimiser prunes empty nodes, so imported GLBs have no anchor empties: `CarModel.deriveAnchors` rebuilds lamp
  and exhaust anchors from the geometry. Lamp roles must only cover lamp parts (check: lamp materials only at the
  car's ends). Retractable lamps: `CarSpec.popUpLamps` (runtime pods in `CarVisual`); dark lens textures: `tailLampGain`.
- Courses live in `track/courses.ts` (design + `Landform` from `track/landforms.ts` + rivals, medals, music, art).
  After changing a course design, regenerate the CPU ghosts (`npm run seed:bots`) and re-check medals with the sim.
- Online battle (≤3 players): lobby/start/results via `RoomController`; car states are presence-channel client events
  (`client-state`, ~12 Hz) relayed by Reverb, which runs inside the `app` container (entrypoint, `START_REVERB`), proxied by
  nginx at `/app/`. Reverb key/secret are generated per container; never commit them. Client: `store/online.ts`,
  engine side `game/net/RemoteRacers.ts`. Online race time = max(physics clock, wall clock since the shared green light).
- Public access: Cloudflare Tunnel, started by plain `docker compose up` when `.env` has `COMPOSE_PROFILES=tunnel` and `CLOUDFLARE_TUNNEL_TOKEN` (dashboard route → `http://web:80`); an explicit `--profile dev|test` replaces it.
  nginx restores the visitor IP from `CF-Connecting-IP`, trusting only cloudflared's fixed address `172.30.77.10`: keep `docker-compose.yml` and `docker/web/nginx.conf` in sync.
- Race timing/splits/AI run per physics step (`Game.raceStep`, `driveAI`); keep frame-time logic out of timing.
- Cars are solid (collision groups in `PhysicsWorld.ts`: GROUND, WALL, CAR, PROXY). Online peers become `net/ProxyCar`
  bodies (group PROXY, collide with CAR only) steered toward the extrapolated network pose; after a teleport or the local
  player's respawn they are ghosted (collider off) until clear. `Game.detectCarContact` → thud/shake/scrape. The AI
  never rear-ends (speed cap from `opponent.speed`), defends its line (`AIProfile.defend`), and a finished rival pulls
  over and parks (`AIDriver.pullOver`). Check AI-vs-AI contact with `npx tsx tools/sim-duel.ts`.

## Conventions
- Units: meters, seconds, radians. +Y up, +Z south (towards the bay). Heading 0 = +Z; car local +Z forward, +X left.
- Physics fixed step 120 Hz (`PHYSICS_DT`); visuals interpolate. Vehicle forces are applied as impulses.
- Keep engine modules free of React; UI reads `game.hud` each animation frame (no per-frame React state).
