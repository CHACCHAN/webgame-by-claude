# CLAUDE.md — TOUGE NOCTURNE (朧峠)

Browser 3D downhill touge racing game. Read `docs/HANDOVER.md` first (current state, owner rules, what the
owner is to deliver, how to verify), then `docs/PROGRESS.md`: the running log of what is done, verified and
pending. `docs/PLAN.md` holds the design.

## Layout
- `backend/` Laravel 13 JSON API (players, runs, leaderboard, ghosts, online rooms) + Laravel Reverb WebSocket server. Tests: `php artisan test` (sqlite in-memory).
- `frontend/` Vite + React 19 + three.js 0.186 (`WebGPURenderer`: WebGPU, or its WebGL 2 backend; node materials / TSL) + Rapier (compat).
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
- Real-GPU performance (needs a host GPU + Google Chrome; `vite preview` on :4173): `cd frontend && node tools/perf-frame.cjs`
  (frame cost, any backend; compare builds with `URL=before@http://…:4174/,after@http://…:4173/`, settings with
  `VARIANTS='{"native":{},"quality":{"upscale":true}}'`, see the file header).
  GPU time per render pass (WebGPU only; says which pass a difference comes from, and holds while the CPU is busy):
  `node tools/perf-pass.cjs`. `tools/perf-gpu.cjs` only works on builds with the old WebGLRenderer.
- The look, on fixed viewpoints (every course × time of day, contact sheets): `node tools/shots.cjs <label>` → `~/.local/opt/quality/<label>`.
  `SET='<settings JSON>'` changes the stored settings, `MOVING=<km/h>` takes each picture on the move.

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
  headless (`--use-angle=vulkan --enable-features=Vulkan`, as in `tools/perf-frame.cjs`; WebGPU is there with these flags).
  The GPU needs the `render` group (`dev` is in it since 11-10; a shell older than that login is not: check
  `id -nG`, else Chrome silently renders with llvmpipe; `~/.local/opt/quality/gpurun.sh VAR=… <command>` runs one
  through `sudo -u dev` with the groups, variables given as arguments).
- The GPU picks its own clock (800–2100 MHz) and frame costs change ~2× with it: compare builds with paired runs.
- ubuntu-dev is a Proxmox VM (QEMU Q35) with the RX 5700 XT passed through. Navi 10 cannot be reset from a VM restart:
  after a `reboot` (or a start within ~30 s of a shutdown) amdgpu fails (`PSP load smu failed`, no `/dev/dri`) and
  Chrome falls back to llvmpipe. Recovery: shut the VM down, wait ≥ 3 min, start it from Proxmox (boots 11-08 and 10-15
  failed this way; every start after ≥ 3 min worked). Rebinding amdgpu inside the VM does not help (mode1 reset fails).
  The lasting fix is vendor-reset on the Proxmox host. Check with `ls /dev/dri` before GPU work. The live stack has
  `restart: unless-stopped`, so it comes back by itself after the VM starts.

