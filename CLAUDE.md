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
  check that the new build is served. Before a deploy: `node tools/gpu-errors.cjs` on the build (GPU errors over the
  garage / race paths, and that the race camera is with the car) and look at one picture of a race: tests look at
  states, and a build whose camera stayed at the garage passed them all (11-11).
  Other compose projects on the host are unrelated: leave them alone.
- `vite preview` inherits the dev proxy (`/api` → localhost:8080 = the live server): always serve with
  `API_PROXY=http://127.0.0.1:9 npx vite preview …` so test runs cannot create players or submit runs.
- No Node on the host: use a user-space Node 24 tarball (nodejs.org) and `npm i playwright-core` outside the repo
  (`PW_MODULE=<that>/node_modules/playwright-core`); Chrome is `/usr/bin/google-chrome` and renders on the RX 5700 XT
  headless (`--use-angle=vulkan --enable-features=Vulkan`, as in `tools/perf-frame.cjs`; WebGPU is there with these flags).
  The GPU needs the `render` group (`dev` is in it since 11-10; a shell older than that login is not: check
  `id -nG`, else Chrome silently renders with llvmpipe; `~/.local/opt/quality/gpurun.sh VAR=… <command>` runs one
  through `sudo -u dev` with the groups, variables given as arguments).
- The GPU picks its own clock (800–2100 MHz) and frame costs change ~2× with it: compare builds with paired runs.
  Uncapped frame rates also follow whatever else runs on the machine (another session's test job moved them between
  47 and 120 fps on one build, 11-11): check `uptime` first; what holds then is the GPU time per pass
  (`tools/perf-pass.cjs`) and the make-up of a CPU profile (`~/.local/opt/quality/cpuprof.cjs` with `DUMP=`,
  `profdiff.py`), not the fps.
- ubuntu-dev is a Proxmox VM (QEMU Q35) with the RX 5700 XT passed through. Navi 10 cannot be reset from a VM restart:
  after a `reboot` (or a start within ~30 s of a shutdown) amdgpu fails (`PSP load smu failed`, no `/dev/dri`) and
  Chrome falls back to llvmpipe. Recovery: shut the VM down, wait ≥ 3 min, start it from Proxmox (boots 11-08 and 10-15
  failed this way; every start after ≥ 3 min worked). Rebinding amdgpu inside the VM does not help (mode1 reset fails).
  The lasting fix is vendor-reset on the Proxmox host. Check with `ls /dev/dri` before GPU work. The live stack has
  `restart: unless-stopped`, so it comes back by itself after the VM starts.

