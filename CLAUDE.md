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
- Backend tests: `cd backend && php artisan test` or `docker compose --profile test run --rm --build backend-test`
  (the image bakes the code in: without `--build` it tests the last built code)
- Frontend: `cd frontend && npx tsc -b && npm run build && npx vitest run`
- Headless driving sim: `cd frontend && npx tsx tools/sim-run.ts [cars] [levels]`
- Handling numbers (wall hits: bounce / spin / thrown out; drift entries: time held, peak angle): `npx tsx tools/handling-feel.ts [cars]`
- E2E: `docker compose --profile test run --rm e2e` (stack must be up)
- Real-GPU performance (needs a host GPU + Google Chrome): `cd frontend && node tools/perf-gpu.cjs <course|quality|ab|census>`
  (`vite preview` on :4173; compare builds with `URL=before@http://…:4174/,after@http://…:4173/`, see the file header).

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

## Environment notes (owner's PC `ubuntu-dev`, when the owner opens a session there)
- The live stack (compose project `touge-nocturne` + cloudflared) runs on this machine. Deploy finished changes with
  `docker compose up -d --build` without asking (owner's standing permission; nobody else uses the site yet), then
  check that the new build is served. Other compose projects on the host are unrelated: leave them alone.
- `vite preview` inherits the dev proxy (`/api` → localhost:8080 = the live server): always serve with
  `API_PROXY=http://127.0.0.1:9 npx vite preview …` so test runs cannot create players or submit runs.
- No Node on the host: use a user-space Node 24 tarball (nodejs.org) and `npm i playwright-core` outside the repo
  (`PW_MODULE=<that>/node_modules/playwright-core`); Chrome is `/usr/bin/google-chrome` and renders on the RX 5700 XT
  headless (`--use-angle=vulkan --enable-features=Vulkan`, as in `tools/perf-gpu.cjs`).
- The GPU picks its own clock (800–2100 MHz) and frame costs change ~2× with it: compare builds with paired runs.

## Gotchas
- Scenery models (street lights, turbines, mirrors, vending machines, shrine, bus stop, cones): glTF folders →
  `node tools/import-props.cjs <srcRoot> [ids]` (`tools/props-import.json`) → `public/models/props/*.glb`; size,
  facing (+Z = front) and origin are set in `PROPS` (`render/props.ts`), placement in `TrackScenery.ts`. Each model
  falls back to the procedural shape when it fails to load. `PropDef.drop` leaves out a box of a model's triangles
  (the bus stop's utility pole). Credits: `PROPS[].credit` (settings screen) + ASSETS.md.
- Car models with pop-up lamps modelled raised: `popUps` in `car-import.json` (box around the pods, lens pattern,
  folding angle); modelled closed instead: `CarSpec.popUpLamps` (runtime pods). Exhaust guess wrong: `CarSpec.exhaust`.
- Never leave a transmissive (refractive) material in the scene: three.js then renders every opaque object a second
  time per frame. Imported car materials are flattened by `CarModel.withoutTransmission`.
- Cars load from `frontend/public/models/cars/*.glb` at runtime. All six are imported third-party models now:
  do not run `npm run assets:cars` (it exports the procedural bodies of hayate/raijin/shiden over their GLBs).
  Deleting a GLB falls back to the procedural builder.
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
- Race setup order (single player): mode → course → time & weather (`ConditionsScreen`) → car (`GarageScreen`) → AT/MT
  (`TransmissionScreen`) → rival (rival mode) → race; ghost battles pick the ghost between conditions and car. The last
  choices persist in settings (`timeOfDay`, `autoShift`) but are no longer in the settings screen. Online rooms carry the
  host's `time_of_day`; AT/MT stays each player's. The host can start only when every member reported `ready`.
- Trains (joke entries, `vehicle/trains.ts`): the sim is only the leading front bogie; `TrainModel` draws three cars
  along its driven path every frame (`CarVisual.tick` → `rig.train.update`; call `CarVisual.refresh()` after moving
  a root by hand). Performance comes from the real figures via `trainSpec` (torque curve, redline, brake force);
  check with the train tests in `vehicle.test.ts`. Models: unpack each glTF zip into a folder, describe the cuts in
  `frontend/tools/train-import.json` (axis, scale to metres, three [from, to] ranges along the axis at the gangways,
  `frontAtMin` / `flip`), then with `vite preview` on :4173: `node tools/import-trains.cjs <srcRoot> [ids]`.
  Own models (`keikyu1000`; `TrainInfo.model.own`) are Blender Python scripts: `tools/blender/<id>.py` (assembly, CLI
  `--out/--render/--views`) + part modules `tools/blender/parts/` + `train_kit.py` (frame, materials, export) +
  `showcase.py` (trackside check renders) → `BLENDER=<bin> node tools/blender-models.cjs trains <id> [--render]`
  (Blender 5.2 headless → GLB → palette, WebP, meshopt; deterministic). Same contract as imports: nodes car0..car2,
  origin at the bogie midpoint on the ground, front +Z (Blender: game x, −z, y → Blender x, y, z). Cars of unequal
  length (E5): `TrainInfo.consist` (`trainBogiePath`).
  The models' lamps are only painted on: `TrainInfo.lamps` (head/tail lamp positions measured on head-on renders,
  lenses put on the surface by a ray; the side-window band and its luminance limit for the night interior glow).
  Sound (`audio/TrainSound.ts`): VVVF trains run a port of VVVF-Simulator (`audio/vvvf/`: AudioWorklet `vvvf-sim`
  at ~192 kHz → the simulator's impulse response `public/audio/vvvf-filter.wav` → body EQ `VVVF_BODY`), driven by
  `TrainInfo.vvvf` (`vehicle/vvvf.ts`: pattern name, gear teeth, poles, slip; `vvvfDrive`). Patterns are the
  simulator's YAML (`tools/vvvf/*.yaml`; after editing run `npx tsx tools/vvvf-patterns.ts`, the test checks the
  JSONs; CHM patterns list their switching-angle tables in `CustomPwm`: the simulator's `.bin` files in
  `public/audio/vvvf-tables/`, `audio/vvvf/customPwm.ts`; a missing table fails the script and silences that train's
  VVVF). A train's tractive effort builds up over `TRACTION_RISE` after a notch-on (jerk limit, `VehicleSim.traction`;
  the sound's slip follows it), so a start sweeps up from 0 Hz (the Keikyu doremifa, ~1.5 s as on recordings).
  `sim.ts` / `data.ts` / `math.ts` / `customPwm.ts` are a line-by-line port: keep them so (C# semantics: banker's rounding,
  `List.Sort`); `vvvf.test.ts` compares with the C# build's output (`tools/vvvf-ref/README.md` to regenerate). Others
  follow a recording of a start by speed (`motorSound`: clip + [s, km/h] points, `audio/TrainRecordings.ts`); all loop
  `runningSound` by speed. Check a change by rendering, not by ear only: `tools/vvvf-train-wav.ts` (Node, inverter only,
  levels per speed band) and `tools/vvvf-game-wav.ts` (Chrome + vite preview: the game's whole chain, offline). Medals: `TRAIN_MEDALS` in courses.ts (re-run tools/sim-run.ts
  with the train ids after physics or course changes). `CAR_ORDER` = cars only (AI, bots, GLBs), `VEHICLE_ORDER` =
  cars + trains (player-facing lists); the backend's `game.cars` lists both.
- The cockroach (joke entry, `vehicle/roach.ts`, id `roach`, last in `VEHICLE_ORDER`): a car-like sim on one fixed
  ratio (`singleRatio` → no AT/MT) with ~1.3× a sports car's grip, ~410 km/h; drawn by `render/RoachModel.ts` from a
  skinned GLB (`public/models/roach/roach.glb`; legs run with the distance covered, eyes are the headlights; colours
  via `CreatureInfo.liveries`), heard through `audio/BugSound.ts`; medals in `ROACH_MEDALS`. The backend's
  `min_time_ms` per course leaves room for it.
- Particles: any per-particle value raised to a power must have its base clamped (a NaN alpha on a puff drawn next to
  the camera covers the screen, and bloom turns a NaN frame black).
- Race timing/splits/AI run per physics step (`Game.raceStep`, `driveAI`); keep frame-time logic out of timing.
- Tyre grip = course surface (`CourseInfo.surface.grip`) × weather (`WET_GRIP` in rain): `Game.roadGrip` → `VehicleSim.gripScale`
  (before `AIDriver.calibrate`). Headless tools take the course's grip. Changing a grip: re-check medals with the sim
  and regenerate the bots (`npm run seed:bots`; the seeder replaces a bot's old run).
- Player drifts start only on a deliberate input (handbrake, brake tap + big steer, throttle stab, slip > 16°); the
  grip assist keeps flat-out corners from sliding. The AI drives as `gripDriver` and skips both. Check feel with
  `npx tsx tools/handling-feel.ts` (ordinary corners should stay under ~15° of slip).
- Cars are solid (collision groups in `PhysicsWorld.ts`: GROUND, WALL, CAR, PROXY). Online peers become `net/ProxyCar`
  bodies (group PROXY, collide with CAR only) steered toward the extrapolated network pose; after a teleport or the local
  player's respawn they are ghosted (collider off) until clear. `Game.detectCarContact` → thud/shake/scrape. The AI
  never rear-ends (speed cap from `opponent.speed`), defends its line (`AIProfile.defend`), and a finished rival pulls
  over and parks (`AIDriver.pullOver`). Check AI-vs-AI contact with `npx tsx tools/sim-duel.ts`.

## Conventions
- Units: meters, seconds, radians. +Y up, +Z south (towards the bay). Heading 0 = +Z; car local +Z forward, +X left.
- Physics fixed step 120 Hz (`PHYSICS_DT`); visuals interpolate. Vehicle forces are applied as impulses.
- Keep engine modules free of React; UI reads `game.hud` each animation frame (no per-frame React state).
- Phones: `.touch` on the app (`ui/touch.ts`: coarse primary pointer, or the first touch); race buttons in
  `ui/hud/TouchControls.tsx` feed `InputManager.touch`; menu screens get a ◀ 戻る button that sends Escape (every
  screen must keep mapping Esc to its back action); compact styles under `@media (max-height: 500px)`. Check with
  Playwright phone emulation (`viewport 844×390, hasTouch, isMobile`; `e2e/tests/mobile.spec.ts`).
  Fullscreen (`ui/fullscreen.ts`): menu button, F key, pause item, settings row (phones: also the title tap).