## Gotchas
- Rendering (`render/RenderHost.ts`, created by `ui/GameCanvas.tsx`; no react-three-fiber): `WebGPURenderer` + a TSL
  `RenderPipeline` (scene → ambient occlusion → bloom → tone mapping (AgX) + the time of day's grade → SMAA → lens). `?webgl=1` forces the WebGL 2 backend. Custom
  shaders are TSL node materials only: no `ShaderMaterial`, no `onBeforeCompile`, no `THREE.Points` with a size
  (WebGPU points are 1 px: particles and lamps are instanced `Sprite`s, `fx/SpritePool.ts`). Plain three.js materials
  (GLB, `MeshStandardMaterial`) still work: the renderer makes their node twins. An `InstancedMesh` with no instances
  must not reach the scene (WebGPU refuses its empty buffer; `Game` drops them from the scenery).
  A post pass at less than full size is `rtt(node, null, null, { resolutionScale })` (`convertToTexture` is always full
  size). three's `GTAONode` cost 3.2 ms at 4K whatever its settings: the occlusion is our own (`render/ambientOcclusion.ts`).
  Measure a new pass with `tools/perf-pass.cjs` before keeping it.
  What costs main-thread time in this renderer (each found with a CPU profile, 34 → 133 fps):
  a shader is built per `InstancedMesh` (never one per chunk: `render/instancing.ts`, `ChunkedLods` = two meshes for
  all trees, instance data as geometry attributes); `alphaTest` on anything that throws a shadow (use `cutout()`, a
  mask node); every draw call (~30 µs, and once more per shadow map: `render/mergeParts.ts` merges a car model per
  material, `CarVisual` lets only shell / glass / wheels throw shadows, only the followed car's headlights throw
  any); a `DynamicDrawUsage` attribute is uploaded every frame, changed or not. A material's nodes (`materialColor`…)
  read the material being drawn, which in a shadow map is the shadow material: name the texture itself there.
- Upscaler (settings アップスケーリング, off by default; `RenderHost` + `render/TemporalUpscaler.ts`): WebGPU draws the
  scene at 50–100 % with a jittered camera into three targets (colour, `velocity`, `reactive`) and gathers the frames
  at the output's size (three.js' `TAAUNode` with our resolve; SMAA off, RCAS after); the WebGL 2 backend uses FSR 1.
  What new scene content must respect: a see-through material without depth (`transparent && !depthWrite`) writes no
  motion vector and marks the reactive mask by its opacity or light (`userData.reactive = 0` for wide soft layers);
  a material with its own `positionNode` on opaque geometry must also assign `positionPrevious` (`instancedMaterial`
  does), or its motion vectors lie and it smears; shaders are precompiled only through `RenderHost.precompile`
  (the scene pass' targets, and the unjittered projection for the motion vectors). Check a change with
  `SET='{"upscale":true,"upscaleMode":"quality"}' MOVING=200 node tools/shots.cjs <label>` next to a native run, and
  `~/.local/opt/quality/flicker.cjs` (a still scene must hold still).
- Own 3D models (no third-party assets): Blender Python scripts built by `BLENDER=<bin> node tools/blender-models.cjs
  <trains|cars|props|creatures> [ids] [--render [dir]]` (Blender 5.2 headless → GLB → glTF-Transform: meshopt, WebP;
  trains also palette textures). Scenery: `tools/blender/props/<id>.py` → `public/models/props/<id>.glb`; size,
  facing (+Z = front) and origin are set in `PROPS` (`render/props.ts`), placement in `TrackScenery.ts`. Each model
  falls back to the procedural shape when it fails to load. The cockroach: `tools/blender/creatures/roach.py` (skinned,
  scuttle cycle resampled at export). A train's line variants (`KINDS.trains.variants`) are the same script with
  `--variant <name>` → `<id>-<name>.glb`.
- Cars are all our own Blender models (`tools/blender/cars/<id>.py` + `<id>_*.py`, fitted to photos with the files in
  `fitdata/<id>/`) built by `BLENDER=<bin> node tools/blender-models.cjs cars [ids]` → `public/models/cars/<id>.glb`,
  loaded at runtime; a missing GLB falls back to the procedural builder. Contract: node `body`, wheel pivots
  `wheel_*` with `spin_*` children, swap materials by name (paint, glass, headlight, taillight, …; docs/ASSETS.md).
  Pop-up lamps modelled raised: nodes `popup_l` / `popup_r` + material `popup_lens`; modelled closed instead:
  `CarSpec.popUpLamps` (runtime pods in `CarVisual`). The optimiser prunes empty nodes, so `CarModel.deriveAnchors`
  rebuilds lamp and exhaust anchors from the geometry (a part named `exhaust` gives the tailpipe; else
  `CarSpec.exhaust`). Lamp materials only on lamp parts (check: only at the car's ends). Dark lens textures:
  `tailLampGain`. Unpainted metal swatches (the Cybertruck's stainless; with `clearcoat` the H2's mirror coat): `CarSpec.bareMetal`. A new model goes in
  only after the owner has seen its sheet; never label a third-party model 自作.
- Never leave a transmissive (refractive) material in the scene: three.js then renders every opaque object a second
  time per frame. Loaded car materials are flattened by `CarModel.withoutTransmission`.
- Courses live in `track/courses.ts` (design + `Landform` from `track/landforms.ts` + rivals, medals, music, art).
  After changing a course design, regenerate the CPU ghosts (`npm run seed:bots`) and re-check medals with the sim.
  `CourseInfo.style`: `'touge'` (the three passes) or `'autobahn'` (motorway scenery in `render/autobahn*.ts`, no touge
  dressing). The AI's speed cap is `CourseDesign.aiTopSpeed` (default 62 m/s); sims take the course with `COURSE=<id>`.
  The autobahn's oncoming traffic is the game's cars: `render/trafficModels.ts` flattens each car's model into four
  instanced parts (paint / gloss / matte / lamps), simplified with meshoptimizer at load; a new car GLB shows up there
  without further work.
- Online battle (≤5 players, `game.online.max_players`): lobby/start/results via `RoomController`; car states are presence-channel client events
  (`client-state`, ~12 Hz) relayed by Reverb, which runs inside the `app` container (entrypoint, `START_REVERB`), proxied by
  nginx at `/app/`. Reverb key/secret are generated per container; never commit them. Client: `store/online.ts`,
  engine side `game/net/RemoteRacers.ts`. Online race time = max(physics clock, wall clock since the shared green light).
  Start grid: `game/net/grid.ts` `onlineGrid(room, startS)`, a pure function of the room (slot + vehicle of everyone) used
  for the local car and the peers alike: rows of up to three in the narrowest start road (9.5 m), trains behind the
  others, rows as far apart as the vehicles in them are long (`grid.test.ts` checks every course and vehicle).
  One paint per slot: `SLOT_COLORS` (five).
- Public access: Cloudflare Tunnel, started by plain `docker compose up` when `.env` has `COMPOSE_PROFILES=tunnel` and `CLOUDFLARE_TUNNEL_TOKEN` (dashboard route → `http://web:80`); an explicit `--profile dev|test` replaces it.
  nginx restores the visitor IP from `CF-Connecting-IP`, trusting only cloudflared's fixed address `172.30.77.10`: keep `docker-compose.yml` and `docker/web/nginx.conf` in sync.
- Race setup order (single player): mode → course → time & weather (`ConditionsScreen`) → car (`GarageScreen`) → AT/MT
  (`TransmissionScreen`) → rival (rival mode) → race; ghost battles pick the ghost between conditions and car. The last
  choices persist in settings (`timeOfDay`, `autoShift`) but are no longer in the settings screen. Online rooms carry the
  host's `time_of_day`; AT/MT stays each player's. The host can start only when every member is `loaded` (reported by
  the game once it shows the room's course) and every guest is `ready` (the 準備完了 button, a toggle; the start button is
  the host's own). The server enforces it and takes `ready` back on a change of car (the client also on AT/MT), of the
  room's course or conditions, at every start and rematch.
- Trains (joke entries, `vehicle/trains.ts`): the sim is only the leading front bogie; `TrainModel` draws three cars
  along its driven path every frame (`CarVisual.tick` → `rig.train.update`; call `CarVisual.refresh()` after moving
  a root by hand). Performance comes from the real figures via `trainSpec` (torque curve, redline, brake force);
  check with the train tests in `vehicle.test.ts`. Models (all own, `TrainInfo.model.own`) are Blender Python scripts:
  `tools/blender/<id>.py` (assembly, CLI `--out/--render/--views/--variant`) + part modules `tools/blender/parts/` +
  `<id>_textures.py` (LED displays, numbers) + `train_kit.py` (frame, materials, export) + `showcase.py` (trackside
  check renders) → `BLENDER=<bin> node tools/blender-models.cjs trains <id> [--render]` (deterministic). Contract:
  nodes car0..car2, origin at the bogie midpoint on the ground, front +Z (Blender: game x, −z, y → Blender x, y, z).
  Cars of unequal length (E5): `TrainInfo.consist` (`trainBogiePath`). Displays show the line's name, never a station.
  Line liveries (`TrainInfo.liveries`, the garage swatches): `variant` → model `<id>-<variant>.glb` (lazy-loaded,
  the base model meanwhile), optional `series` / `control` / `vvvf` for that line's cars (`specForLivery`, the sound
  keyed by the pattern); `swatch` when two lines share a band colour.
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
  `List.Sort`); `vvvf.test.ts` compares with the C# build's output (`tools/vvvf-ref/README.md` to regenerate). The
  running noise is synthesised, no recordings (`audio/running.ts` in AudioWorklet `train-running`: rolling roar by
  octave bands, rail joints timed per axle from carLength / bogies / `TrainInfo.running.axle`, wind ∝ v⁶, the rotors'
  hum from wheel and gear ratio, flange squeal from the lateral acceleration Game.ts passes, brake hiss);
  `TrainInfo.running` is optional (defaults: commuter on jointed 25 m rails; `rail: 'welded'`, `sealed` for a
  Shinkansen). Check a change by rendering, not by ear only: `tools/train-run-wav.ts` (Node: running noise at fixed
  speeds, a run-up, a curve; band levels against the old recordings' numbers), `tools/vvvf-train-wav.ts` (Node,
  inverter only, levels per speed band) and `tools/vvvf-game-wav.ts` (Chrome + vite preview: the game's whole chain,
  offline). A train's acceleration over its whole range (level, and up a gradient): `npx tsx tools/train-accel.ts <id> [‰]`
  (the E5 matches the published figures; the train test bounds its 0→300 km/h time). Medals: `TRAIN_MEDALS` in courses.ts (re-run tools/sim-run.ts
  with the train ids after physics or course changes). `CAR_ORDER` = cars only (AI, bots, GLBs), `VEHICLE_ORDER` =
  cars + bikes + trains + the cockroach (player-facing lists); the backend's `game.cars` lists them all.
  The L0 maglev (`TrainInfo.maglev`, `sound: 'lsm'`): on its tyres up to `lift` km/h, then the model floats `height` m
  higher (`TrainRig.update(anchor, dt)` sees the speed) and `running.ts` drops the tyre roar, joints, squeal and brake
  grind for the wind and the guideway's field hum; articulated bogies are a `consist` with `front: 0` cars.
- Kinds of vehicle (`vehicle/kinds.ts`): `kindOf(spec)` → car / bike / train / creature; what differs in shared code
  (badge, garage framing, lamp height, exhaust) is a `KIND_TRAITS` entry, not a branch per call site. Electric cars
  (`engine.electric`, `gears: [1]`: Cybertruck, Yangwang U9) sound through `audio/EvSound.ts` and have no exhaust;
  `engine.strokes: 2` / `supercharger` change EngineSound's timbre (NSR, H2).
- Motorcycles (`vehicle/bikes.ts`, `BikeInfo`): VehicleSim on a virtual 0.7 m track with a 0.1 m centre of mass (never
  tips; ×4 pitch/roll inertia). The real centre of mass (`com`) sets the wheelie cap on the drive and the stoppie limit
  of the brakes, and a virtual pitch load transfer moves the drive/brake limits only (side grip stays on the static
  load). Brakes by load, rear brake for the handbrake, traction control, slipper clutch, no drift state, a steering cap
  at the grip limit: without these the bikes spun at every braked corner entry. The model leans by the root's motion
  (`render/BikeModel.ts`: GLB nodes `steer`/`spin_f`/`spin_r` in `public/models/bikes/<id>.glb`, else procedural), the
  rider-view camera rolls with it (`BIKE_CAMERA`). Medals: `BIKE_MEDALS`. Check with `npx tsx tools/handling-feel.ts
  nsr250r,ninjah2,hayabusa` (the vehicle test bounds the bikes' corner slip).
- The cockroach (joke entry, `vehicle/roach.ts`, id `roach`, last in `VEHICLE_ORDER`): a car-like sim on one fixed
  ratio (`singleRatio` → no AT/MT) with ~2.6× a sports car's grip (half the steering lock, else it turns twice as hard),
  Mach 1 at the top (the chase camera's lag is capped for it); drawn by `render/RoachModel.ts` from a
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