## Gotchas
- Rendering (`render/RenderHost.ts`, created by `ui/GameCanvas.tsx`; no react-three-fiber): `WebGPURenderer` + a TSL
  `RenderPipeline` (scene → ambient occlusion → the lights' glow in the haze → bloom → tone mapping (AgX) + the time of
  day's grade → SMAA → lens). `?webgl=1` forces the WebGL 2 backend; without WebGPU, or when it fails while running
  (errors in a burst, a lost device), the game goes to WebGL 2 by itself (`render/backendChoice.ts`, settings 描画方式;
  check with `node tools/backend-fallback.cjs` on the GPU). Custom
  shaders are TSL node materials only: no `ShaderMaterial`, no `onBeforeCompile`, no `THREE.Points` with a size
  (WebGPU points are 1 px: particles and lamps are instanced `Sprite`s, `fx/SpritePool.ts`). Plain three.js materials
  (GLB, `MeshStandardMaterial`) still work: the renderer makes their node twins. An `InstancedMesh` with no instances
  must not reach the scene (WebGPU refuses its empty buffer; `Game` drops them from the scenery).
  A post pass at less than full size is `rtt(node, null, null, { resolutionScale })` (`convertToTexture` is always full
  size). three's `GTAONode` cost 3.2 ms at 4K whatever its settings: the occlusion is our own (`render/ambientOcclusion.ts`).
  Measure a new pass with `tools/perf-pass.cjs` before keeping it.
  `render/threeFixes.ts`: three.js 0.186 keeps a destroyed GPU buffer on an `InterleavedBuffer` after
  `geometry.dispose()` (a model shown, freed and shown again froze the picture on WebGPU); check whether it is still
  needed when three.js is updated. A check that starts a race directly does not cover this: go through the garage
  (`node tools/gpu-errors.cjs` counts the GPU's validation errors over those paths).
  `keepShaders` (same file): three.js throws a built shader and its pipeline away with the last object that used
  them, so every car leaving the scene cost its 22–32 shaders again at the next one (0.3–0.6 s); they are kept now
  (not those keyed by one object: `InstancedMesh`, morph targets). It reaches into `renderer._nodes` /
  `_pipelines`: check both when three.js is updated (`~/.local/opt/quality/builds2.cjs` counts shaders built per step).
  Passes that work from the depth buffer share `render/screenSpace.ts` (view position from the depth, sized targets,
  the surface-keeping blur that cancels a five-pixel tap pattern). The glow in the haze (`render/volumetricLights.ts`)
  takes its lights from `volume` (the course's lamps, the cars' cones via `CarVisual.beamInto`) and its amount from the
  preset's `haze`: a new kind of light source that should glow is added there.
  What costs main-thread time in this renderer (each found with a CPU profile, 34 → 133 fps):
  a shader is built per `InstancedMesh` (never one per chunk: `render/instancing.ts`, `ChunkedLods` = two meshes for
  all trees, instance data as geometry attributes); `alphaTest` on anything that throws a shadow (use `cutout()`, a
  mask node); every draw call (~30 µs, and once more per shadow map: `render/mergeParts.ts` merges a car model per
  material, `CarVisual` lets only shell / glass / wheels throw shadows, only the followed car's headlights throw
  any); a `DynamicDrawUsage` attribute is uploaded every frame, changed or not. A material's nodes (`materialColor`…)
  read the material being drawn, which in a shadow map is the shadow material: name the texture itself there.
  What makes the picture stand still (all materials rebuilt in one frame, 1–2.6 s): the shaders are built for the
  scene's set of lights (ids + `castShadow`, in scene order), the fog object and the environment texture object.
  So every light lives in `render/LightRig.ts`, made once: never add, remove or re-parent a light, never make a
  second fog or PMREM target; change intensity / colour / position (a car's headlights are `CarVisual.headlight()`
  → the rig's three spots via `Game.updateBeams`; the vending machine's light is `vendingSpot`). Measure with
  `~/.local/opt/quality/hitch.cjs` (frame gaps over 40 ms per action).
  Courses stay built after leaving them (`Game.leaveWorld` / `enterWorld`, `keepCourses`, `keepBudget` in MB of
  `gpuBytes`, oldest freed first, all on a GPU out-of-memory: `releaseKept`); `disposeWorld` frees only what no
  other built course uses. Vehicle models load in stages (`render/vehicleModels.ts`: one car before the title, the
  rest behind the menus): whatever shows a vehicle first waits with `Game.needs` / `ensureVehicleModels`.
- Ground, road and roadside at quality medium and up (`surfaceDetail` 1–3 in `store/settings.ts`; 0 = `low`, the old
  plain path `plainRoadside` / `plainTerrainMaterial`): `render/terrainMaterial.ts` (`groundMaterial`: photo layers
  blended by slope, height and the `surf` vertex attribute), `render/roadMaterial.ts` (`roadSurface`: wear, markings
  and puddles in one material; it reads the `road` attribute from `roadGeometry`: every asphalt strip merged into
  the road must carry it), `render/weather.ts` `wetness` (set in `Game.applyTimeOfDay`). Costs ~1–1.8 ms of GPU time
  a frame (scene pass, 1080p–4K); the layer textures are 512 px (medium, 2.6 MB) or 1024 px (high / ultra, 9.5 MB),
  loaded before the title: `ACG=<dir of ambientCG zips> node tools/surface-textures.cjs [photo|own|all]` →
  `public/textures/terrain/{512,1024}`.
  Roadside (`render/roadside.ts`, materials in `render/structureMaterials.ts`): positions are `out` (metres outward
  from the barrier line = width/2 + 0.6) and `h` (metres above the road there); a profile is a polyline of (out, h)
  with its visible side on the left of the drawing direction; (right, up, fwd) is left-handed, so a module's
  triangles are flipped when `side * dz > 0`. Colliders are not built here. Its models: `BLENDER=<bin> node
  tools/blender-models.cjs roadside [ids]` → `public/models/roadside/<id>.glb`, materials by name only (`METAL` in
  `structureMaterials.ts`); the optimiser drops the UVs of untextured models (`Roadside.bake` derives them);
  `--render` does not work for this kind: run the script with `--out <dir> --render <dir>`.
  A cut-out or line thinner than a pixel flickers under the upscaler (the rockfall net): dissolve it by `fwidth` of
  its UV, keep thin steel dark.
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
  (`client-state`) relayed by Reverb, which runs inside the `app` container (entrypoint, `START_REVERB`), proxied by
  nginx at `/app/`. Reverb key/secret are generated once and kept in the `secrets` volume (see Stack); never commit them. Client: `store/online.ts`,
  engine side `game/net/` (`game.net`). Online race time = max(physics clock, wall clock since the shared green light).
  Car states: arrays of whole numbers at 30 Hz, at once on an impact (`net/codec.ts`: pose, velocity, acceleration,
  turn rate, sequence, respawn epoch; Reverb re-encodes JSON in PHP, so whole numbers only), sent and received by
  `NetLink` on a `NetTransport` (`store/online.ts` `relay`: the seam a WebRTC DataChannel will take). A clock per peer
  (`net/clock.ts`, NTP-style echo on the state stream: Reverb has no time source). Peers are drawn in the present
  (`PeerTrack`: the newest packet carried on, corrections eased, a snap above 8 m or on a respawn), not in an
  interpolation buffer: the buffered mode (`?netmode=buffered`) shows a car metres behind where it is, and solid cars
  then touch at different moments on the two screens. Link numbers per peer: N key in a race, `?netstats=1`,
  `game.net.stats()`; a bad link for tests: `?netsim=<one-way ms>,<jitter ms>,<loss %>` or `game.net.impair(…)`.
  Check a change with `npx tsx tools/net-replay.ts <vehicles>` (error against the true path under delay, jitter, loss;
  `duel=1`: when two solid cars touch on each screen). Reverb: rate limiting must stay off
  (`REVERB_APP_RATE_LIMITING_ENABLED`: 60 messages a minute), `tcp_nodelay` is on (`config/reverb.php`: without it
  three players and more waited 23–30 ms per relay), messages ≤ 10 kB.
  Waiting room: every member's vehicle stands on the course in the start grid's rows (`Game.showLobby`,
  `net/LobbyLineup.ts`, `net/lineup.ts`; `window.__game.lobbyState`), under the garage's camera. The vehicle a member
  is looking at in the car select is told to the others (`client-browse`, ≤ 2 Hz, only changes: `net/browse.ts`,
  `store/lobby.ts`, which hears the game's `'garage'` event) and stands in their seat as 選択中; only the select's
  confirm calls `chooseCar` (the server takes the ready back). Closing the select: `showRoomLineup()`.
  Start grid: `game/net/grid.ts` `onlineGrid(room, startS)`, a pure function of the room (slot + vehicle of everyone) used
  for the local car and the peers alike: rows of up to three in the narrowest start road (9.5 m), trains behind the
  others, rows as far apart as the vehicles in them are long (`grid.test.ts` checks every course and vehicle).
  One paint per slot: `SLOT_COLORS` (five).
- Stack (`docker-compose.yml`): nginx looks `app` up per request (`resolver 127.0.0.11` + `$app` in `docker/web/nginx.conf`:
  a name written straight into `fastcgi_pass` / `proxy_pass` is resolved once at start and answers 502 after the
  backend alone is rebuilt); `app` is healthy when PHP-FPM listens and Reverb answers over HTTP, `web` starts after that;
  a watchdog in `docker/php/entrypoint.sh` ends a Reverb that stops answering (it can hang with its port open and
  ignore SIGTERM: seen after `docker network disconnect` / `connect` on the running container, so do not do that). Keys that
  `.env` does not give (APP_KEY, Reverb key / secret) are generated once into the `secrets` volume
  (`docker/php/entrypoint.sh`), so the games that are open reconnect after a deploy. `backup` dumps the database once a
  day into the `backups` volume (`docker/backup/backup.sh`, one file per day of the month). Logs are capped (`x-logging`).
  The client reloads itself once when a chunk of an older build is gone (`vite:preloadError` in `main.tsx`).
- Public access: Cloudflare Tunnel, started by plain `docker compose up` when `.env` has `COMPOSE_PROFILES=tunnel` and `CLOUDFLARE_TUNNEL_TOKEN` (dashboard route → `http://web:80`); an explicit `--profile dev|test` replaces it.
  nginx restores the visitor IP from `CF-Connecting-IP`, trusting only cloudflared's fixed address `172.30.77.10`: keep `docker-compose.yml` and `docker/web/nginx.conf` in sync.
- Car select (`ui/garage/`: `VehiclePicker` is the one component: single player's `GarageScreen`, online's
  `OnlineVehicle`): tabs by kind (`KIND_ORDER`, `KindTraits.label`), a grid of thumbnails, bars from measured figures,
  sorting, favourites (`store/garage.ts`, localStorage `touge-garage`). A new or changed vehicle needs
  `npx tsx tools/vehicle-stats.ts <id>` (the headless sim: 0–100, top speed, skid-circle g →
  `vehicle/vehicleStats.json`; a vitest fails without an entry) and `node tools/thumbs.cjs <id>` (the game's own
  garage on the GPU → `public/img/vehicles/<id>.webp`; run them all again after a change of the look). The garage's
  camera is aimed by `game.garageFraming` (the picker puts the vehicle in the free part of the screen) and a kind's
  `garage.middle` / `garage.span`. Trees inside the camera's circle are shrunk away (`clearing` in
  `render/instancing.ts`, set by `Game.garageCamera`), in the waiting room too.
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
- The rival's language model (rival battles; `ai/RivalMind.ts`): a model never drives. It gives the rival's line
  before the start and after the finish (`hud.rivalLine`, event `rivalLine`), and in the race it can only call two
  things the game then does by rule: `AIDriver.block(seconds)` (moves in front of the chaser across the road, inside
  the road's edges; the road is left open as long again afterwards) and the horn (`AudioEngine.horn`, also the
  player's H key). Whom to ask is a list of `RivalBrain`s (`game.rivalBrains`: `api/rivalBrain.ts` = the server;
  the owner dropped inference in the browser on 11-11: everything goes through the API), with the game's own lines and rules (`scriptedBrain`) always
  last: no key, no network, a slow answer (line 3.2 s, decision 1.5 s) or the setting ライバルAI off give the same game.
  Server: `POST /api/ai/taunt|decide` (`RivalAiController` → `Services/RivalMind.php` → the owner's LiteLLM gateway,
  `config/llm.php`; its address and key are `LLM_API_URL` / `LLM_API_KEY` in `.env` only: never to the browser, never in a log
  or commit, no address written into the code). The requests carry
  facts only (ids, numbers, the rival's name / title / description), never a prompt; 45 a minute per address; 503 =
  nobody to ask. The decision is real tool calls (`block_player`, `sound_horn`), clamped by the server. The models are
  `LLM_TAUNT_MODELS` / `LLM_DECIDE_MODELS` (first that answers). Check the block with
  `BLOCK=4 npx tsx tools/sim-duel.ts <lead:level> <chase:level>`.
- The rivals' voice (owner 11-11; `game/audio/speech/`): a rival's line is spoken by a speech model on the player's
  GPU: Supertonic 3 (four ONNX graphs, 398 MB, OpenRAIL-M) through `onnxruntime-web/webgpu` in a module worker
  (`speech.worker.ts`; `Speech.ts` is its controller, `text.ts` the publisher's text preparation: NFKD, `<ja>…</ja>`,
  only the sound tags `<laugh>` `<breath>` `<sigh>` pass, so a language model cannot write tags). **Text is the rule,
  the voice an extra**: no WebGPU adapter, no model on the server (`/tts/supertonic-3/onnx/tts.json` must be the
  model's own JSON), a failed download or set-up, a slow answer: the line is shown and nothing else changes. No CPU
  fallback (it would take the game's frames). The model is fetched only after a yes (setting `rivalVoice`:
  `ask` → the offer on the rivals screen, `ui/screens/VoiceOffer.tsx`; `on` / `off`; settings rows ライバルの声 and
  音声モデルのデータ), kept in Cache Storage (`touge-tts-supertonic-3`), brought up on the way to a rival battle and
  released when another kind of race starts (`store/voice.ts`: its weights are ~400 MB of video memory).
  `Game.rivalVoice` is injected like `rivalBrains`; `rivalSays` waits `VOICE_WAIT` (0.7 s) for the sound so that line
  and voice come together; `AudioEngine.say` plays it at one level over the `bed` (everything else, turned down
  meanwhile). A voice per rival: `RivalInfo.voice` (`F1`–`F5`, `M1`–`M5`). Server: the model is not in the
  repository; `docker compose --profile tts run --rm tts-fetch` puts it into the `tts` volume once (pinned revision,
  SHA-256 per file, `docker/tts/fetch.sh`), nginx serves it at `/tts/` (404 without it, never the app's page); the
  test stacks have none, so E2E never meets the offer. The model's files are the publisher's, unchanged, with its
  LICENSE next to them (linked from the offer and the settings: the licence asks that its use restrictions reach
  whoever gets the model). Local check: `~/.local/opt/tts/proto/ttsserve.cjs` + `TTS_PROXY=http://127.0.0.1:4191
  npx vite preview`, then `~/.local/opt/quality/voicecheck.cjs` on the GPU (offer, download, a spoken line in a rival
  battle, frame gaps with the model busy, the second visit from the cache); `window.__speech` for probes.
  The vite build makes ES-module workers (`worker.format: 'es'`): the audio worklets are built that way too.
- Interface (redesigned 11-11: a telemetry terminal over the live scene; `ui/theme/`: `tokens.css`, `base.css`,
  `screens.css`, `picker.css`, `online.css`, `hud.css`; parts in `ui/kit.tsx`, the shell around every menu in
  `ui/Shell.tsx`). Colour: tokens only, as rgb triplets (`rgb(var(--c-cyan) / 0.3)`); cyan = focus and live data,
  magenta = rivals, others online, alerts, amber = medals and warnings, green = ready; no literal colour outside
  `tokens.css`. Shape: a cut panel is one shared rule in `base.css` (`--c` cut, `--edge`, `--fill`): add a new
  panel's class to that selector list. Type: Saira Variable for Latin and figures (width axis `--w-tight` /
  `--w-cond` / `--w-norm`, tabular figures), Zen Kaku Gothic New, Shippori Mincho for place names; 1rem follows the
  screen's height. Motion: durations and easings are tokens; entrances use `var(--kf-*)` so that `.motion-off` (the
  setting UI アニメーション, or reduced motion) swaps them for fades; screen changes go through `ui/motion.ts`
  `useScreenWipe` (the incoming screen is uncovered by a **mask, never a clip path**: a clip path takes the pointer
  away for the wipe's 240 ms); figures count through `data-count`; `FocusFrame` is the moving focus marker; what must
  move while the main thread is blocked (the busy mark, the boot bar) is a CSS transform / opacity animation only.
  Lists the keys walk: hover moves the selection (`hoverSelect`), inside `.focus-box` only the selected button is
  filled. `window.__app` is the app's store for probes (as `__game` is the game).
  The grains over the menus (`ui/fx/`, owner 11-11: fine, close to 3D particles; grains alone depict things and
  grains alone emphasise them; "the part in charge of beauty"): up to 48 000 grains (12 000 on a phone) in a volume
  behind the screen, one canvas over the interface (`Cloud.tsx`; not in a race, not with motion off, none on a
  software renderer). `cloud.ts` is the simulation (DOM-free, tested): three interleaved groups (dust / the thing a
  screen shows / the selection's edge); a group is given a `Shape` (points in its own space, placed anew every frame)
  and its grains fly there, a shape let go scatters through the volume. `shapes.ts` makes the shapes: a course's
  relief (`courseRelief`: road, start / finish beams, the land as contour lines; laid across its place, `box` fits
  it), a glyph from a mask, the edge of a selection (`shellOf`). In the markup: `data-cloud="course:<id>"` or
  `"glyph"` (`data-cloud-fill="0…1"`: how much has gathered, as on the loading screen) = a thing depicted where the
  element stands; the emphasis goes to what the pointer is on (anything with `cursor: pointer`), else the screen's
  `FocusFrame`, else an element with `data-grains` (`"line"` / `"ring"` / its panel; `data-grains-tone`;
  `data-grains-first="<ms>"`). While the grains depict, the app has the class `cloud-on` and the page's own picture
  of the same thing steps back (the title's kanji, the drawn focus frame). The count follows the grains' own cost
  on the main thread (`BUDGET` 4 ms a frame; 48 000 cost ~3–4 ms here), never the frame time. What is slow in the
  step: `Math.hypot`, sines (a table), anything per grain per frame that could be done for a quarter of them in turn.
  **Nothing else on the page may make a WebGL context while the game is on WebGPU**: it lost the game's device
  (`VK_ERROR_DEVICE_LOST`, 11-11). Whatever else draws uses the game's own API: the grains draw on
  `RenderHost.gpuDevice` (`cloudRenderGpu.ts`), or with WebGL 2 next to the WebGL 2 backend (`cloudRender.ts`); the
  rivals' voice (WebGPU, in a worker) is offered only when the game is drawn with WebGPU (`Speech.usable`).
  The title's and the replay's camera (`Game.cinematicCamera`): every shot is laid along the road or checked against
  the ground (`tracksideAnchor`, `groundClear`); a new shot must be too (an offset from the car alone ends up inside
  a slope or behind the roadside).
- Who plays (owner 11-11: accounts come from Authentik; nothing in the browser keeps an account any more). **Members**
  log in through the owner's Authentik (`AuthController`: authorization code + PKCE, the code is exchanged on the
  server; `config/authentik.php`, `AUTHENTIK_*` in `.env` only: never to the browser, a log or a commit). The account
  is Authentik's subject (`players.oidc_sub`, the owner's wish: never match by name or mail); the name is taken from
  Authentik at every login. A login is the cookie `touge_session` (HttpOnly, SameSite=Lax; its hash in
  `player_sessions`, 30 days from the last visit, `Services/MemberSession.php`); a request that changes something is
  taken from the cookie only with the header `X-Touge-Client` (`api/client.ts` sends it always). **Guests** are
  everyone else: `POST /api/players` gives a name a pass for the sitting (bearer token, 24 h, in the page's memory
  only), and a record asks for the name every time (`Results`: only a member's is sent by itself);
  another name is another guest. A token without an end date (the players of before 11-11) lets nobody in; a member
  claims such records, and those set as a guest in the sitting, at login (`POST /api/auth/claim`,
  `store/account.ts` `memberArrived`). A member's save data (`players.save` + `save_rev`, `GET/PUT
  /api/players/me/save`): best time per vehicle, records against rivals, favourites (`Progress` in `api/client.ts`),
  merged with the machine's at start and sent 1.5 s after a change (409 = changed elsewhere: merge, send again);
  ghosts are not in it (the runs have them: `best_runs` of `/api/players/me`). **Nothing of a guest is kept by the browser**
  (owner 11-11): pass, times, medals, battle records and favourites live in the page's memory (`guestProgress`,
  the garage store's `partialize`); only device settings (`touge-settings`) are stored. What a browser kept from
  before stays untouched until a member logs in there (it goes into their save); a logout clears the member's
  copy from the machine. The guest's token rides along to Authentik and back in `sessionStorage` (`touge-claim`,
  taken out at once) so that records set just before a login become the member's. Without `AUTHENTIK_*` (dev, the test stacks, E2E)
  everyone is a guest and `/api/content` says `auth.enabled: false`. The redirect URI the provider must know is
  `<public address>/api/auth/callback` (taken from the request: `X-Forwarded-Proto` + `Host`; `AUTHENTIK_REDIRECT_URI`
  overrides). Tests: `AuthTest.php` (Authentik faked), `client.test.ts`.
- Race timing/splits/AI run per physics step (`Game.raceStep`, `driveAI`); keep frame-time logic out of timing.
- Tyre grip = course surface (`CourseInfo.surface.grip`) × weather (`WET_GRIP` in rain): `Game.roadGrip` → `VehicleSim.gripScale`
  (before `AIDriver.calibrate`). Headless tools take the course's grip. Changing a grip: re-check medals with the sim
  and regenerate the bots (`npm run seed:bots`; the seeder replaces a bot's old run).
- Player drifts start only on a deliberate input (handbrake, brake tap + big steer, throttle stab, slip > 16°); the
  grip assist keeps flat-out corners from sliding. The AI drives as `gripDriver` and skips both. Check feel with
  `npx tsx tools/handling-feel.ts` (ordinary corners should stay under ~15° of slip).
- Cars are solid (collision groups in `PhysicsWorld.ts`: GROUND, WALL, CAR, PROXY). Online peers become `net/ProxyCar`
  bodies (group PROXY, collide with CAR only) that follow the peer's path (`net/steer.ts`; `net/RemoteBody.ts` is the
  body shared with the replay tool); after a teleport or the local player's respawn they are ghosted (collider off)
  until clear, and a peer not heard for 2 s stops being solid. `Game.detectCarContact` → thud/shake/scrape. The AI
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
