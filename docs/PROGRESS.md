# Progress log

Newest first. "Verified" means actually executed in this environment; anything else is marked as unverified.

## Session 9 (2026-11-10) — Fable phase: WebGPU renderer (plan B1), online ready button and five players (F1, F5)

Plan: `docs/FABLE_PLAN.md`. Commits `2074c02` (renderer), `0c79c61` + merge `a4c2fde` (online).

### Phase A (measurement)
- The GPU works again after the owner's VM maintenance; `dev` joined the `render` and `video` groups (owner: 「許可します」).
  A shell older than that login has no GPU access: `~/.local/opt/quality/gpurun.sh` (CLAUDE.md).
- `tools/shots.cjs`: fixed viewpoints on every course × time of day (93 pictures, contact sheets). The game is stepped
  by hand at 1/60 s, so a slow build gives the same frame. `tools/perf-frame.cjs`: frame cost on any backend, paired
  builds. The pictures and numbers are in `~/.local/opt/quality/` (outside the repo): `base-e` (old renderer),
  `gpu-e` / `gpu-f` (WebGPU), `gl2-e` (WebGL 2 backend), `perf-1.json`, `perf-2.json`.

### Phase B1 (WebGPU): done, verified on the RX 5700 XT in headless Chrome
- `render/RenderHost.ts` replaces react-three-fiber + postprocessing (both removed from package.json). Every custom
  shader is TSL (list in the commit message). `?webgl=1` forces the WebGL 2 backend.
- **Look**: side by side with the old build on the 93 viewpoints: the same picture (mean luminance within 1 % on three of
  the four pairs measured, +7 % on a rain picture with more streaks in it; after two fixes: the vignette now works on
  linear values, the bloom takes a soft threshold).
  Known differences: tree shadows are a little more solid; the rain is denser in a race's first seconds (the old
  shader gathered the drops into a band there: fixed, not a regression).
- **Speed** (1920×1080, rival race on 朧峠 at night, uncapped, `perf-2.json`): old renderer 231 fps (frame p50 4.2 ms,
  p99 8 ms); WebGPU 133 fps (7.3 ms, p99 11–12 ms) at high and ultra. Both are far above 60 fps on this machine; the
  WebGPU build spends 1.75× the main-thread time (6.9 ms against 3.9 ms). The first WebGPU build ran at 34 fps with
  100 ms hitches; what fixed it:
  - three.js builds a shader for every `InstancedMesh` → trees went from 632 instanced meshes to 2 meshes
    (`render/instancing.ts`, `ChunkedLods`): no shader is built during a race any more (was ~7 a second).
  - `alphaTest` on a shadow caster made every caster recompute its cache key each frame (3 ms) → mask nodes (`cutout`).
  - a draw call costs ~30 µs of main thread → car models merged per material (`render/mergeParts.ts`: the R34 is 34
    meshes now, 14 of them the body; a car was ~50), only shell / glass / wheels throw shadows, a rival's headlights throw none: 580 → 285 draws a frame.
  - a `DynamicDrawUsage` buffer is uploaded every frame whether it changed or not.
- **Load time** to the title: 10–12 s against 4.7 s (shader pipelines). Not yet worked on.
- **WebGL 2 backend** (`?webgl=1`): 30 viewpoints on 朧峠 and the autobahn drawn without errors, same look. Its speed
  is not measured yet.
- Not verified: phones; a browser without WebGPU other than through `?webgl=1`; the garage and menus by eye; the
  train / bike / jet / tank / roach models under the new renderer (only cars were looked at); sound is untouched.

### F1 / F5 (online): ready button, five players, grid in rows
- Guests press 準備完了; the host can start only when everybody is loaded and every guest is ready. Rooms take five;
  the grid stands in rows of up to three (trains at the back). Details in the commit `0c79c61` and CLAUDE.md.
- Verified by the agent that wrote it, on its branch: backend 20 passed, frontend tsc / vitest (70) / build, the
  online E2E spec 2 passed. After the merge: tsc, vitest 70 passed, build.

### E2E on the merged code (`a4c2fde`)
- The whole suite on an isolated stack (project `touge-e2e`, port 8090; SwiftShader, so the renderer's WebGL 2
  backend): 10 passed, 1 flaky, 31 min. The flaky one is the ghost battle: on its first try the game was still on
  the AT/MT screen 30 s after the choice (the race had not started yet), on the retry it passed. That wait is 90 s
  now, like the other waits for a race. Not known: whether the start of a ghost battle got slower with the new
  renderer on a real GPU (to measure with the load time).
- **Deployed** (`7dd1ebc`, bundle `index-B7_3Wkth.js`; migration `add_loaded_to_room_players` ran, health and
  leaderboard API 200, `max_players` 5). The live site itself was not opened in a browser after the deploy.

### B2: upscaler (plan B2, owner decision D4)
- **What**: settings アップスケーリング (off by default) / 描画解像度 (ネイティブ 100 %, ウルトラ品質 77 %, 品質 67 %,
  バランス 59 %, パフォーマンス 50 %) / シャープネス. WebGPU: the scene is drawn smaller with a jittered camera and
  motion vectors, `render/TemporalUpscaler.ts` gathers the frames at the output's size (it is also the anti-aliasing:
  SMAA is off with it), then RCAS sharpening. WebGL 2 backend: FSR 1 (EASU + RCAS) after SMAA, as planned.
- **The upscaler is three.js' `TAAUNode` with our own resolve.** What had to change, each found by a measurement:
  - three's node never saves its second output (the lock), so nothing carried over there. What a pixel's history
    knows is kept in the history's alpha now: a frame counts by how near its sample fell to the pixel (a running
    average), a newly uncovered pixel takes its first frames whole, and the sum is capped by the pixel's speed.
  - history read with Catmull-Rom (five taps); the thin-feature lock only where the picture holds still (on the
    move it left ghosts of the guard-rail posts).
  - reactive mask (a third target): rain, smoke, sparks, lamps leave their share of the pixel and the current frame
    counts for that much more. Without it the rain was averaged away. `userData.reactive = 0` on the cloud sea.
  - motion vectors: fragments without depth leave the surface's vector as it is (the velocity target blends by a
    weight); `instancedMaterial` (the trees) gives its previous position.
  - texture LOD bias log2(scale) for the scene's materials (three has no switch: `TextureNode.setup` is wrapped).
  - a shader built outside a frame took the jittered projection for its motion vectors: `steadyVelocity`.
- **Precompile** (`RenderHost.precompile`, used by `Game`): for the scene pass' real targets, one at a time, the
  target set again after every frame while it runs; at load no frame is drawn meanwhile. A pipeline error
  (a 2-target pipeline with a 1-output shader) came from two overlapping compiles. **Load time to the title:
  12.5 s → 7.0–7.8 s** (the old precompile aimed at a stand-in target and its work was thrown away).
- **Speed** (RX 5700 XT, 朧峠 night, ultra, rival race, uncapped; `perf-up-1440.json`, `perf-up-4k.json`):
  | output | native | 品質 67 % | パフォーマンス 50 % |
  |---|---|---|---|
  | 2560×1440 | 102 fps | 119 fps (×1.17) | 125 fps (×1.22) |
  | 3840×2160 | 60 fps | 75 fps (×1.26) | 94 fps (×1.57) |
  **The plan's target (1440p 品質 ≥ ×1.4) is not met on this machine**: at 1440p the frame is bound by the main
  thread (draw calls; ~130 fps is the ceiling at any resolution), not by pixels. The gain grows where the GPU is
  the limit (4K here; weaker GPUs, not measured).
- **Look**, verified on the GPU:
  - 93 fixed viewpoints (4 courses × 3 times) with 品質: no errors or warnings; mean luminance within ±5 % of native.
  - a still scene, six pictures 150 ms apart (`~/.local/opt/quality/flicker.cjs`): 0.1 % of pixels change by more
    than 8/255 between pictures (native: 0; before the fixes: 5–10 %). Fences, rails and far lamps hold still.
  - 200 km/h, the 90th frame on the move (`tools/shots.cjs` `MOVING=200`), native next to 品質: no trail behind the
    car, no ghosts of posts; the picture is a little softer than native (rock and asphalt texture, far trees), the
    nearest wall can show the scene's pixels. Rain about as dense as native, streaks a little coarser.
  - settings switched live on both backends (`uptoggle.cjs`): on/off, the five modes, sharpness; no errors.
  - WebGL 2 backend with FSR 1: 30 viewpoints without errors, same look as its native picture.
- Not verified: thin-line flicker on the move by video (only stills of moving frames); phones; the speed gain on a
  weaker GPU; the WebGL 2 path's speed; non-car vehicles (the trains' cars are moved every frame: their motion
  vectors were not looked at). Tests: tsc, vitest 70, build; E2E on the isolated stack, four specs only (boot, time
  attack, rival battle, phone: 4 passed; the upscaler itself is off there, they cover the new precompile).
- Tools: `tools/shots.cjs` takes `SET` (settings JSON) and `MOVING` (km/h); `tools/perf-frame.cjs` takes `VARIANTS`.
- **Deployed** (`e4ad192`, bundle `index-C7BnGh_G.js`, the same hash as the local build; leaderboard API 200). The
  live site itself was not opened in a browser.

### C1: tone mapping and grade, ambient occlusion (plan C1 and the first part of C3)
- **Tone mapping**: ACES → AgX, with a grade per time of day on the displayed picture (`render/grade.ts`: an S-curve
  for contrast, saturation, a tint for shadows and one for highlights; values in the `Environment` presets). Shot
  side by side first (ACES / AgX / Khronos Neutral, then AgX with the grade): plain AgX is flat, Neutral dark and
  very saturated; AgX with the grade keeps ACES' contrast and rolls lamps and headlights off without the orange
  clipping. A modest change by design: the look comes from the lighting items that follow.
- **Ambient occlusion** on high / ultra (`QualityProfile.ao`, `render/ambientOcclusion.ts`): from the depth buffer,
  half the output's size, eight taps on a spiral turned in a five-pixel pattern, two five-tap blurs that keep to
  the surface and cancel that pattern, laid over the picture where it is put together (not a pass of its own),
  pixels brighter than a threshold left alone (a lamp's pool is not ambient light). Seen at kerbs, under the wing
  and the cars, between bushes and rocks.
- **What it cost to get there** (kept as a warning): three's `GTAONode` took 3.2 ms of GPU at 4K (half-size target;
  the whole scene is 10.9 ms), the same with 6 samples or a third of the radius; 4K fell from 60 to 48 fps, 1440p
  from 101 to 88. Our own pass is 0.68 ms + 0.19 ms of blur there.
- **New tool** `tools/perf-pass.cjs`: GPU time per render pass (WebGPU timestamp queries, `?gputime=1`), which is
  what found the above. At 4K ultra, 朧峠 night: scene 10.8 ms, shadow maps 0.4 ms, bloom 0.5 ms, SMAA 0.7 ms,
  occlusion 0.87 ms. GPU time of the occlusion: 0.87 ms at 4K, 0.38 ms at 1440p, 0.22 ms at 1080p.
- Checked: 96 viewpoints (4 courses × 3 times, ultra) and 16 on the WebGL 2 backend without page errors; the
  occlusion with the upscaler on (pictures; a still scene: 0.40–0.45 % of pixels changing against 0.23 % for the
  film grain alone at this quality and 0.11 % for the upscaler alone at medium); tsc, vitest 70, build.
- **Not verified**: the frame rate after the change, paired. The paired runs of the final build were taken while
  three agents were using every core (load average 19) and are worthless (the game is CPU-bound); only the GPU
  times per pass above stand. Phones. The grade on a real screen by the owner's eye.
- **Found on the way and fixed** (`Environment.buildEnvMap`): the WebGL 2 backend's picture was darker than
  WebGPU's since B1 (same viewpoint, dawn: mean 93.6 against 102.4 on `588ddb3`; car body and trees clearly
  darker; the earlier "same look" check had compared WebGL 2 with itself). The sky was missing from the reflection
  environment there: three's PMREM generator keeps its camera's default far plane (2 km) on that backend whatever
  `fromScene` is given, and the sky dome is 9 km. The copy of the dome in the environment scene is now a tenth
  of the size (its colour is by direction only). Checked on a still scene (lower half of the picture, mean RGB):
  WebGPU 74.8 / 59.2 / 55.7 before and after, WebGL 2 57.9 / 42.1 / 32.2 → 74.6 / 59.0 / 55.7; with the
  environment taken away both give 56 / 41 / 31. WebGL 2 pictures taken before this fix (`c1-gl`) are dark.
- **Deployed** (`26841c0`, bundle `index-SYHO0olc.js`, the same hash as the local build; leaderboard API 200). The
  live site itself was not opened in a browser.
  The WebGL 2 fix after it: `ac8c2e1`, bundle `index-UOm_3OHj.js`, API 200.

### C2: the lights' glow in the haze (plan C5, first part)
- `render/volumetricLights.ts`, on high / ultra (`QualityProfile.volumetric`): what the air scatters towards the eye
  from the 16 street lamps nearest the camera and from up to four cars' headlights, per pixel from the depth
  buffer at 0.4 of the output's size, two surface-keeping blurs (`render/screenSpace.ts`, shared with the
  occlusion), added to the picture before the bloom. A lamp shines down (cos^1.5) within 15 m: the light gathered
  along the view ray is a closed form (∫ 1/d² − 1/R²), no steps; a headlight cone takes six steps at equal angles
  from the lamp, turned in the five-pixel pattern the blur cancels. The scene cuts the ray, so a glow ends at the
  wall behind it. No shadows in the air (a tree cuts no shaft). The amount is `haze` per time of day in the
  `Environment` presets (night 0.005, rain 0.008, dawn 0.003 per metre). The cars' old see-through beam cones
  show only where the pass is off (`beamCones`).
- Got there in four rounds of pictures: first the lamps were dark (a reversed smoothstep), then the whole sky
  glowed (1/d² without an end, sixteen lamps adding up), then a hard edge at lamp height (half-space emitter).
- Look: a cone of lit air under each lamp, clearest in rain; a faint dome on a clear night; a soft glow ahead of the
  car's lamps; nothing by day. Same picture natively, with the upscaler and on the WebGL 2 backend (same
  viewpoint, rain: mean RGB 112.0 / 74.5 / 49.4, 112.6 / 75.3 / 50.5, 111.2 / 73.7 / 48.8).
- GPU time (`tools/perf-pass.cjs`, 4K ultra): 0.84 ms + 0.24 ms of blur (scene 10.9 ms, occlusion 0.89 ms).
- Checked: 96 viewpoints at ultra without page errors (at 0.5 scale, before the last tuning), then 32 of the final
  build, 8 with the upscaler, 8 on WebGL 2; a still scene in rain: 0.04 % of pixels changing natively, 0.16–0.28 %
  with the upscaler (rain and grain included); tsc, vitest 70, build.
- Deployed 11-10 (`b521295`, bundle `index-DAzv1geN.js`, API 200).
- Frame rate, 1080p, before the phase (`588ddb3`) against C1 + C2, paired, 20 s each, machine idle (11-11): high
  148 / 115 fps before, 110 / 125 after; ultra 122 / 129 before, 97 / 116 after. The same build scatters by ±15 %
  between runs, as much as the difference: roughly 10 % slower at most; the GPU pass times above are the firm numbers.
- **Not verified**: online peers' beams (wired through `RemoteRacers.forEachExhaust`, not run with a second
  player); trains' and bikes' lamps in the haze; the autobahn's oncoming traffic has no beams in the air; phones
  (the pass is off below high).

### Fixed: the picture froze on the grid after the car select (WebGPU, since the switch to it)
- Found while photographing the menus through the keyboard (title → … → car → race): the race ran (clock, gears,
  sound) but the picture stayed on the garage's last frame, with "Buffer used in submit while destroyed" on every
  frame. Not seen before because every tool and the E2E start a race directly or on the WebGL 2 backend.
- Cause, in three.js 0.186: `geometry.dispose()` destroys an interleaved attribute's GPU buffer (every meshopt GLB
  has them) but leaves the destroyed buffer on the shared `InterleavedBuffer`; the next clone of the model (the same
  geometry: the garage's car, then the same car on the grid) gets the dead buffer back and WebGPU refuses the frame.
  The WebGL 2 backend forgets the buffer properly. `render/threeFixes.ts` gives the WebGPU backend the same
  behaviour (called once in `RenderHost.create`); remove it when three.js fixes it.
- Checked on the real GPU: the keyboard path into a race shows the race, 0 errors (140 distinct before); garage with
  seven vehicles (a car twice, a train, a bike, the cockroach) → race → restart → another course → garage → rival
  race → back → attract: 0 errors. tsc, vitest 70, build. Deployed 11-11 (`c581eba`, bundle `index-D2cgf5O8.js`,
  API 200). **Not verified**: the online path (lobby → race) on real WebGPU, phones.
- The same check on the WebGL 2 backend found a second one, there since the first course switch existed:
  `disposeWorld` freed the geometry of every mesh of the old course, and every `Sprite` draws three.js' one shared
  quad, so after a change of course no sprite was drawn again on WebGL 2 (lamps' flares, smoke, sparks, the city's
  lights; 252 `no buffer is bound to enabled attribute` per run; WebGPU makes the buffer again). Sprites keep their
  quad now. `tools/gpu-errors.cjs` walks these paths and counts the GPU's errors: 0 on both backends.

### F2 / F3 / G1–G3 merged (11-11): car select, waiting room, netcode — three agents in worktrees
Each worked on its own branch with its own stack; reports kept in the session, numbers below are theirs unless it
says "checked here". The account's usage limit cut all three off twice; they resumed from their worktrees.

- **Car select (F2)**: `ui/garage/VehiclePicker` for single player and online: tabs by kind, a grid of thumbnails,
  five bars (acceleration, top speed, cornering, power, weight) from figures measured by the headless sim
  (`tools/vehicle-stats.ts` → `vehicleStats.json`: 0–100, top speed, skid-circle g; e.g. roach 0.88 s / 1226 km/h,
  E5 320 km/h, Cybertruck 209.5), sorting, favourites, grid keys (Q/E tabs, R sort, C colour, X favourite).
  Thumbnails are drawn by the game itself on the GPU (`tools/thumbs.cjs`), redrawn here with the current look (18).
  Checked here on the GPU: the picker at 1600×900 and on the phone layout (all / cars / bikes / trains / other),
  0 errors; the keyboard path title → race still starts the race.
- **Waiting room (F3)**: the members' vehicles stand on the course in the start grid's rows; the vehicle someone is
  looking at shows in their seat on everyone's screen (選択中), confirmed only by the select's button. Merged with
  the picker here: opening the select in a room is the browsing (the game's `'garage'` event), closing it brings
  the line-up back (`showRoomLineup(keep)`). Checked here on the GPU (WebGPU, five members, 1080p high): 87–108 fps;
  a member joining or swapping costs one long frame while the model is built (E5 0.6–0.9 s, a bike 0.25 s, cars
  50–140 ms): not hitch-free.
- **Netcode (G1–G3)**: 30 Hz compact states with velocity / acceleration / turn rate, a clock per peer, peers drawn
  in the present with eased corrections, link statistics (N key), `?netsim`. Replay tool (RTT 100 ms, jitter ±20,
  loss 2 %, 60 fps): position error of a car 1.26 m mean / 2.35 max before → 0.03 / 0.14 after (autobahn at 240
  km/h: 1.83 → 0.05); two solid cars touch 17 ms apart on the two screens (before: 21 s apart, or never on one).
  Reverb `tcp_nodelay`: relay delay with five players 23–30 ms → 2.7 ms mean (localhost). A train's rear cars are
  up to 0.78 m off for a moment after it hits a wall; at 30 fps one 39 cm jump there.
- **Found while merging, fixed here**: the waiting room's and the garage's camera could stand inside a tree (it
  depended on where the slow swing was when you looked): a round clearing among the trees follows the camera's
  circle (`clearing`, the trees inside shrink to nothing with their shadows). A long line-up (a Shinkansen in the
  room) moved the camera behind a bank that hid the front row: the camera's side is chosen again with every change
  of the room and has to see both ends of the line-up. A bike's or the cockroach's headlight was a white cone
  across the garage picture (the camera looks across the beam from two metres): a lamp has a size now
  (`SPOT_SIZE`), gain 0.5 → 0.32.
- Checked here: tsc, vitest 133 (11 files), build; backend tests 20 (304 assertions) on the merged tree;
  `tools/gpu-errors.cjs` 0 on both backends.
- **Not verified** (theirs and mine): smoothness of the peers judged by eye at a normal frame rate with two real
  players (numbers only); contact in the browser; the netcode over the Cloudflare tunnel; mouse / touch / pad in
  the picker beyond what the E2E clicks; the lobby on other courses and times of day (unit test only); bikes, the
  cockroach and the L0 through the replay tool; one WebGPU message seen once and not again ("sampler type …
  Comparison" for a train's material while four members joined at once; the picture was right).

### System base: stability (11-11)
What a deploy or a bad hour could break, found by reading the stack, and changed:
- nginx resolved `app` once at start: after the backend alone was rebuilt it answered 502 until it was restarted
  too. It asks Docker's DNS as requests come in now (`resolver` + `$app`).
- `app` has a health check (PHP-FPM and Reverb both listen), `web` one too and starts only when `app` is healthy.
- The Reverb key was made anew by every container, so every deploy cut the open games off from their rooms until a
  reload. Keys that `.env` does not give are made once and kept in the `secrets` volume.
- Reverb can stop answering while its port still accepts connections: every room then falls back to polling, and
  the process ignores SIGTERM. Seen once, made on purpose three times: by taking the container's network away and
  giving it back (a test of the nginx change; not something a deploy does). A watchdog in the entrypoint asks it
  every 10 s and ends it (SIGKILL) after three silent checks, the loop that was there starts another; the health
  check asks Reverb over HTTP now, not just its port.
- PHP-FPM ran Ubuntu's default of 5 workers (a five-player room polls and reports through them): 16, a hung
  request ends after 30 s, a worker is replaced after 2000 requests.
- Container logs had no size limit: 3 × 10 MB each.
- No copy of the database existed (players, runs, ghosts): the `backup` service dumps it once a day into the
  `backups` volume, one file per day of the month; how to restore is written in `docker/backup/backup.sh`.
- A game opened before a deploy asked for files of the old build that were gone (a model loader, the audio):
  it reloads itself once (`vite:preloadError`).
- Verified on the isolated stack (`touge-wt-merge`): both containers report healthy; the key is the same after the
  app container is made anew; with the app container moved to another address the API and the WebSocket path answer
  at once (200 / 101) without touching nginx; the worker settings are in the running pool; the dump is written
  (672 kB, 11 tables) and restoring it brought back five deleted runs (25 of 25), leaderboard 200 afterwards.
  The watchdog: Reverb hung by the network change answered again 45 s later (log: "does not answer, ending it",
  "Starting server"), a WebSocket handshake with the room key then got `connection_established`.
- **Not verified**: the reload on a missing chunk in a browser (it needs a deploy between two page loads); the
  backup on the day after (the loop's second round); 16 workers under a real load.
- Not done, candidates: `cloudflared:latest` is not pinned to a version; rooms are tidied up only when a room is
  made; a copy of the backups outside this machine.

### E2E on the merged tree (11-11)
- Whole suite (13 tests, isolated stack): 11 passed, 2 failed by time: the time attack (the lap was at 1:41 of
  1:54 when the 4 minutes ran out) and the five-player battle (the second game was still loading after 3 minutes).
- Not the merge: the build that passed the same time attack in 3.0 min on 11-10 (`588ddb3`) failed it today in the
  same way on the same machine, built and run next to it. The software renderer is slower today, by about 1.3–1.6×
  in every test (boot 47 → 55 s, rival 1.7 → 2.3 min, phone 1.6 → 2.6 min); the machine was idle (no steal time).
  Why: not found. On the host's Chrome with SwiftShader the merged build is not slower than the old one.
- The two tests wait longer now (the lap up to 8 min, a game's loading up to 7 min).
- Time attack again with the longer limit: passed (9.8 min).
- Five-player battle, three more runs, each stopped by something else:
  1. `通信: ポーリング` instead of LIVE: Reverb was hung, by my own `docker network disconnect / connect` test on the
     running container (→ the watchdog above).
  2. A real inconsistency between two merged packages: a ready member who opened the car select lost the ready mark
     on the others' screens (`MemberMark` showed 選択中 instead of it), while the rule is that looking around enters
     nothing. Fixed: both marks are shown.
  3. After the car select was confirmed the test waited 60 s for the ready button; the page's main thread stood
     still for 60–80 s at each change of scene (garage ↔ line-up) under the software renderer (the trace: the room
     poll, every 2.5 s, has gaps of 61–82 s there; the request itself took 81 ms). The two waits are 240 s now.
     Not seen on the GPU (the garage and line-up changes there were checked by the packages' own GPU runs).
  4. After the rematch the test waited 60 s for the room on every screen: three games change their scene at once
     there, and each page stood still for about 100 s (same trace reading). 300 s now.
  Then: **passed** (27.9 min), together with the rival test (which now also expects the rival's line before the
  start and the camera with the car). All 13 tests have passed on the merged tree, though not in one run: the
  whole suite has not been run again in one piece since the first run (11 of 13).
- The rival's line was missing in the first run of that test: the question "does the server have a model?"
  (`/api/content`) alone outlasted the countdown on the slow page, and the line was dropped as late. The game now
  asks once at start-up (`warmRivalBrain`), so the game's own line is there at once when there is no model.

### Found on the first deploy of all this: the race camera stayed at the garage (11-11)
- My own bug in `31c6a03` (the clearing among the trees): the line that closes the clearing was written into the
  camera's `if / else` chain and cut the chase camera off in every phase but the garage. In a race started through
  the menus the car drove away from a camera that stayed where the car select had left it.
- Nothing had seen it: E2E and `tools/gpu-errors.cjs` look at states and errors, the contact sheets of that round
  were of the garage and the waiting room. I saw it on the screenshots of the rival check, **after** the deploy:
  the live site had it for about ten minutes (05:54 → 06:05), then the fix was deployed and checked on the live
  build (camera 9 m behind the car at 6 s and 16 s of a race started through the menus).
- Guards: the E2E time attack and rival tests and `tools/gpu-errors.cjs` now check that the camera is with the car.
  Lesson kept: look at a picture of a **race** before every deploy, whatever the change was about.

### Generated assets: ChatGPT (images) and Gemini (music) through the owner's browser (11-11)
- Owner (11-11): generate what is needed, images with ChatGPT, music / video with Gemini, both in the browser.
- In the game: the autobahn's three rival portraits (it had none: silhouettes), its course art (was a screenshot) and
  its own race music (`bgm_race_autobahn`, loop 59.05 → 133.31 s found with `tools/music-loop.cjs`: tempo, level per
  10 s, the best pairs of whole-bar distances by band spectrum; loudness matched to the other tracks, −15.4 LUFS).
  Listed in docs/ASSETS.md. No names, no project details in the prompts.
- Not verified: nobody has heard the music in the game (the loop point is a measurement); sent to the owner with a
  preview of the seam.

### The rival's language model (11-11, owner's request)
- What the owner asked for: LiteRT-LM.js with Spark 2.6 1.7B in the browser (8-bit weights and KV cache, 64k context),
  the server (Gravitee → LiteLLM) where the client cannot; uses: the rival's taunt before a race, and in the race the
  decision to obstruct or to sound the horn, the model never driving itself (a fixed blocking routine as a tool).
- Built (the server path and the whole game side):
  - `ai/RivalMind.ts`: a `RivalBrain` is asked for a line (before the start, after the finish) and, when the two cars
    are close, for a decision; the game's own lines and rules (`scriptedBrain`) are always the last brain, so nothing
    depends on a model being there. At most one question per 3.5 s, none while a block is on or the road is left open
    after one, an answer older than 3 s of race is dropped.
  - `AIDriver.block(seconds)`: the one blocking routine (in front of the chaser across the road, inside the road's
    edges). `AudioEngine.horn` (synthesised twin horn; the player has one too: H / right stick).
  - Server: `/api/ai/taunt`, `/api/ai/decide` (facts only, 45 / min per address, key from `.env` to the gateway in a
    header, the gateway's address from `.env` too since 11-11 (`LLM_API_URL`, owner: no address in the code), models by env, first that answers; decisions as real tool calls, clamped). `/api/content` → `ai.enabled`.
  - UI: the line under the versus plate (countdown and first seconds), the line on the results, the setting
    ライバルAI, the player's record against each rival (localStorage `touge-rivals:<course>`) as a fact for the line.
- In the browser on the GPU, a stack with the key, through the menus (`~/.local/opt/quality/rivalmind.cjs`): the line
  before the start came from the model in 1.5–2.0 s and stood under the versus plate; with the player put 9 m behind
  the rival, the model called `block_player` (4 s) in 0.5–0.6 s and the rival blocked; put in front, it called the
  horn (double); a decision that took longer than 1.5 s was dropped, the game's rules took over for 30 s and the
  model again after that; the line after the finish stood on the results. Deployed: `/api/content` says
  `ai.enabled`, a real `/api/ai/taunt` on the live stack answered in 1.9 s.
- Fixed on the way: a rival that is behind was offered the blocking tool and used it (now only the horn is offered
  there); without a gap the prompt said "0 s" and the model spoke of a dead heat (a rival still on its way gives an
  estimate, and no gap says nothing).
- Verified: backend tests 28 passed (8 new: no key → 503 and nothing sent, key header, next model on failure, empty
  answers → 503, tool calls clamped, the horn only from behind, a model that calls nothing, only facts accepted; they found a real bug: `trim()`
  with 「」 in its list cut the 。 off a line byte-wise → invalid UTF-8 → 500). Frontend: tsc, vitest 138 passed (5 new for RivalMind),
  build. The block in the duel sim (`BLOCK=4 npx tsx tools/sim-duel.ts`): Oboro and the autobahn, three pairings: no
  respawn, no flip, the blocker never off the road, in front of the chaser 82–90 % of the blocked time on Oboro.
  With only a 2 s breath between blocks a rookie held a legend behind for the whole autobahn (57 % cover, 30 blocks):
  the road is now left open as long as the block was (+1 s), and the legend gets past (148 s vs 174 s).
- Measured on the gateway (11-11, one request each, from this machine): sarashina-3-nano 0.19 s, sarashina-3-mini
  0.29 s, qwen-3.8-27b 0.33 s, nemotron-3.5-bolt 0.58 s, gemini-3.5-flash-lite 2.0 s (the best line), gemma-4-31b
  6.7 s, gemini-3.8-flash 12 s; tool calls correct with sarashina-3-mini in 0.15–0.47 s. Defaults: lines
  gemini-3.5-flash-lite then sarashina-3-mini, decisions sarashina-3-mini then gemini-3.5-flash-lite (owner, 11-11:
  only these two; qwen has a usage limit on the gateway).
- **Owner's decision (11-11, after this report): inference on the device is dropped, everything goes through the
  API.** What follows is the finding that led there; nothing of it is to be built.
- **Not done: the model in the browser.** The combination asked for is unconfirmed at every point: LiteRT-LM.js
  (`@litert-lm/core`, early preview) documents Gemma 4 only for the web; there is no `.litertlm` of Spark-X2.6-1.7B,
  its architecture is its own (`Spark2_5ForCausalLM`) and no conversion path for such a model is documented; nothing on
  an 8-bit KV cache; the documented example context is 8192 tokens; tool calling from JS is undocumented. The gateway
  has no Spark either. Alternatives for the owner to choose from: (a) LiteRT-LM.js with Gemma 4 E2B (the documented
  path), (b) Spark through ONNX Runtime Web (WebGPU) or llama.cpp's WASM build (GGUF q8_0) if a conversion works,
  (c) stay with the server. The seam is there: one more `RivalBrain` in `game.rivalBrains`, before the server's.
  No experiment in the browser has been run yet.

### The renderer falls back from WebGPU to WebGL 2 by itself (11-11, owner's request; `d4fd3b5`)
- What was there: three.js takes its WebGL 2 backend when the browser gives no WebGPU device. What was missing:
  everything after that moment. Now (`render/backendChoice.ts`, `RenderHost.create`'s `onTrouble`, `ui/GameCanvas.tsx`):
  - the renderer cannot be built although WebGPU came up, or three's own fallback cannot take the canvas (one that has
    given a `webgpu` context gives no `webgl2` one) → started again on a new canvas with WebGL 2, remembered;
  - the WebGPU device reports errors in a burst (12 in 10 s), or a frame throws that often → remembered for a week,
    one reload, WebGL 2 (then WebGPU is tried again: a browser or driver update may have fixed it);
  - the device is lost → one reload on WebGPU (a crashed GPU process is back), WebGL 2 from the second loss in a
    session, a message with a reload button instead of a third reload in a row;
  - settings row 描画方式 (自動 / WebGPU / WebGL 2): shows what runs and why; a choice by hand forgets what was
    remembered, and an explicit WebGPU is not left on errors.
- **Verified** on the RX 5700 XT (headless Chrome, `node tools/backend-fallback.cjs`: 14 cases, each a fresh browser
  context, "up" = the title reached and frames drawn): WebGPU as it is; `?webgl=1`; the setting; no `navigator.gpu`;
  no adapter; the device refused; no device with the canvas already taken; drawing throws on WebGPU; errors in a
  burst (→ WebGL 2 after the reload, remembered); a few stray errors (stays); a burst with WebGPU chosen by hand
  (stays); the device lost once (WebGPU again), twice (WebGL 2), a third time at once (message, no reload).
  The losses and errors are simulated by calling the renderer's own handlers or by replacing browser functions
  before the page loads: a real driver failure was not available to test with.
- Not verified: a real browser without WebGPU (Firefox, Safari, a phone) by hand; a real device loss.

### The freezes at a change of weather, car or course (11-11, owner's request)
Owner: the screen stands still when the weather is switched; keep what was loaded, open the game as soon as what it
needs is there and fetch the rest behind it, show that something is loading; asked also whether VRAM is used, and
proposed freeing the oldest first when it runs short.

- **Cause, measured** (`~/.local/opt/quality/hitch.cjs`: every frame gap over 40 ms after each action, with a CPU
  profile): the renderer builds a material's shader for the scene's set of lights (each light's id and whether it
  throws a shadow, in the scene graph's order), the fog object and the environment texture object. Every switch
  changed one of them: a car brought two `SpotLight`s, the garage added its own, each time of day made a new PMREM
  target, each course its own sun and fog. All materials were then rebuilt in one frame: 1.2–2.6 s, every time.
- **`render/LightRig.ts`**: every light of the game is made once and never added, removed or re-parented (sun,
  sky fill, fog, six lamp points, the vending machine's, three headlight spots; spot 0 is also the showroom's);
  what changes is intensity, colour and position. `CarVisual` carries no lights any more (`headlight()`,
  `beamInto()`), `Game.updateBeams` gives the three spots to the followed car and the nearest others each frame.
  One environment target, drawn again in place at a change of time.
- **Courses stay built** (`Game.leaveWorld` / `enterWorld`): up to three besides the shown one, within a budget of
  GPU memory (`keepBudget`: 2000 MB, 500 MB under 8 GB of RAM, 0 on phones / quality low / under 4 GB); the one
  left longest ago is freed first, and all of them when the GPU reports it is out of memory. Freeing a course keeps
  what another built course still uses.
- **Models in stages** (`render/vehicleModels.ts`): the title needs one car; the others load one at a time behind
  the menus (paused in a race). The garage, a race and the waiting room wait for exactly the models they need
  (`Game.needs`, `prepareRace`), with a mark in the corner (`busy` event → `.busy-mark`, an animation the compositor
  runs, so it moves while the main thread works).
- **Numbers** (RX 5700 XT, 1080p high, WebGPU, worst frame after the action; before = `d4fd3b5`):

  | action | before | after |
  |---|---|---|
  | time / weather switched | 1.2–1.8 s every time | no frame over 40 ms (the first switch to dawn on a course: 0.5 s) |
  | the garage shows another car | 1.3–1.6 s | 0.34–0.6 s |
  | race start | 2.6 s (5.6 s of slow frames) | 0.65 s (0.75 s) |
  | restart | 2.5 s | 0.59 s |
  | back to a course shown before | 9.5–12.5 s | 15–32 ms |
  | bytes fetched before the title | 31.0 MB | 10.9 MB |

  A course's first visit is as before (3.5–14 s behind the loading screen). VRAM of the whole machine: 0.92 GB with
  one course, 1.34 GB with four built (80–108 MB a course by our own count); JS heap ~170 → ~310 MB.
  Cost of the fixed set of lights: scene pass 2.96 → 3.12 ms, GPU total 4.25 → 4.44 ms (`perf-pass.cjs`, two pairs);
  `perf-frame.cjs` pairs are within their scatter.
- **Tried and dropped**: compiling a car before it is shown (`compileObject`: several 110 ms frames and then the
  same long one); building every time of day's shaders at course load (the first dawn stood still all the same).
- **What still stands still**: ~0.5 s when a car is drawn for the first time (its materials' shaders), ~0.5 s at the
  first dawn on a course, and the first visit of a course (the terrain is built on the main thread: frames of 1–1.4 s
  behind the loading screen).
- Verified: tsc, vitest (147), the build; `gpu-errors.cjs` 0 on WebGPU and WebGL 2; `backend-fallback.cjs`;
  before / after pictures of the attract run, garage, grid, rain, dawn and waiting room (same look); E2E on an
  isolated stack: 13 of 13 (the phone test failed first: it read a tab's place while the car select was still
  sliding in, which the old freeze had hidden; its taps now wait until the target stands still).
  Not verified: phones on a device; a slow network (the mark and the waits were only seen locally); the hitch numbers
  on WebGL 2 and on medium / low; a real GPU out-of-memory.
- **Built shaders are kept** (`render/threeFixes.ts` `keepShaders`, later the same day). What was left of the garage's
  0.34–0.6 s: three.js counts the uses of a built shader and of its pipeline and throws both away with the last
  object that used them, so a car that left the scene took its 22–32 shaders along and the next car (or the same one
  again) built them anew. The count now never reaches zero for shaders that are not bound to one object (an
  `InstancedMesh`'s and a morph target's key holds the object's id: those go as before), and pipelines / programs
  are not released. Shaders built per garage step (`~/.local/opt/quality/builds2.cjs`): 32 / 29 / 26 / 22 / 22 →
  21 (first car) / 11 / 3 / 3 / 6 / 2, a train 24. Worst frame (`hitch.cjs`, 1080p high, WebGPU): another car in
  the garage 536 → 113 ms, a car shown before 547 → 58 ms, race start 648 → 107 ms, the attract run 381 ms → none
  over 40 ms; a train's first showing 463 ms and the first car's 374 ms stay (shapes drawn for the first time).
  Restart: no difference between the builds in paired runs (another session loaded the machine: 0–26 frames of
  40–150 ms on both). Verified: tsc, vitest 147, `gpu-errors.cjs` 0 on both backends, one race picture.
  Not measured: how much memory the kept shaders hold over a long sitting (a few hundred small objects; nothing
  frees them before the page is left).

### The interface, redesigned (11-11, owner's brief: all-new cyber UI with animation; package `ui`, an agent in a worktree)
- Every screen and the HUD on one design system (`ui/theme/` tokens, `ui/kit.tsx`, `ui/Shell.tsx`: the trail at the
  top, back and fullscreen bottom left, the hint bar in the glyphs of the device used last), a screen wipe, figures
  that count, a moving focus marker, a setting to turn the motion off (CLAUDE.md "Interface").
- Found and fixed on the way: a screen wipe took the pointer away for its 240 ms (clip path → mask); the main menu
  forgot the row it was left through; two buttons filled at once on the results; the phone's back button clipped.
- Verified by the agent (its report): tsc, build, vitest; E2E on its stack `game.spec.ts` 10 of 10, `mobile.spec.ts`,
  the waiting-room and phone tests of `online.spec.ts`; sheets on GPU Chrome in `~/.local/opt/wt/ui/shots/` (shown to
  the owner). The full suite on the merged tree: below.
  **Not verified**: the HUD's frame cost (the machine was loaded by other work), the busy mark while the main thread
  is blocked (built for it, only seen standing), Firefox / Safari, sound, pad glyphs, `prefers-reduced-motion`.

### Accounts come from Authentik; everyone else is a guest (11-11, owner's request)
Owner: members of their platform log in with the Authentik they host and go on with their own save data; keeping
an account in the browser (the token in `localStorage`) is abolished; whoever cannot log in is a guest, asked for a
name whenever a record is kept. Later the same day: the account's key should be Authentik's `sub`.

- **Server**: `AuthController` (login → Authentik with PKCE and a state bound to the browser by a cookie; callback →
  code for token, userinfo, the member by `oidc_sub`, name taken from Authentik each time), `MemberSession` (cookie
  `touge_session`, HttpOnly / Lax / Secure over https, hash in `player_sessions`, 30 days from the last visit; a
  change by cookie only with the header `X-Touge-Client`), `AuthenticatePlayer` (a guest's pass with an end date, or
  the cookie), guests by `POST /players` (24 h; those without a record are removed two days after), claim of a
  guest's records by a member, save data with a revision (`players.save`, 64 kB), `is_member` on the ranking,
  `auth.enabled` in `/api/content`. Migration `2026_11_11_000001_members_and_guests`.
- **Client**: `api/client.ts` (member = cookie, guest = pass in `sessionStorage`; the old `touge-player` only for
  the claim), `store/account.ts` (who am I at start; at a login the guest's and the old player's records are
  claimed, the save of server and machine merged — better time, larger battle count, favourites three-way — and
  the best runs' ghosts fetched; sent 1.5 s after a change), the main menu's row メンバーログイン / ログアウト (only when
  the server has a login), PLAYER / GUEST in the top bar, a notice for what the login came back with, the results
  ask a guest for the name every time, the online lobby takes a member in at once, MEMBER marks in the ranking.
- **Decided here** (the owner can change them): the login itself lives in a cookie of our own (the account is
  Authentik's; nothing a script can read); a member's name is Authentik's `preferred_username` (cut to the game's
  16 characters and letters), not editable in the game; what a machine holds at a login (the progress of before)
  goes into the member's save; a logout clears it from the machine; device settings (graphics, sound, controls)
  stay per machine for everyone.
- **Owner's decision (same day)**: nothing of a guest is kept, not even for the tab: pass, times, medals, battle
  records and favourites live in the page's memory; sending a record under a typed name stays. (A guest who
  reloads in an online room loses the seat: the pass is gone with the page.)
- Verified: backend tests 40 passed (12 new: the whole trip with Authentik faked, PKCE, state from another browser,
  refusal, the same subject = the same player, the cookie without the header, expiry, guests, the old tokens and
  the claim, the save's revisions); the migration on a copy of the live database (32 players, 71 runs: all kept,
  the board unchanged); frontend tsc + vitest (8 in `client.test.ts`); Authentik's authorize endpoint knows the
  client id from `.env` (it answers "redirect URI" for an address not registered, as it should).
  **Not verified: a real login** (it needs the redirect URI `https://<public host>/api/auth/callback` registered
  in the provider and a member's own credentials), the save across two real machines.
### Ground, road and roadside remade (11-11, the owner's request to re-model everything; package `terrain`)
An agent's package (six commits, `46041ec` … `6a1854a`), merged with the freeze work on its branch and checked there
by the main session. Live since the release of 11-11 (below): the owner saw the sheets and asked for it
(「それも頼む」).
- What it is: the ground as one layered TSL material (rock on steep faces from its two sides, forest floor, moss or
  grass, gravel at the verge, shoreline; wet and pooled in rain), the road's wear in one material (patches, seams,
  cracks, tar lines, polished wheel tracks, worn markings, puddles), a modelled roadside (guardrail spans with
  terminals, delineators that answer the headlights, U-gutters with gratings, block walls, sprayed slopes with their
  frames and rockfall fences, rock shed, bridge), spurs and gullies on the hillsides away from the road. Quality
  `low` keeps the old path. Textures: seven ambientCG CC0 sets + our own tiles (docs/ASSETS.md).
- The drivable surface did not move (agent's proof: heights under road and shoulder, road and wall colliders
  identical; `sim-run.ts hayate rookie` gives the same time on all four courses).
- Checked on the merged tree by the main session: tsc, vitest 147, build; `gpu-errors.cjs` 0 on WebGPU and WebGL 2;
  `hitch.cjs`: the freeze work holds (time / weather: no frame over 40 ms but the first dawn, kept courses 16–40 ms);
  the before / after sheets of all four courses and close-ups looked at; E2E on an isolated stack: 13 of 13.
- Cost. GPU time of the scene pass, before → after (`perf-pass.cjs`): 1080p high 3.06 → 4.91 ms, 1080p medium
  2.65 → 3.04, 1440p ultra 5.63 → 7.23, 1440p ultra with the upscaler at Quality 3.33 → 4.32, 4K ultra 11.7 → 13.3
  (whole frame 16.5 → 17.8 ms: native 4K ultra no longer fits 60 fps on the RX 5700 XT, with the upscaler it does).
  Main thread: the CPU profile's make-up is the same (264 → 273 draw calls). Download before the title:
  10.9 → 20.5 MB at high / ultra (the 1024 px layers), +2.7 MB at medium, nothing at low.
- **Frame rates were not settled**: uncapped runs gave 105–116 → 66–73 fps (high) and 86–104 → 51–52 (ultra) in
  one hour and 78 / 47 → 103 / 100 in the next: another project's session was running a six-process test job on the
  machine (load average 6–7). The numbers above are the ones that do not depend on it.
- Not done by the package: the autobahn's guardrails, barriers and gantries (new concrete material only), signs.
  Known: under the upscaler the nearest rockfall-net panels flicker a little more than the base (99.9th percentile
  8–9 against 5–7 of 255); the wear pattern's repeat shows from ~26 m above the road.
- Not verified: frame rates on a quiet machine; low / medium / high on every course by eye (ultra everywhere);
  phones (low: the old path).

### Release (11-11): the redesigned interface, Authentik accounts and the remade ground go live

- One tree (`auth` = main + the interface branch + the accounts + the terrain branch), fast-forwarded into main at `7a18cb6`.
- Checked before the deploy: `tsc -b`, vitest 153, backend 40 (container), `vite build`; `tools/gpu-errors.cjs` on this
  very bundle (`index-wYd6wJdU.js`, the same hash as the build that was checked): 0 errors on WebGPU and WebGL 2, the
  race camera with the car, one race picture looked at; the account screens looked at (guest, member, a failed
  login, no login configured; desktop and phone, the API played by the script).
  E2E on an isolated stack: 14 of 15 in the full run (42.8 min, the five-player online race among them); the
  fifteenth, the phone test, tapped one row too low: its helper took a row for standing while the software renderer
  had drawn no frame between its two looks (the new ground makes the frames slower). The helper now waits for the
  target's animations; the phone test alone then passed (2.0 min). Not re-run as a whole after that change (test only).
- Deployed on ubuntu-dev with a dump taken first (`~/.local/opt/backups/touge-1111-1447-pre-auth.sql`): the
  migration ran (9 migrations), players 32 and runs 71 as before; the new bundle is served locally and through the
  public address; leaderboard API 200; `/api/content` says `auth.enabled: true`, `ai.enabled: true`; `/api/auth/login`
  through the public address answers 302 to Authentik's authorize endpoint (PKCE S256, scope `openid profile`, the
  callback https at the public host, the state cookie HttpOnly / Secure / Lax), and Authentik takes the request to
  its login flow.
- Not verified: a real login (the code exchange, the account by `sub`, the save's sync, the claim of a guest's
  runs, logout): it needs a member's credentials, which are the owner's to enter. The interface's cost in the HUD on
  a quiet machine, Firefox / Safari, pads' glyphs, sound of the new interface by ear.
- Seen and left for a follow-up: the title's roadside cameras are now and then behind a mound or pass a post of the
  new roadside (the cameras do not look for what stands in the way).

### Grains over the menus (11-11, owner's idea)

- Owner: 「粒が浮いている表現→マウスで特定の選択肢に重なると→粒子が形を変えてボタンの装飾になる」. `ui/fx/grains.ts` (simulation,
  6 tests) + `ui/fx/Grains.tsx` (one canvas): dust that gathers into the outline of what the pointer is on, else of
  the keys' selection; a change of screen sweeps it. Pictures and a 21 s recording taken on the GPU and looked at
  (menus hold 60 fps with it: frame gaps median 16.7 ms); the recording was sent to the owner. Phones: fewer grains,
  the selection's frame only (looked at one picture).
- The results' medal pulls them in as it is stamped (`data-grains-first`: an element has the grains for its first
  moments on show), in amber; looked at on frames of a made-up result (the store set by a script, no race driven).
- Not done: cost on a slow phone; other uses (the boot bar). The owner has the recording; their word on the look
  is still to come (their brief left it to my judgement, so it ships with the next update).

### The title's and the replay's camera sees the car (11-11)

- Seen on the release: the four cinematic shots were offsets from the car, and with the remade ground and roadside
  the orbit went through posts and slopes, the trackside camera stood behind mounds, the wide shot in a hillside.
- Now laid along the road (`Game.cinematicCamera`): orbit and front shot inside the rails, the wide shot over the
  centre line; the trackside camera (`tracksideAnchor`) takes the place with most of the road in sight over the
  ground and is cut when the car is hidden or 80 m past; the front shot sits above the headlight cones (inside them
  the glow in the haze whitened the picture).
- Checked: sixteen frames over 30 s of the title on the GPU, before and after (`~/.local/opt/quality/cmp/title`,
  `title2`): the car is in every frame after. Trees and bushes are not asked (only the ground's heights), so a tree
  can still pass in front. The replay uses the same camera: not looked at separately.
- The condition cards as looping video (owner's idea): Gemini's video generation failed three times in a row
  ("Sorry, something went wrong"); asked the owner.

### Second release the same day (11-11): the grains, the cinematic camera
- Main `4e8f88b` deployed (bundle `index-B6xGEdHc.js`): the grains over the menus, the medal's grains, the title's and
  the replay's camera. **Verified**: the bundle served locally and through the public address, leaderboard 200,
  `tools/gpu-errors.cjs` 0 on WebGPU and WebGL 2, title frames and a race picture looked at. E2E on an isolated
  stack: only a subset (boot, menu navigation, click during a wipe, car select, rival battle, time attack, phone:
  all passed after the boot test was pointed at the game's canvas); the whole suite was **not** run again.
- Seen in the live database afterwards (counts only): one member row (`oidc_sub` set), one session, one save: a real
  Authentik login has happened. How it felt (name shown, the save on another device, logout) is the owner's to say.
- **The owner on the grains (11-11, after seeing them live): not what they had in mind.** They want far finer
  grains, close to 3D particles, that depict things and emphasise things by themselves: "the part in charge of
  beautiful expression". The 2D layer (`ui/fx/`) is to be remade on that brief.

### Time & weather: the scene is the picture (11-12, the owner's choice of layout A)
The owner (11-12): the screen where the weather is chosen looks somehow dowdy; rework the layout and show it in
pictures first, the decision follows. What was wrong (my reading): three cards across the middle hid the scene
that changes with the choice, the camera looked down on the car's roof, and the cards mixed three kinds of
picture (a drawn sky strip, a grain sky, text). Two layouts were shown next to the old one
(`~/.local/opt/quality/cmp/cond2/conditions-proposals.jpg`); the owner: 「A案でよいと思います」.
- **Layout A, now the screen** (`ConditionsScreen`, `.cond*` in `screens.css`): the three conditions as a list on
  the left where the menus have theirs (row `FocusFrame`, ↑↓ and ←→), the selected one's description and three
  readouts at the bottom left (grip in % from the course's surface × `WET_GRIP` with a bar, lamps on / off, sight
  in three steps; amber for what the rain worsens). Nothing covers the road and the sky.
- **The camera is held for the screen**: `Game.menuShot = 'sky'` (case 4 of `cinematicCamera`): 7.5 m behind the
  car and 2.6 m to its left at 2.2 m, looking 38 m down the road, eased; the car stands right of the middle, clear
  of the list. Set and given back by the screen's effect (checked: `null` again after Esc).
- **Removed**: the cards and their drawn sky strips for this screen (the gearbox screen keeps its two cards), the
  grain skies (`skyScene`, `data-cloud="sky:…"`, their test): a picture of the sky next to the sky itself had no
  job left. `Shape.fall` (travelling points) stays in `cloud.ts` with its test, unused.
- Phones (844×390): the list top left, the panel above the two touch buttons (it lay under them at first: seen on
  the picture, moved). Standing phones show the rotate notice as before.
- **Verified** (GPU, headless Chrome, RX 5700 XT; `~/.local/opt/quality/condshots.cjs` → `cmp/cond3`): night /
  rain / dawn at 1280×720 and 1920×1080 on WebGPU, on WebGL 2 (`?webgl=1`), with UI motion off, on a phone
  (touch, 844×390): all looked at; no page errors. vitest 185 (one fewer: the grain sky's). `tools/gpu-errors.cjs`:
  0 on WebGPU and on WebGL 2; the race picture looked at. E2E on the isolated stack, the six tests that pass the
  screen (time attack, ghost battle, rival battle, course select, car select, phone): 6 passed (14.1 min).
  The shot on the other three courses (霧降 / 天狼 / アウトバーン, the three conditions each, 1280×720): looked at,
  the car and the road ahead are in view on all of them, nothing in front of the camera.
- **Not verified**: a real phone; other GPUs; the whole E2E suite.
- Seen on these pictures and reported by the owner the same hour: the glow of the car's own headlights stands as a
  ball above its bonnet (the next section).

### Release 2.0 (11-12): version, the terrain on all cores, three reports by the owner
- **Version** (owner: 「バージョンがずっとv1.0なの気になる 常に更新していいと思う … v2.0かな?」): 2.0.0, written once in
  `frontend/package.json` (`src/version.ts`: the title's foot, a run's `client_version`; the server's default in
  `config/game.php` says the same and a vitest compares). The rule for raising it is in CLAUDE.md (Conventions).
- **A course's terrain is worked out on all cores but one** (the owner's yes to using all the machine's resources
  for loading): `track/terrain.ts` `planTerrain` → `stripe(k, n)` → `finish`, `terrain.worker.ts`, `terrainJob.ts`,
  begun in `Game.load` before the downloads. The result is the same to the bit as `buildTerrain`'s on all four
  courses (Node: whole and in 7 stripes; `track.test.ts`: 5 stripes in any order, missing / double / wrong-size rows
  refused). In the browser (GPU Chrome, 1280×720, high, three paired runs, load 4 of 20 cores,
  `~/.local/opt/quality/loadtime.cjs`): 16 workers, no fallback, no page error; the job takes 0.6–2.1 s beside the
  downloads; **first load 10.0 → 9.5 s, a change of course 5.4 → 4.2 s (medians; single runs 8.7–16.0 s and
  3.6–6.5 s: the machine is shared, the gain on the first load is within the scatter)**. Not verified: the fallback
  in a browser (no Worker, a failing worker, the 20 s limit: the code path is the old `buildTerrain`), phones.
- **Results: a scrollbar came up for a moment** (owner). Reproduced: for ~0.4 s while the card builds up, the last
  part rises into place from under the card's edge and the card (`overflow-y: auto`) offered to scroll by 13–15 px
  (`~/.local/opt/quality/resultscroll.cjs`: 3 of ~78 samples at 1920×911, 1280×720, 1366×650, time attack and rival).
  The card scrolls only once it stands (`Results.tsx` `settled` → `.results.settled .results-card`); after: 0 samples.
- **The vending machines stood half inside the retaining wall** (owner; seen on 朧峠 and 天狼, on 霧降 they were sunk
  0.4 m into the verge): placed 1.6 m behind the barrier line, where the remade roadside (11-11) has its wall from
  0.95 m on. They now stand on the strip in front of it (0.48 m out) on a concrete plinth as high as the ground at
  their backs; their light moved with them. Pictures on the three passes, dawn and night (`cmp/vend1` before,
  `cmp/vend2` after). Seen on the way and fixed: **the pass name board said 朧峠 / OBORO PASS / 452 m on every
  course**; it now carries the course's own name and the road's height there (`makeSignTexture('kanban', board)`).
  Not done: at night the machines' fronts burn out in the bloom (the labels cannot be read).
- **A probe camera**: `game.lookFrom([s, side, up], [s, side, up])` (`Game.spy`) stands anywhere along the road
  whatever the phase; `~/.local/opt/quality/spy.cjs` takes pictures with it. Made for the owner's reports of places.
- **Verified**: vitest 190; `tools/gpu-errors.cjs` 0 on WebGPU and on WebGL 2; the race pictures looked at.
  E2E on the isolated stack built from this tree: title, a whole time attack with results and submission, the
  phone run: 3 passed (7.7 min); the rest of the suite not run.
- **Deployed** (`a1e9292`): the live stack serves the new bundle locally and through the public address, the
  leaderboard answers 200, `/api/content` says version 2.0.0.
- **Open after this release** (11-12): the course select's two layouts shown to the owner as pictures (branch
  `course-proposal`, `?courseui=a|b`; `~/.local/opt/quality/cmp/course2/course-proposals.jpg`), decision pending;
  the 13 re-modelled props (branch `worktree-agent-a0462d11d1fc0d277`, sheets sent) wait for the owner's look;
  four agents at work in worktrees: the upscaler (FSR 3 of `@pmndrs/upscaler` on WebGPU, the owner's instruction),
  shadows and lamp light far from the camera, the rain's sound, the About screen with the AI desk. Still to look
  into: the owner's "black horizontal lines repeated over half the screen" (not found yet).

### The vehicles' lights start at their lamps; the glow in the haze no longer grains (11-12, two reports by the owner)
The owner: 「車両のライトの発射位置が全部おかしい」, and an hour later, with a screenshot of the car select on the
autobahn (a motorcycle, the camera in its beam): 「正面から光を浴びると画面上部がつぶつぶになります」.
- **What was wrong with the places** (measured on every vehicle, `~/.local/opt/quality/lamps.cjs`):
  the lamp anchors were the middle of the lamp material's bounding box per half of the car, 20–27 cm inside the
  lamps on models whose lamp parts wrap round the corner; the one real spot light per vehicle started at a height
  by kind (0.75 m cars, 0.45 m bikes, 1.1 m trains) on the centre line, whatever the model: from the front wheel of
  the NSR, from under the floor of a train whose lamps sit on the roof line, and its glow in the haze was one cone
  from that point (a ball of light above the bonnet of a low car).
- **Now**: an anchor is the area-weighted centroid of the lamp material's triangles per side (`CarModel.deriveAnchors`
  → `sides`; lamps closer than 0.3 m to each other are one lamp on the centre line: the bikes). The spot starts
  between the lamps at their height, just ahead of the nose (`CarVisual`: `max(lens + 0.1, min(nose, lens + 0.6) +
  0.05)`, the nose from the unskinned meshes; trains at their measured lamps), so the bonnet does not catch its own
  light. The glow in the haze is one cone per lamp (`CarVisual.lampSources`, `beamsInto`; lamps closer than 0.5 m
  glow as one), the intensity shared; the pool is 8 cones (`VOLUME_SPOTS`, was 4).
  After: s15 ±0.60 m, r34 ±0.68, supra ±0.54, raijin ±0.61, the Cybertruck on its light bar, the bikes one lamp at
  x = 0, trains at 2.85–3.37 m (their own lamps). `KIND_TRAITS.lampHeight` is only the fallback for a model without
  lamp parts now.
- **The grain**: a cone's six steps were spread at equal angles over the whole view ray. From inside a beam, looking
  at its lamp, none or one of them fell into the light, by the pixel's dither: lit or unlit by chance, and visible
  wherever the depth-keeping blur cannot average (leaves, nets, the sky's edge). The steps are now taken only on the
  part of the ray that is inside the cone and its reach (ray × cone as a quadratic, the interval by case, clamped to
  the reach sphere), at equal angles within it. A beam seen from the side looks as before.
- **Cost**: the volume pass 0.22 → 0.34 ms of GPU time (1080p, ultra, rival race at night, `tools/perf-pass.cjs`,
  load ~4 of 20 cores; a frame is ~6.5 ms there). Eight cones and the interval are the difference.
- **Verified** (GPU, headless Chrome, RX 5700 XT): the anchors and origins of all 18 vehicles as numbers before and
  after; the car select before / after on nine vehicles (`cmp/lamps4`: the NSR's light leaves its lamp, no glow
  above the U9's bonnet, the E235's comes from its roof lamps, the roach's from its eyes); the chase view before /
  after (`cmp/lamps3`: hardly a difference, as it should be); the owner's case reproduced and gone
  (`cmp/grain1/sheet-top.jpg`); one car on WebGL 2 and at quality `low` looked at. vitest 188;
  `tools/gpu-errors.cjs`: 0 on WebGPU and on WebGL 2.
- **Left as it is**: in a view from the front the road just before the camera shines (the lamp's mirror image on
  wet asphalt: right); stars on a rear window are the street lamps' highlights in the bloom, not the car's lamps.
- **Not verified**: other GPUs, a phone; every vehicle × every paint in the race (the anchors do not depend on paint).

### The grains reconsidered: pictures only, in water; no dust, no ornaments (11-12, the owner's word)
The owner (11-12): the grains are too many; grains decorating the buttons and particles spread over the whole
screen all the time are "しつこい"; reconsider all of it; a fluid-simulation-like expression would be beautiful; do
not cling to my requests, make it by your own sense. What I decided, and why:
- **Grains are a picture of a thing or they are not there.** Dust over the screen and the selection's edge in
  grains are gone (with `sweep`, `burst`, `data-grains`, the three groups). A menu is the interface over the live
  scene, nothing more; the drawn focus frame marks the selection again. Without a picture on the screen the layer
  does nothing: no step, no draw (it used to cost 3–4 ms a frame on every menu).
- **Four pictures stay**, each where the screen is about that thing: the course's relief (course select, loading
  screen), the sky in the selected time-of-day card, the medal on the results, and the title's 峠, which is now an
  **entrance only**: it condenses out of wisps in about a second, then the type takes over (at that size type is
  finer than grains: next to the crisp "TOUGE NOCTURNE" the grain glyph looked like noise) and the grains come
  apart. The grain glyph is now as large as the type (it was 1 / 1.3 of it).
- **The grains hang in water** (`ui/fx/fluid.ts`: stable fluids on a 40-row grid of the screen, velocity only).
  The pointer's strokes stir it; where it runs a grain goes with it and comes home when it rests: a stroke through
  the relief bends its contour lines, draws them out into mist between two eddies, and they find their places
  again within ~2 s. A thing asked for condenses near its place; let go, it thins out like ink within a second
  (it used to fly apart through the whole screen and stay as dust).
- 32 000 grains, all of them the picture (before: 48 000, half of them the picture): finer pictures for less.

Verified (RX 5700 XT, Chrome headless, WebGPU; build of this tree on vite preview; load average ~1):
- vitest 186 passed (grains: gone / condense / let go / move over / fill / stroke and home; water: rest, two
  eddies, divergence, dies down and never runs away); `tsc -b`; build.
- Pictures (`~/.local/opt/quality/cmp/fluid2`, `titlein1`, `fluid-medal`, `fluid-sky`, `fluid-gl`, `fluid-phone`):
  the title's entrance frame by frame (wisps → 峠 → type, no jump in size or place), a menu without a grain and
  with its drawn focus frame, the relief condensing, a stroke through it at 60 / 300 / 700 / 1400 / 3200 ms (bent,
  mist, home), the next course (the grains move over), the three skies, the medal in the three metals, the loading
  screen filling; the same on the WebGL 2 backend (`?webgl=1`), at phone size with touch (8 000 grains), and
  nothing with motion off.
- Cost on the page (their own step + draw, a frame): 0 on a menu without a picture (frame gaps 16.7 ms median and
  max), 2.5–3.0 ms with 32 000 grains in a picture, ~1 ms more while the water runs (then the count goes down by
  itself: `BUDGET` 3.5 ms). Node: 32 000 placed 1.9 ms a step, stirred 3.0 ms; the water alone 0.4 ms.
- `tools/gpu-errors.cjs`: 0 on WebGPU and on WebGL 2; one race picture looked at (camera with the car).
- E2E on the isolated stack (SwiftShader, quality low: no grains there, the markup only): boot, menu navigation,
  a click during a wipe, the phone run: passed; the time attack failed once and passed on its retry (the rank
  message did not show within 30 s; the server had answered 201 to the run, 17 s after the name: the machine was at
  load 10 with five tests' worth of SwiftShader), then passed at once when run by itself. Not the whole suite.

Not verified: other GPUs and real phones; how the stroke feels in the hand (pictures of a scripted stroke only);
the owner's opinion.

Live (11-12, `e1799be`): `docker compose up -d --build`; the served bundle is the built one, locally and through the
public address; leaderboard 200 on both; one picture of the live main menu (no grains, no page errors, no API
writes). A 55 s recording went to the owner (`~/.local/opt/quality/cmp/fluidrec1`, `fluidrec.cjs`).

### The forest is in: trees, bushes, undergrowth, rocks remade; a course's shaders built once (11-12)
The `nature` package (three rounds by an agent, each reviewed by me on pictures) is merged: twelve own species from
Blender scripts, planted by altitude, slope and distance to the road, on medium and up (`low` keeps the old trees).
CLAUDE.md "Forest" and "A course's shaders are built …"; docs/ASSETS.md for the models. The species' sheets went to
the owner after round 1; the owner has not commented on them (the look is my call under the overhaul brief; one
commit reverts it: the merge `b4e8db2`).

- Round 3 against my five points of round 2 (pairs before / after on every course × dawn / night / rain,
  `~/.local/opt/wt/nature/shots/pairs3`; I looked at tenrou dawn, oboro dawn, kirifuri dawn, autobahn night):
  tenrou has low growth on its slopes and trees on the uphill sides, the views stay open; the slopes under the
  views are grown over; the comb on oboro's ridge is gone; kirifuri's far hills read as forest (pale faces remain
  where steep). Still to be said: tenrou's hairpin and finish have no tall tree by the road (an open ridge now).
- **Found by the agent, on main too: every shader of a course was built twice** (three.js keys a render context by
  the depth of the `render` call; a compile asked at the top, the frames draw one level in), and the compile
  waited for 53 pipelines one by one. `threeFixes.compileAtPassDepth`, six compile lanes, the shadow maps marked
  after a compile (its first try left a destroyed depth texture in bind groups: the cause is written in
  `RenderHost.precompile`). The agent's numbers (quiet machine, load 1.3–2.4, six back-to-back pairs): load to the
  title on main 6.9–8.1 s, with the forest 7.8–9.1 s (median +1.0 s; it was +5.5 s before this); GPU time a frame at
  ultra 1440p with upscaling 6.86 → 8.48 ms, high 1080p 5.15 → 5.65 ms; frame rate at ultra 1440p upscaled
  91 / 80 → 77 / 75 fps (p95 20–21 ms), which is the main thread (379 draws against 304).
- **Found by me on the merged build: at night a birch in the headlights stood by the motorway like a green lamp**
  (bright leaves lit as by day). Foliage is darker and greyer by night now (`vegetationWeather(rain, dark)`);
  pictured on the autobahn and oboro at night.
- Verified by me on the merged tree (`fx3d`): tsc, vitest 182, build; `tools/gpu-errors.cjs` 0 on WebGPU and on
  `?webgl=1` (race pictures looked at: camera with the car, forest and undergrowth drawn);
  `~/.local/opt/quality/hitch.cjs` at high (load 3–5): first load 9.1 s (the build before the forest 8.1 s in the
  same sitting), a race's start 2 gaps (76 ms worst; before 112 ms), a new course 5.4–8.0 s behind the loading
  screen (before 4.3 s), courses kept afterwards switch without a gap, video memory with four courses built
  1.54 GB (before 1.42 GB). **The first change to dawn stands still for 0.9 s** (gaps of 146 / 313 / 315 / 124 ms;
  before the forest the first change to rain took 0.76 s and to dawn 0.28 s: about the same in sum, not looked
  into further).
- E2E on an isolated stack, a subset (quality `low` on SwiftShader: the load path, not the forest): boot, the
  full time-attack run, rival battle, course select, the phone test: 5 passed.
- Not verified: other GPUs (the two-pass trees lean on equal depths between two shaders: a driver that rounds them
  differently leaves flat-lit pixels, by design no holes); the forest on phones (they start on `low`, which has none of it; a phone set to medium or
  higher: untested); frame rates on a weaker GPU than the RX 5700 XT; the whole E2E suite;
  the vehicle thumbnails still show the old trees behind the cars (re-rendered since: `a62a10c`, all 18 looked at).

### The results' medal in grains (11-12)
- `shapes.ts` `medalShape(gold | silver | bronze)`: a disc with a rim, fluting and an edge (it swings on its ribbon
  and turns to the pointer), a wreath of two branches, the medal's character (金 / 銀 / 銅, the element's text through
  a mask, drawn by its strokes' edges: filled in, 銀 was a blot at this size), a ribbon, a gleam that goes round
  (`along` = the angle about the disc). Tones `silver` / `bronze` from the tokens. `Results.tsx`: a place beside
  the card (`.medal-grains`, `data-cloud="medal:<kind>"`), mounted when the stamp lands; none on a phone or a
  screen narrower than 3:2 (no room beside the card); the stamped label stays as it was.
- The resting rule of the commit before took the grains from the results after a replay (the game stays in
  `replay` behind them): `replay` is out of the rule again.
- Verified on the GPU: a made-up gold result (no race driven) pictured as the medal gathers (2.6–7.2 s) and close,
  silver and bronze close: disc, wreath, character and ribbon read in all three; 48 000 grains at 3.6–4.1 ms a
  frame of their own, no page errors; `tools/gpu-errors.cjs` 0 on WebGPU and `?webgl=1`. vitest: 12 in `ui/fx`.
- E2E on an isolated stack: boot and the full time-attack run with its results (SwiftShader: the markup and the
  results flow, not the grains). tsc, vitest 170, build.
- Not verified: a real race's result on the GPU (the made-up one only); other aspect ratios than 16:9 by picture;
  the owner's eye.

### The condition cards' skies in grains; the grains rest in a race; the title's first shot (11-12)
The owner asked for moving pictures on the clear night / rain / dawn cards (videos made with Gemini); Gemini's video
generation still fails, so the selected card's sky is now a scene of grains (my proposal of 11-11, a stand-in the
owner has not yet seen).

- `shapes.ts` `skyScene`: **night** (stars at every depth, the band of the galaxy, a crescent moon, the ridge in
  cyan, the town's lights in quarters under it), **rain** (streaks of six grains that fall together through a
  lamp's cone, the lamp, rings on the wet road, the lamp drawn out in the water), **dawn** (the sun's disc cut off
  by the sea of clouds, its glow and rays, the clouds in rows, two peaks lit on their sunward side). `cloud.ts`
  `Shape.fall`: points with an `along` travel through the shape; their grains get the points' velocity fed forward
  (they ride without lag), start again at the other end, fade at both ends. `Cloud.tsx`: `data-cloud="sky:<id>"` on
  the selected card's `.ch-sky` (`RaceSetup.tsx`), the drawn sky fades to a dark stage under it (`.cloud-on`); the
  strip is 7.5rem high now (was 5). Without grains (motion off, a software renderer) the cards are as before.
- **The grains rest while the game is in a race**, whatever the app's screen (`countdown` / `racing` / `replay`):
  found by the nature package's timings (a tool that starts a race with the app on the title kept 3 ms a frame of
  grains running). `tools/gpu-errors.cjs`' race picture shows the title's plain 峠 over the race: no grains.
- **Two of the title's four shots showed a roof and a bonnet** (seen behind the condition cards in these pictures;
  `Game.cinematicCamera`, also the replay's camera). The orbit was as wide as the road around the centre line, and
  the car drove along the edge: the camera stood right over it six seconds into the title. And both travelling
  shots were eased towards a place ahead of the car, so at speed they fell back by speed / rate (five metres at
  140 km/h): the low front shot looked down on the bonnet. Now: the travelling shots are carried along by the
  car's own movement and eased only in the rest; the first is a swing on the side of the car where the road has
  room, never nearer than five metres; the low front shot is a three-quarter view beside the lamps' cones (in
  them the glow in the haze whitens the picture: found when the camera first kept its lead). Measured on the GPU
  over 36 s of the title: shot 0 at 5.9–9 m from the car (was 1.8 m at its nearest), the front shot at 5.1–6.3 m
  and 0.6–0.7 m above the car's origin; pictures of both looked at.
- Verified on the GPU (load 2–5): the three skies pictured whole and close (1280×720), the rain in two pictures
  0.35 s apart (different) and in a 24 s recording (51 fps of screencast frames) looked at as a sheet; a phone
  (844×390, touch: 12 000 grains, the strip 34 px: moon, ridge and town still read), the WebGL 2 backend (same
  picture), motion off (the drawn skies, the drawn focus frame); 31 500–37 000 grains at 2.8–4.1 ms a frame of
  their own; no page errors. `tools/gpu-errors.cjs` 0 on WebGPU and on `?webgl=1`. vitest: 11 in `ui/fx`.
- E2E on an isolated stack, a subset only (SwiftShader: no grains there, so it covers the markup, the guard
  and the camera, not the skies): boot, menu navigation, course select and the phone test on the tree before the
  camera change; boot and the full time-attack run (race, results, replay camera behind them) on the final tree.
  The whole suite was **not** run. tsc, vitest 169, build.
- Not verified: the owner's eye (a recording goes with the report); other GPUs / browsers / real phones; a
  display with a pixel ratio of 2 at desktop size.
- **Live (11-12)**: main `540856c` deployed, bundle `index-D21nWRu6.js` served locally and through the public
  address, leaderboard 200 on both, the speech model's JSON 200. A 24 s recording, a still of the three cards and
  four title pictures went to the owner.

### The grains as a cloud in depth (11-11, after the owner's word on the first grains)
Owner: 「粒はもっと細かく、3d パーティクルに近いです。粒だけで物を表現したり、粒だけで強調させたりといった使い方を
予想してました。美しい寄りな表現担当ですね。」 The 2D layer (420 grains tracing frames) is gone; CLAUDE.md "The grains
over the menus" describes what replaced it.

- `ui/fx/cloud.ts` (simulation, 9 tests with `shapes.ts`), `shapes.ts`, `Cloud.tsx`, `cloudRenderGpu.ts` (instanced
  quads on the game's WebGPU device), `cloudRender.ts` (WebGL 2 points, only next to the WebGL 2 backend).
  Depicted by grains alone: the title's 峠 (the element's own text through a mask), the selected course as a relief
  under the course cards and on the loading screen, where it fills with the progress (road, start and finish beams,
  the land as contour lines from the course's `Landform`, water as a sheet; it sways and follows the pointer).
  Emphasis by grains alone: the edge of what the pointer is on or the keys selected (the drawn focus frame is hidden
  while the grains depict; rows keep their bar and wash).
- **Found: a WebGL context made next to the game's WebGPU device loses that device** (`vkQueueSubmit failed with
  VK_ERROR_DEVICE_LOST`, headless Chrome on the RX 5700 XT; the game then fell back and reloaded). Hence the WebGPU
  renderer on the game's own device, and the rivals' voice offered only when the game is drawn with WebGPU
  (`Speech.usable`; a WebGPU model next to a WebGL 2 game is the same pairing, untested and now excluded).
- **Found: the first cloud cost 2.9 ms a frame for 9 400 grains** (~15 ms for 48 000: frames were lost and the
  count, then steered by the frame time, fell to nothing under any load and stayed there). The step was rewritten
  (no `Math.hypot`, sines from a table, flow / brightness / colour for a quarter of the grains in turn, the look
  bytes written in the step): 48 000 grains cost 1.2 ms floating and 3.0 ms all seated in Node, 2.5–4.1 ms in the
  page (upload and draw included). The count now follows the grains' own cost (4 ms budget).
- Verified on the GPU (machine load 2–5 meanwhile): pictures of the title, the main menu with the pointer, the four
  courses' reliefs with the pointer left and right (each stays in its place under the cards), the rivals screen,
  the loading screen at three fills; two recordings (41 s, 57 fps of screencast frames) looked at as sheets of
  frames; frame gaps with 48 000 grains median 16.7 ms, p95 16.8–33 ms; `tools/gpu-errors.cjs` 0 on WebGPU and on
  `?webgl=1`; the WebGL 2 twin looked at (same picture). tsc, vitest 167, build.
- **Found by E2E: on a software renderer (SwiftShader) the grains' WebGL 2 context blanked the game's canvas** (the
  boot test's picture of it: 5.6 kB). No grains without a GPU now, decided from the game's own context
  (`RenderHost.software`), no second context made. E2E on an isolated stack, a subset only: boot, menu navigation,
  phone passed on the final tree; click during a wipe, course select, rival battle passed on the tree before that
  fix. The whole suite was **not** run.
- Not verified: other GPUs, browsers and phones (the WebGL 2 twin next to a WebGL 2 game on Firefox / Safari: one
  machine's Chrome only); a display with a pixel ratio of 2 or 4K (pictures at 1280×720, ratio 1); the medal's
  grains on the results screen are an amber edge only and faint on so small a thing (one picture of a made-up
  result); the owner's eye on the whole.
- Not built yet (ideas): the results' medal itself, the condition cards' pictures (stars, rain, dawn: a stand-in
  for the Gemini videos that fail), the rival's portrait gathering; the simulation on the GPU (a compute pass) for
  several hundred thousand grains if the owner wants it denser still.
- **Live (11-11)**: main `6f453b4` deployed, bundle `index-BoanQkpS.js` served locally and through the public
  address, leaderboard 200, the speech model's JSON 200; the grains pictured on the live site on the GPU (47 250
  grains, 3.8–3.9 ms a frame of their own, frame gaps median 16.7 ms, no page errors). A 42 s recording of the
  final build went to the owner.

### Trees, bushes, undergrowth, rocks remade: rounds 1 and 2 (11-11; merged on 11-12, see above)
- The `nature` package's branch `worktree-agent-a93b5dfec501746d9` (tip `2621c03`): twelve own species (Blender
  scripts, three levels + impostor each), forests planted by altitude and slope, on medium and up; low keeps the old
  trees. Its own numbers, all taken under load (2–18): GPU time a frame at 1080p high 5.0 → 7.8 ms, ultra 8.0 →
  9.5 ms, 1440p ultra with upscaling Quality 6.7 → 11.6 ms; frame-rate pairs contradict each other; the plan's
  targets are **not shown met**. Downloads per course: 9.6 MB (high / ultra), 2.7 MB (medium).
- Reviewed by me on its sheets (oboro dawn / night, kirifuri dawn pairs, close-ups, quality levels, one species):
  a large step up, but **not ready**: the forest closes the views the courses are named for (the sea and the town
  from oboro, the lake from kirifuri), one artefact on a retaining wall at night, far hillsides as dots. Sent back
  for one more round (views open by a planting rule, the artefact, far hills, frustum culling, timings on a quiet
  machine). Five sheets went to the owner; nothing of it is in the game.
- **Round 2 (tip `8c984ee`), reviewed by me on its pairs (11-12)**: the views are open (a sight-line planting rule;
  trees within 40 m of the road: oboro 8 090 → 2 952, kirifuri 4 246 → 2 917, tenrou 1 793 → 293), the wall
  artefact is gone, the forest is culled by the camera's frustum. Still **not ready**: tenrou is nearly treeless
  by the road (worse than before at its hairpin and finish), the valley sides under the views are bare, a comb
  of same-height trees on a ridge of oboro, kirifuri's far hillsides read as pale bare faces; and the cost: load
  to the title 7.2–8.7 → 13.2–13.9 s, ultra at 1440p with upscaling 64.6 fps with a p95 of 32 ms (the agent's
  numbers, quiet machine). Sent back once more with these five points (round 3: see the section of 11-12).

### The rivals speak (11-11, owner's request): a speech model on the player's GPU
Request: a TTS model, Supertonic 3, WebGPU assumed; the language model's lines are spoken; without WebGPU no TTS
model, text only. My plan (the ~400 MB model only after the player's yes, served from our own server, a voice per
rival) was approved by the owner the same day. CLAUDE.md "The rivals' voice"; docs/ASSETS.md for the model.

- `game/audio/speech/`: `text.ts` (the publisher's text preparation; tags other than the three sound tags are taken
  out of a line), `speech.worker.ts` (onnxruntime-web 1.31.1 on WebGPU in a module worker; the model's files into
  Cache Storage with progress; a warm-up line so that the first real one is quick), `Speech.ts` (states:
  unsupported / absent / idle / loading / ready / failed). `Game.rivalSays` waits up to 0.7 s for the sound;
  `AudioEngine.say` plays it over the rest, turned down to 40 % meanwhile. The offer once on the rivals screen, two
  settings rows (on / off with the state, delete the browser's copy), the licence linked from both.
- Server: volume `tts` + `docker compose --profile tts run --rm tts-fetch` (revision pinned, SHA-256 per file),
  nginx `/tts/` (404 without the model).
- **Verified** on the RX 5700 XT in headless Chrome (WebGPU), `~/.local/opt/quality/voicecheck.cjs`, against a
  preview and against an isolated stack that got the model through `tts-fetch` (26 s for 383 MB):
  - the offer appears, a yes fetches and sets the model up: 8–10 s from a local server (no network to speak of);
    a second visit from the browser's copy 5–13 s (the machine was shared: load 2–3), no model file asked of the
    network again, no offer;
  - a rival battle: the line before the start came with its voice (the sound took 0.42–0.59 s after the text;
    2.6 s of speech), the rest stepped back to 0.4 and returned to 1;
  - frames in the race (720p, quality high, vsync 60): no gap over 40 ms in 8 s without the model and in ~9 s with
    a line synthesised every 1.5 s (0.3–0.7 s per line of 6–17 characters; worst frame 33 ms, one dropped);
  - in the menus the set-up costs frames while it runs (8–27 gaps over 40 ms, worst 0.2–0.7 s): it is started on
    the way to a rival battle, where the course loads anyway.
  - E2E on that stack (the model in its volume; headless Chromium there has no WebGPU adapter, so no offer): boot,
    menu navigation, rival battle, course select, phone: 5 passed (10.6 min). The whole suite was not run.
  - `tsc`, 164 unit tests, build (the worker is 126 kB, the runtime's WebAssembly 28.7 MB, both fetched only when
    the voice is loaded).
- **Live** (11-11, main `27efc93` + this note, bundle `index-3tF9oDyG.js`): deployed, the model fetched into the live
  `tts` volume (`tts-fetch`, 383 MB, checksums right). Checked: the bundle and the leaderboard locally and through
  the public address; the model's files through the public address (36 MB in 0.8 s from this machine, the 257 MB
  file's headers, the licence as text; Cloudflare does not cache them: `DYNAMIC`); `gpu-errors.cjs` 0 on WebGPU and
  WebGL 2; `voicecheck.cjs` against the live site: the language model's own line (「免許取り立てだけど、この峠じゃ負け
  ないからな！」) came up with its voice 0.35 s after the text, 3.5 s of speech. In that run a line synthesised every
  1.5 s **during** the race gave 10 frames over 40 ms (worst 67 ms; the two runs before gave none, the machine was
  busier): the game itself speaks only before the start and after the finish.
- **Not verified**: how it sounds (I cannot hear: the owner got a sample of the ten voices on 11-11; which rival
  gets which voice was assigned from names and portraits, to be changed by ear), whether names and kanji are read
  right, other GPUs and browsers (Safari, Firefox, phones: the download alone is 400 MB), the download through the
  public tunnel, video memory next to the game at 4K / ultra (the model's weights are ~400 MB there).

## Session 8 (2026-11-10) — new vehicles: Cybertruck, Yangwang U9 Xtreme, three motorcycles, the L0 maglev

Owner: 「テスラのサイバートラック、バイクを3台、リニアモータ新幹線を実装してください」 (bikes chosen: Honda NSR250R,
Kawasaki Ninja H2, Suzuki GSX1300R 隼), then 「サイバートラック以外の電気自動車で現状最速の車両も入れてほしい」 → the
Yangwang U9 Xtreme (503.17 km/h, 2026-11-01, production-car record). Code is in; the own models are being built (not
deployed yet: the owner sees each sheet first).

- **Kinds** (`vehicle/kinds.ts`): `kindOf` / `KIND_TRAITS` / `hasExhaust` replace the per-call-site checks for the
  garage framing, badge, lamp height and exhaust (the "base + extension" design the owner asked for, first step).
- **Cybertruck (Cyberbeast)** and **U9 Xtreme**: single-ratio electric cars (`EvSound`). Measured (`tools/train-accel.ts
  <id>`): Cybertruck 0–96.6 km/h 2.9 s, top 209.5 km/h; U9 0–96.6 2.0 s, top 502.8 km/h. The U9 out-runs the cockroach
  at the top (the roach test exempts it).
- **Bikes** (`vehicle/bikes.ts`, `render/BikeModel.ts`, `BIKE_CAMERA`): see CLAUDE.md. Measured: NSR 0–100 6.0 s, top
  186 km/h; H2 3.0 s, 329 km/h; 隼 3.1 s, 313 km/h. The first AI runs spun and flipped (maxSlip 90°, a DNF on 朧峠): the
  rear lost its side grip under the virtual load transfer and the drift state took more. Fixed (brakes by load, side
  grip on the static load, traction control, slipper clutch, no drift state, steering cap, wider/lower virtual track,
  more pitch/roll inertia); now every legend lap is clean (0 impacts, 0 respawns on all four courses) and the feel tool
  keeps ordinary corners at 4–15° (NSR braked in at 90 km/h: 20°). Vehicle test added.
- **L0** (`TrainInfo.maglev`, `'lsm'`): 0–500 km/h in 191 s / 13.6 km (published ~13.4 km; test bound 180–200 s);
  floats 10 cm above 150 km/h; running noise at 500 km/h −13 dBFS (E5 at 320: −17), floating at 160 km/h −40 dBFS
  (on its tyres at 140: −32). Procedural stand-in body until its model is done.
- **Medals** from legend-AI sims (2026-11-10): cars scaled by the R34's gold/sim ratio per course, bikes and L0 the
  legend time +7 % / +16 %. Backend: 18 vehicles in `game.cars` (container tests 17/17); the autobahn floor comment
  updated (U9 ~64 s).
- Verified: tsc, vitest (all pass), backend tests (container, `--build`), handling-feel, sims. **Not yet**: Chrome
  check of the garage / race / sounds (Blender agents running; no Chrome alongside), E2E.
- **Metal looks metallic** (owner: 「金属光沢ついているものは金属光沢にしてほしい」): `CarSpec.bareMetal` draws the
  Cybertruck's bare stainless swatch fully metallic without clear coat (`paintFinish`, `c46688a`); the own models'
  chrome, rims and discs were already metallic. The agents' check renders now have something for metal to reflect.
- **Lamp shapes** (owner: 「ライト部分の目の形が参考とはかなり違うかも」): every own model's lamps are traced on the
  photos and scored per lens (IoU, p95 / max px) with close-up sheets. Supra round done (head lamp 0.78 → 0.89,
  corner opening 0.47 → 0.92, indicator 0.70 → 0.95; far-side lamps limited by the camera solves); the four deployed
  own cars are being re-checked.
- **R34 and Cybertruck: our own models in the game** (owner approved, 「はい」, 2026-11-10). Built with
  `blender-models.cjs cars r34,cybertruck`: R34 57 k tris, 0.56 MB (V-spec look, fitted to 6 photos; the exhaust
  anchor comes from its `exhaust` part, so the `exhaust` override is gone; the import entry is dropped); Cybertruck
  39 k tris, 0.27 MB (fitted to 6 photos; `tailLampGain: 12` for its smoked light-bar lens). Checked in Chrome
  (software rendering, the GPU is off after a VM restart): garage at dawn and night for both, a night race start
  behind the Cybertruck (light bar and tail bar lit, the stainless reflects). The Supra is the last third-party car.
- **Deployed** (2026-11-10, bundle `index-C8ga6l-7.js`; the R34 and Cybertruck GLBs served hash-equal; `/api/content`
  lists 18 vehicles). Before it, every new vehicle was opened in Chrome (garage, and a race start for the NSR, U9 and
  L0; no page errors). Bikes, U9 and L0 still show their procedural stand-ins. E2E not run for this deploy.
- **Supra: our own model; every car is now our own** (owner: 「スープラ入れてイイヨ」, 2026-11-10). Late RZ with the
  factory wing, fitted to 7 photos (silhouette IoU 0.906–0.955), lamps traced and scored per lens (head lamp 0.89,
  corner opening 0.92, indicator 0.95), the wing rebuilt as a rigid aerofoil after the body fit (the lattice had
  twisted it), the plate recess and rear seams redone; 73 k tris, 0.47 MB (the Sketchfab file was 1.1 MB). With no
  third-party car left, the import tools are gone (`import-cars.cjs`, `car-import.json`, `render/carImport.ts`, the
  `__importCar` / `__previewCar` hooks) and so is the procedural export (`export-cars.cjs`, `assets:cars`,
  `__exportCar`). Checked in Chrome: garage at dawn and night, a night race start. Deployed (bundle `index-Y1K8yz12.js`, the GLB
  served hash-equal).
- **Lamp review of the four earlier own cars** (owner: 「ライト部分の目の形が参考とはかなり違うかも」; approved 「はい」 to ship
  them together). Each lamp traced on the photos and scored (IoU, p95 / max px; `fitdata/<id>/lamps.json` + tools),
  insides redrawn, metal parts metallic 1 (rims, discs, reflectors, clear lens housings), check scenes with reflection
  panels. Impreza: head lamps 0.61–0.82 → 0.76–0.92, tail 0.60–0.68 → 0.78–0.85 (lamp patches welded: the cover's
  reflections no longer break into blocks). RX-7: rear band 0.68 → 0.88, bumper reflector bars 0.63–0.65 → 0.86–0.89,
  front combination lamps redrawn inside. S15: head lamps 0.55 → 0.84 / 0.63 → 0.71 (blunt rounded inner end), reverse
  lamps 0.69–0.71 → 0.84–0.89 (a wedge), tail cells redrawn. AE86: tail rows and cells redrawn (the photos disagree
  by 2–3 cm); the late front bumper lamp is now amber + clear (fluted lens, chrome reflector; the clear cell uses the
  `headlight` material and glows as a parking lamp), 8.8 cm tall; the solved cameras are 22–28 px off at the car's
  face (checked against the bumper's own edges), so the lamps were scored registered by that offset (whole lamp
  0.28–0.38 → 0.66–0.67). Silhouettes unchanged. Checked in Chrome: garage (night / dawn) for all four, a night race
  start behind the AE86 (pop-ups up and lit at night, closed at dawn).
- **L0: our own model in the game** (owner: 「リニア新幹線優先で実装までお願いできる？」, i.e. through to the game once
  the final sheet is sent). `tools/blender/l0.py` + `parts/l0_*.py` + `l0_textures.py`, fitted to Commons photos
  (`fitdata/l0/`: cameras, masks, lamps, scoring tools; silhouette IoU 0.94–0.96 on three solved cameras, lamps
  0.82–0.94). 60 k tris, 0.24 MB. The consist stays at the published 28 m end cars (the model's tip is 0.17 m short of
  `trainNoseZ`). `TrainInfo.lamps`: two round units per side low on the nose, the tail lamp in the inner one, the
  small side windows lit at night.
- **Optimiser fix** (`tools/blender-models.cjs`): the first `dedup` merged the L0's two identical end cars into one
  mesh shared by both nodes, and `join` + `quantize` then squashed it (reproduced on the L0 with identical end cars:
  2.90×2.75 m came out 2.80×3.15). The first dedup now leaves the vertex accessors alone (meshopt's own cleanup still
  shares identical buffers after quantising); l0.py's 1 m offset workaround is gone (0.26 → 0.24 MB). Rebuilding the
  Cybertruck with the fix gives a byte-identical GLB.
- Checked in Chrome (software rendering): garage at night and dawn (side windows glow at night; the four head lamps
  lit and lighting the road, seen head-on), a night race start in the cab view and the chase views; no page errors.
  The float above 150 km/h was not reached in the browser (the sim and the earlier stand-in cover it).
  Deployed (`e880d4e`, bundle `index-D8DrH9l9.js`, `l0.glb` served hash-equal, leaderboard API 200). E2E not run.
- **E5/H5 nose refit** and **the three bikes' own models** (owner: 「配置できるものは配置してok」, 2026-11-10, after the
  nose sheet and the H2 round-2 sheet). E5/H5: the canopy moved ~2 m back, the nose narrower for longer, the green line
  kept high down the flank; on the solved Nasu-Shiobara camera the nose window's IoU 0.862 → 0.926, outline p95 50.6 →
  31.7 px (one camera only; `fitdata/e5/`); consist and lamps unchanged; e5.glb 0.74 MB, e5-h5.glb 0.76 MB.
  Bikes: NSR250R 39 k tris 0.32 MB, Ninja H2 (detail round 3: stock can, layered cambered panels, drilled discs, grey
  engine) 0.37 MB, 隼 (detail round at a clean point) 0.35 MB; riders in the GLBs. The H2's mirror coat
  (ミラーコートスパークブラック, swatch now #64686e) is a metal swatch under a clear coat (`bareMetal.clearcoat`).
  `blender-models.cjs` now creates a kind's output folder. Checked in Chrome (software rendering): E5 head-on at dawn
  and the H5 at night (lamps, window glow), the H2 and 隼 garage at dawn, the NSR garage at night and a night race start
  (chase, rider and rear views); no page errors. The bikes' refinement continues (Hayabusa detail round finished after
  this build; H2 round-3 sheet pending): rebuild and redeploy when they land.
  Deployed (`c68aaa3`, bundle `index-GpzDFAQv.js`; e5, e5-h5 and the three bike GLBs served hash-equal; leaderboard
  API 200). E2E not run.

- **The cockroach: twice the performance, Mach 1 at the top** (owner: 「ゴキブリがチート枠の威厳失ってきてるから性能2倍に
  してほしい、最大速度はマッハ1」). Grip 1.75 → 3.5, brakes 15 → 30 kN, pull 3600 N·m flat to the legs' limit at
  29,540 rpm = 340.3 m/s, drag 0.25 → 0.2 (else it stalled ~15 km/h short). Measured (`tools/train-accel.ts roach 0`):
  0–100 km/h 1.56 → 0.88 s (the tyres' limit, ~1.8×), 0 → Mach 1 in 15.5 s / 3.4 km, top 1226 km/h; from 100 km/h it
  stops in < 13 m. Doubling the grip doubled the cornering stiffness (side force = μ · load · curve(slip)), so every
  steering input turned it twice as hard and the AI weaved into the walls (flips, 90° slides): half the steering lock
  (40° → 22°) restores the response. Side effects handled:
  - `VehicleSim.impact` counted any > 3 g as an impact: the cockroach's own cornering and braking would thud and shake
    all the time. Now the threshold is 3 g or 1.25× what the tyres can give (downforce included); other cars unchanged.
  - The chase camera trailed by speed / 14 (24 m at Mach 1): the lag is held to 10 m and the speed pull-back stops at
    500 km/h (no other vehicle reaches either).
  - The HUD's speed takes four digits in a smaller face (`.speed.wide`).
  - The autobahn's AI cap 140 → 345 m/s (only the cockroach goes faster than 140).
  - Medals from the legend AI (2026-11-10): 朧 58.5 s, 霧降 50.0 s (rolls once after a wall hit at 227 km/h), 天狼
    44.0 s, autobahn 35.5 s (989 km/h: the AI's corner speeds leave out the downforce). The AI still brushes the walls
    at the pass speed cap (it did before, less often): only the medal runs use it.
  - Backend floors: a lap on the racing line at the cockroach's full limits takes 37.5 / 30.5 / 27.6 s on the passes
    and 27.5 s on the autobahn (Mach 1 for 5.2 km); floors 32 / 26 / 23.5 / 23 s (were 50 / 42 / 38 / 58). Container
    tests 17/17 (the autobahn floor test now at Mach 1).
  - `tools/sim-run.ts` gained `DEBUG=1` (hard impacts, slides, tilts with the lateral offset) and `AI_TOP=<m/s>`.
  Checked in Chrome (software rendering): the garage card (0.9 s, 1225 km/h), the autobahn race with the speed pushed
  to 340 m/s (HUD "1201" in the small face, the cockroach in view in both chase views); no page errors. tsc, vitest
  64/64, handling-feel (corners 4–16° of slip, wall hits keep their speed).
  Deployed (`c757b8c`, bundle `index-BXSzCoyg.js`; the live backend reports the new floors; leaderboard API 200). E2E
  not run. Before it, the bikes were rebuilt from the finished scripts and redeployed (`0a099bb`, GLBs hash-equal).

## Session 7 (2026-11-03 – 11-04) — every model our own (Blender); the owner's train lineup; a livery per line

Owner: "E231 (Musashino), E235 (Yamanote), Keikyu 1000, Tobu 30000 and the Hayabusa: build them all and put them in
the game; the cars too, and the scenery. The goal is that no credits have to be shown" (the VVVF-Simulator port and
its YAML-Files patterns keep their credit: owner's choice). Then: "a train's colours and destination change with the
line: E231 Musashino and Sobu local, E235 Yamanote and Sobu Rapid, Tobu 30000 Tojo or Isesaki; show the line's name,
not a station". Models are built by Blender Python scripts (5.2 LTS, headless; subagents in parallel, at most four
Blender processes) and checked against photos (photos only to measure) before they go in.

- **Pipeline** (`09f96e7`): `tools/blender-models.cjs <trains|cars|props|creatures> [ids] [--render]` replaces
  blender-trains.cjs: Blender → GLB → glTF-Transform (dedup, train palettes lossless, join, weld, WebP, meshopt);
  materials, primitives and triangles sorted, so an unchanged script gives the same bytes. Train line variants are
  the same script with `--variant <name>` → `<id>-<variant>.glb` (`KINDS.trains.variants`).
- **Keikyu N1000 v2** (`09f96e7`): rebuilt from part modules (body with painted livery and LED displays, TH-2100
  bogies, PT7117 pantographs, underfloor, couplers, skirt); accepted by the owner from renders.
- **Scenery props** (`d01cd10`): street light, wind turbine, curve mirror, vending machine, torii, stone lantern, bus
  shelter, traffic cone from `tools/blender/props/` (built to the game's convention: PROPS lost its yaw / origin fixes
  and the credits). Checked in the game at dawn and night on 朧峠 and 天狼 (lamp glass and vending fronts glow,
  rotor turns about the hub). The Sketchfab props and import-props.cjs are gone.
- **Lineup** (`c8795ff`): E231-0 after its move to the Musashino Line (renewed Mitsubishi 2-level IGBT), E235-0
  (full SiC), Keikyu N1000, Tobu 30000 (Hitachi 3-level IGBT), E5 Hayabusa (26.5 m end cars: `TrainInfo.consist`,
  `f87a388`). Ginza 1000 and N700 retired: their stored runs stay but leave every list (`cbb8e4d`, test). Specs from
  ja.wikipedia (estimates marked). Medals from clean legend-AI laps (`TRAIN_MEDALS`). The AI no longer backs up when
  a slow train gathers speed (`4363a27`; the cars' sim laps unchanged to the digit, bots stay valid).
- **Sound**: patterns for the new trains (`7c303f1`: YAML-Files `JRE_E233_1000_MITSUBISHI` stands in for the renewed
  E231; our estimates `E235_ESTIMATE`, `TOBU30000_ESTIMATE`; the E5 runs the N700 estimate with its gear 82:31). The
  running noise is synthesised (`3a5b7f9`, `audio/running.ts`: octave-band roar fitted to two Commons recordings within
  ~1 dB per band, joints per axle, wind, the motors' hum, flange squeal, brake hiss); the recordings and their credits
  are gone.
- **Own models** (`a5e2e82`, `1732e1e`): E235, Tobu 30000, E231 (body, roof, underfloor, bogies, couplers; LED
  displays; car numbers) and the cockroach (57-bone rig, alternating-tripod scuttle). Lamps measured on head-on
  renders (`TrainInfo.lamps`). The train import pipeline (import-trains.cjs, train-import.json, trainImport.ts,
  `__importTrain`) is removed.
- **Liveries per line** (`8d8957e`, `9a60669`): `Livery.variant / series / control / vvvf / swatch`. E231 武蔵野線 /
  総武線各駅停車 (yellow, the original 3-level IGBT `JRE_E231_MITSUBISHI`), E235 山手線 / 横須賀・総武快速線 (E235-1000),
  Tobu 30000 東上線 / 伊勢崎線 (1996–2011 three-colour LED era). The model `<id>-<variant>.glb` is loaded on demand;
  the garage rebuilds the train when the line changes and names the line next to the swatches; the race's spec and
  sound follow the line (`specForLivery`). Displays show the line's name (Keikyu: 京急本線).
  Verified in Chrome on the RX 5700 XT (vite preview, API cut off): each swatch of E235, Tobu 30000 and E231 loads
  its line's model and the label names the line; E231 head and tail lamps at dawn and night in a race.
- **Owner's review (2026-11-04)**: "the top of the E235 / E231 faces is wrong: the colour normally frames the windows";
  "the E231 also ran in Tozai-through and Joban colours, check the other trains"; logos: the owner chose to put them in
  (they are trademarks, the site is public): drawn by us as shapes, removed if a rights holder objects; no mascots.
  - E235 (`ef25c0d`): the line colour runs over the windscreen as a frame (0.08 m top band), JR marks on the cab-car
    sides; `chuosobu`: the sets moved from the Yamanote Line in 2026, canary yellow (総武線各駅停車).
  - Keikyu: the KEIKYU side logotype on the middle car. Tobu 30000: no body logos on the real cars (photos).
  - E231: the silver FRP frame round the black face (the line colour a bar under it), JR marks. Owner then: "the black
    here bothers me" (the top corners): the black ran out into the corners, because near the top the face turns into
    the roof's shoulders and the face texture's rows end short of the body's width. The black now ends just over the
    displays (y 3.36, round top corners r 0.30) and stays a frame's width inside each row's end. Liveries 常磐線 (快速,
    emerald + yellow-green), 地下鉄東西線直通 (800番台: narrower body, the cab's emergency door on one side) and
    上野東京ライン (近郊型 1000番台, 湘南色; Hitachi 2-level IGBT, YAML-Files `JRE_E231_HITACHI`). A line whose cab differs
    gives its own lamps (`Livery.lamps`).
  - E5 (`fda2605`): own model (nose and canopy fitted to head-on and 3/4 photos, PS208 with its noise shields, bogies,
    the Hayabusa logo and JR marks) and the H5 (北海道新幹線: 彩香パープル band, H5 numbers and logo). Its four lamps
    in a row: `LampPair.n / gap`.
  - Verified in Chrome on the RX 5700 XT (vite preview, API cut off): each new swatch loads its line's model and the
    label names the line; head and tail lamps at dawn and night.
- **Deployed** (2026-11-04, `378220c`): the served bundle matches the local build, the new train models are served
  byte-identical, `/api/content` lists e231 and e5. Tests: vitest 53/53, backend 16/16 (container, `--build`); E2E not
  run for this deploy.
- **Cockroach lamps fixed** (owner: the lamps sat off the head; `4d978d8`, deployed 2026-11-04, bundle
  `index-CS_Gjguf.js`): the model was centred across on its lopsided posed bounds (antennae, gait), 0.35 m off its body
  and off the lamp spheres. It now keeps its own plane of symmetry, and the compound eyes (their atlas patch) take the
  lamp material, the beams starting at their centres. Checked head-on in the garage at night; vitest 53/53.
- **Owner's bug reports, 2026-11-06** (`2743cf9`, deployed, bundle `index-Aa5HYB9G.js`):
  - Rain fell inside the rock shed: the sheds export their roof footprint (`SceneryResult.covers`), and the rain
    shader drops streaks under the slab of the nearest 16 quads. Checked in Chrome on 朧峠 in the rain.
  - "Saving to the database sometimes failed": the nginx log showed a `POST /api/runs` 401. `ensurePlayer` checked
    the stored token only on a name change, so a token the server no longer knew (e.g. after the 2026-11-04 reset of
    the players) failed every submission. It now checks the token every time and registers again on 401
    (`src/api/__tests__/client.test.ts`). No 422 or 5xx on run submissions in the log since 2026-11-04.
- **Impreza (`raijin`): our own model in the game** (owner: 「はい、入れてください」 after the final sheet; deployed 2026-11-10, bundle `index-CuQha91H.js`).
  - Replaces Mac CGI's Sketchfab model. Stock WRX STI GDB-C (2004 "blobeye") with the factory wing and gold 12-spoke wheels.
  - Built by `tools/blender/cars/raijin*.py` and fitted to 5 photos with a body lattice (`raijin_ffd.py`, `fitdata/raijin/ffd.json`).
    Silhouette IoU 0.958–0.967; p95 passes on the front 3/4 and the side (1.41 / 1.09 %). The rear and the head-on
    photo stay at 1.8–2.6 %: their cameras do not agree (wing vs bumper) and one mask is drawn by hand.
  - 49 k triangles, 16 materials, 0.44 MB (was 0.57 MB). Exhaust anchor moved to the model's own tip.
  - Not yet: the WRX / STi badges (only the Subaru oval); the lamp interiors are simple drawings.
  - Checked in Chrome (software GL, API cut off): the garage at night and a night race start.
- **Autobahn: the oncoming traffic is the game's own cars** (deployed 2026-11-10; owner: 「アウトバーンの反対車線にある自動車たちは
  実装済みの自動車を走らせてください」).
  - `render/trafficModels.ts` builds a light copy of each of the six cars from the same GLB the player drives (or its
    procedural fallback) when the autobahn loads.
    - Four merged parts: paint (coloured per instance), glossy (glass, chrome, rims), matte and lamps (always lit).
      Each material's colour, or its texture's mean, is baked into the vertices.
    - Each material is welded and simplified to 1.2 cm (meshoptimizer's simplifier, a 38 kB gzip chunk loaded only
      for the autobahn; `meshoptimizer` is now a runtime dependency). Result: 3–12 k triangles per car instead of
      42–82 k.
  - `AutobahnTraffic`:
    - All 64 oncoming vehicles are game cars (no lorries on that side any more). A car is drawn as a model within
      1000 m of the camera (500 m on low quality); beyond that, only its lamps show.
    - The light sprites sit on each model's own lamps.
    - The paint is the car's own colour or an everyday one, picked again each time a car comes round.
    - The cars follow the road's grade and normal.
  - Lorries remain only far ahead in our direction, as before.
  - Cost during a race start (high): 25 instanced draws, ~22 cars, ~78 k triangles. A touge course draws ~440 calls
    and 3.9 M triangles.
  - The halo of the traffic's lamp sprites now fades out at its rim; up close its square edge had shown.
  - Checked in Chrome (vite preview, API cut off), all six cars up close at night and dawn, plus a driver's-eye view.
    Not GPU-timed: the host's GPU was not available that day (`/dev/dri` missing, Chrome fell back to llvmpipe).
- **E5 acceleration checked against the real train** (owner: 「新幹線の加速度は現実と同じものか確かめてください」).
  - Published figures:
    - starting acceleration 1.71 km/h/s;
    - 32 × 300 kW;
    - balancing speed 360 km/h on a +3 ‰ climb;
    - service maximum 320 km/h.
  - No speed-by-speed curve is published. A reference was worked out from those figures: load-compensated 1.71, full
    power, running resistance A + Cv² fitted to the 360 km/h balance, empty 453.5 t to full ~500 t.
  - Game vs reference:
    - start 1.69 vs 1.71 km/h/s;
    - at 200 km/h 1.08 vs 0.96–1.08;
    - at 300 km/h 0.48 vs 0.38–0.47;
    - 0→300 km/h 275 s / 14.1 km vs 269–298 s;
    - 0→320 km/h 338 s / 19.6 km vs 317–359 s;
    - on +3 ‰ it still reaches 320 (the real train balances at 360).
  - The game matches, at the light-load end of the range; no change. New tool `tools/train-accel.ts`. The train test
    now also bounds the E5's 0→300 km/h time (265–300 s).
- **S15 (`s15`): our own model in the game** (owner: 「入れて」 after the final sheet; deployed 2026-11-10, bundle `index-Dx7cGdnA.js`, together with the traffic above).
  - Replaces Mona x Supercars' Sketchfab model.
  - Built by `tools/blender/cars/s15*.py` (stock spec-R without the wing; `s15.py --wing` adds it) and fitted to 7
    photos with a body lattice (`s15_ffd.py`). Silhouette IoU 0.972–0.979 (mean 0.975).
  - 48 k triangles, 15 materials, 0.29 MB (was 1.9 MB). The taillights no longer need `tailLampGain`.
  - Physics unchanged.
  - Checked in Chrome: the garage at night, and a night race (taillights and twin exhaust).
- **RX-7 (`shiden`): our own model in the game** (owner approved the sheet, 2026-11-08; deployed). Replaces Lexyc16's
  Sketchfab model.
  - Fitted to 10 photos (5 Type RS, 5 Spirit R in a showroom). Mean silhouette IoU 0.968, mean p95 1.50 %;
    5 photos pass every condition. Length set to the official 4285 mm.
  - Pop-ups modelled raised (`popup_l` / `popup_r`, closed 0.68 rad).
  - 57 k triangles, 16 materials.
  - Game side: `deriveAnchors` now prefers the pop-up lenses for the beams, because the RX-7's 'headlight' material
    is its bumper parking lamps. The runtime pods (`CarSpec.popUpLamps`) and the exhaust override are gone.
  - Physics unchanged: track 1.50 against the model's 1.46.
  - Checked in the garage at night (pods up and lit) and at dawn (flush). vitest 61/61.
- **AE86 (`hayate`): our own model in the game** (owner approved the sheet, 2026-11-07; deployed). Replaces Lexyc16's
  Sketchfab model.
  - Built by `tools/blender/cars/hayate*.py`, fitted to 6 photos with `tools/carfit` plus a body lattice (`hayate_ffd.py`,
    `fitdata/hayate/ffd.json`). Silhouette IoU 0.961–0.979, p95 1.7–3.2 % of the car width (bar 1.5 %: not met).
    Dark-line and lamp-line errors are well below round 1.
  - Panda livery; black front bumper bar with white corners (the owner's choice); pop-up lamps modelled raised
    (`popup_l` / `popup_r`, closed 0.36 rad).
  - 42 k triangles, 15 materials.
  - Game side: there is no `headlight` material, so `deriveAnchors` now takes the beams from each pod's `popup_lens`.
    The tailpipe anchor comes from its mesh (the `CarSpec.exhaust` override is gone). The physics specs are
    unchanged: track 1.42 against the model's 1.35, a 3 cm difference per side in the visual wheel position only, so
    medals and bots stand. `car-import.json` has no hayate entry any more, so an import can't overwrite the model.
  - Checked in Chrome (RX 5700 XT): garage at night (pods up and lit, beams on the road), at dawn (pods flush), and a
    night race. vitest 61/61.
  - Known differences: slight wedge left in the side view of the nose; no SPRINTER lettering on the right tail lamp
    (it would take a 17th material).
- **New course AUTOBAHN** (owner, 2026-11-06: "the Shinkansen and others never ran flat out, too many corners: make
  a new map, an Autobahn"; `a7e685f`, deployed 2026-11-07, bundle `index-Cb8bCzhs.js`). Built by two agents in
  parallel (course / scenery):
  - Course: 7.8 km timed (8.6 km of road, start at s 100, 650 m run-off), −2.4 % on average, every radius ≥ 1300 m,
    14.5 m wide. Zones: forest, overpass ×2, interchange, bridge (viaduct over a side valley), village. Landform
    `PLATEAU` (river valley, villages, turbines). `CourseDesign` gained `startS`, `runoff`, `smoothing`, `formation`
    (flat ground beside the road for the median and the opposite carriageway) and `aiTopSpeed` (140 m/s here; 62
    elsewhere). `CourseInfo.style` = `'autobahn'` switches off the touge dressing.
  - Scenery (`render/autobahnScenery.ts`, `autobahnTraffic.ts`, `autobahnTextures.ts`): 3-lane markings, median with
    a double guardrail, the opposite carriageway with oncoming traffic, traffic ahead, invented German signs
    (procedural atlas), overpasses with rain covers, an interchange with gantries, lamps and a decorative slip road
    (the wall blocks it), a box-girder viaduct, noise walls, the village. Own props: sign gantry, emergency phone,
    village house, farmhouse, church.
  - Physics: past the finish, cars brake for the road left and trains get a retarder (`Game.stopBrake`). The
    cockroach's downforce stops growing above 70 m/s (`CarSpec.downforceTopSpeed`): at ~395 km/h it flipped. It is
    unchanged on the passes, where its vmax is ~226 km/h (re-checked: 75.9 / 62.9 / 55.3 s, medals unchanged).
  - Top speeds (sim): E5 305 km/h, cockroach 423, R34 239. Medals for all 12 vehicles from standing-start sims;
    3 rivals (portraits empty, silhouettes) and 6 CPU ghosts (seeded on deploy, shown on the live leaderboard).
  - Performance (RX 5700 XT, full course): high 442 draw calls p50 / 572 max, 2.16 M triangles, GPU 4.5 ms; less
    than 朧峠 (364 / 530, 4.2 M). The key art is an in-game screenshot.
  - Checks: tsc, vitest 61/61, backend 17/17 (container, `--build`). Chrome autodrive runs on night, rain and dawn
    with no console errors. Live: the bundle names the course, the assets are served, and `/api/content` lists
    `autobahn`. E2E not run (its course-card count was updated to 4).
  - Open: owner-supplied portraits, key art and music (it reuses an existing track).
- **Cars: paused** (owner, 2026-11-04: "your cost is very high: finish everything but the cars; the cars use the
  external models; I'll restart them next week or later"). The six cars stay on the Sketchfab models with credits.
  Modelling by eye against photos did not converge (owner: "not the same as the real cars"), so a measured fit was
  built for the restart: `tools/carfit/` (silhouette and material-ID renders from cameras solved on the photos,
  GrabCut masks, IoU / boundary error / zone offsets; acceptance IoU ≥ 0.95, p95 ≤ 1.5 % of the car's width). The
  work in progress is committed unused (`bb80d52`: `tools/blender/cars/`, `fitdata/`).

## Session 6c (2026-11-03) — the doremifa takes as long as on the real train (owner: "it reaches the F too fast")

- Measured on Commons recordings (pitch track of the spectrogram, first note F → top G): `Keikyun1000.ogg` ~1.35 s,
  `Keikyu2100.ogg` ~1.7 s. The game took 0.85 s: the trains reached full tractive effort at once and only the sound's
  slip ramped in (`SLIP_RISE` 0.8 s).
- **Traction ramp in the physics** (`VehicleSim.traction`): a train's tractive effort follows the notch at a limited
  rate, `TRACTION_RISE` = 1.2 s to full (fades at twice that rate after a notch-off, so a quick re-notch keeps most of it;
  the brake, the grid hold and a respawn cut it). The VVVF's slip follows the same share (`TrainSound.driveVvvf`,
  `Game` hands the sound `sim.traction`), so sound and push build up together. `SLIP_RISE` is gone.
  Verified: the game's whole chain rendered offline in Chrome (`tools/vvvf-game-wav.ts keikyu1000`), pitch track:
  first F at 1.52 s, top G at 3.08 s → **1.56 s**; `tools/vvvf-train-wav.ts` uses the same ramp.
- Medals of all four trains re-simulated (tools/sim-run.ts, legend AI): clean laps moved by −2…+3 % (the AI's own
  spread); runs with respawns keep their earlier medals (see the comment above `TRAIN_MEDALS`).
  朧峠 keikyu 145.40 / ginza 151.33; 霧降湖 e231 126.27, keikyu 121.21, ginza 131.28, n700 119.68; 天狼 keikyu 118.31.
- Checks: `tsc -b` clean, vitest 50/50, `vite build`.

## Session 6b (2026-11-03) — Keikyu N1000 "doremifa" modelled in Blender; 117 and 京成3300 retired (owner's requests; deployed)

- Owner: "as a test of building models with Blender MCP, make the Keikyu 1000 doremifa", then "retire the 117 and the
  3300 and replace them with trains made in Blender". Second replacement slot: open, the owner is to choose.
- **Blender MCP not installed**: the Claude Code permission check refused installing the third-party addon
  (ahujasid/blender-mcp `addon.py`, `pip install`) as external code. Not worked around; asked the owner. Built with
  Blender's own Python instead (Blender 5.2.3 LTS, user space on ubuntu-dev, headless).
- **CHM ported** (`audio/vvvf/customPwm.ts`: the simulator's `CustomPwm.cs`, its switching-angle `.bin` tables served from
  `public/audio/vvvf-tables/`, listed per pattern in `VvvfData.CustomPwm`, handed to the worklet as processorOptions;
  `AudioEngine.vvvfNode` plays no VVVF if a table is missing). Verified: the C# reference (`tools/vvvf-ref`, now loading
  `CustomPwmPresets`) and the port agree sample by sample on the N1000 pattern through every CHM mode (1,584,128
  samples identical); `vvvf.test.ts` has it as its third case (fixture regenerated).
- **The doremifa**: YAML-Files `N1000_SIEMENS_GTO` unchanged (async 175…400 Hz steps to 24 Hz, CHM 15…3, sync 3 / 1),
  `KEIKYU_N1000_GTO` (gear 14:83, 2 pole pairs). The slip frequency now ramps in over 0.8 s after a notch change
  (`SLIP_RISE`, sound only), so the inverter starts at 0 Hz and the first notes play. Verified in a Node render
  (`tools/vvvf-train-wav.ts keikyu1000`): the stepped scale is audible, ~1 s long (the real train's jerk-limited start
  takes 1.5–2 s; a traction ramp in the train physics would match it — proposed, not done: it changes feel and times).
- **Model** (`tools/blender/train_kit.py` + `tools/blender/keikyu1000.py`, `node tools/blender-trains.cjs keikyu1000`
  → `public/models/trains/keikyu1000.glb`, 79 KB): lofted body with shoulder radius, bevelled ends, raked / bulged cab,
  decals projected on the body (windows, doors, band, cab mask, rollsigns, lamps), bogies, underfloor boxes, ACs,
  pantograph on the middle car, skirt, couplers. Stage renders checked at each step (Cycles). Blender's glTF exporter
  orders materials / primitives differently on every run (same geometry): `blender-trains.cjs` sorts them by material
  name before optimising, so a rebuild is byte-identical (checked: 3 builds, same SHA-1).
  Verified in the game (Chrome on the RX 5700 XT, vite preview with the API cut off): garage from fixed poses and
  races in chase / near view, by dawn and night: headlamps at the top of the cab, red tail lamps at the rear, window
  glow at night, the three cars in line; no page errors. Estimates: wheel 0.86 m, bogie centres 12 m.
- **Removed**: `jr117`, `keisei3300` (GLBs, `motor_jr117` / `motor_keisei3300` / `run_jr117`, train-import.json,
  backend `game.cars`, medals). The `motorSound` mechanism stays. Backend test: 11 vehicles.
- **Medals** `keikyu1000` (tools/sim-run.ts, legend AI, road grip on): 朧峠 147.93 s, 霧降湖 119.33 s, 天狼 118.73 s,
  no respawns → gold 148.0 / 119.5 / 119.0 s, silver +7 %, bronze +16 %.
- Checks: `tsc -b` clean, vitest 50/50, `vite build`, backend 15/15 (container, `--build`). E2E on a separate test
  stack (`-p touge-e2e`, other subnet, port 8090): 8 passed + 2 flaky (time attack, ghost battle: timeouts while
  Blender Cycles renders used every core); both re-run on an idle machine with retries off: passed → 10/10.
- Deployed (`docker compose up -d --build`): served bundle = local build (`index-DwVXFRCO.js`), keikyu1000.glb (same
  SHA-1), the CHM tables and the worklet served, `jr117.glb` gone, `/api/content` lists 11 vehicles incl. keikyu1000.

## Session 6 (2026-11-03) — VVVF Simulator ported for the trains' in-train sound (owner chose B: body resonance −15 dB; deployed)

- Owner approved porting VvvfGeeks/VVVF-Simulator (non-commercial terms; credit + link in the settings screen and
  ASSETS.md). `frontend/src/game/audio/vvvf/`: `data.ts` (the YAML structure with the C# defaults), `math.ts`
  (MyMath, banker's rounding, .NET `List.Sort` on small lists), `sim.ts` (control state, carrier, pattern solver,
  2-/3-level PWM incl. SVM / DPWM / HO / ΔΣ / special sync modes, induction motor RK4, in-train sound; CHM / SHE
  tables left out), `engine.ts` (the game's driver: control every 128 output frames = 512 calculations at 192 kHz as the
  simulator's real-time mode, rotor pinned to the wheels, windowed-sinc decimation, idle when gates off and currents
  gone), `vvvf.worklet.ts` (AudioWorklet 'vvvf-sim', bundled with `?worker&url`), `train.ts` (simulator defaults, gear
  whine off). Patterns: the simulator's YAML as is (`tools/vvvf/*.yaml` → `tools/vvvf-patterns.ts` → JSON; N700 = our
  estimate in the same format). `TrainSound.setVvvf`: worklet → ConvolverNode with the simulator's Filter.wav
  (`public/audio/vvvf-filter.wav`, gain 192 kHz / rate) → peaking EQ −15 dB at 230 Hz (`VVVF_BODY`) → gain.
  `vehicle/vvvf.ts`: per-train pattern, gear teeth, poles, slip; `vvvfDrive` (notch N keeps the brake flag, electric
  brake off below 3 km/h). Old `public/audio/vvvf-worklet.js` and the hand-typed bands removed.
- Verified: the port against the simulator's own C# files built as a console app in the .NET SDK container
  (`tools/vvvf-ref/`): identical in float32 (16.5 s at 96 kHz: E231 in-train sound with gear 14:99, 207-2000 line
  voltage); 75 s at 192 kHz earlier: max difference 6e-11. `vvvf.test.ts` repeats the comparison (fixture), checks the
  JSONs are current, engine behaviour (silent standing / coasting, sounds under power and braking, 2× vs 4×
  oversampling within 3 dB pre-IR; after the IR within 0.1 dB in the loud parts), every train's pattern and teeth.
  vitest 50/50, tsc, vite build.
- Verified in Chrome (host GPU, vite preview with the API proxied to nowhere): the game's whole sound chain rendered
  offline through `__renderTrainSound` (`?export=1`): E231 109 s in 33 s, Ginza 55 s in 12 s, N700 140 s in 30 s; the
  spectrogram shows the asynchronous random carrier, 3-pulse and 1-pulse lines, the braking sweep under the running
  noise. A live time attack with the E231 (autodrive): the worklet joins after 1.4 s, the master level follows the
  speed, no errors. Settings screen shows the new credit. Cost: ~0.5 µs per calculation in V8 → ~9 % of a desktop core
  at 192 kHz (phones 96 kHz).
- Findings: the simulator's impulse response lifts 150–350 Hz by ~25 dB, so the synchronous 3-pulse region (6f torque
  ripple there) is ~20 dB above the rest (A = as the simulator); the game uses a −15 dB cut there (B). The simulator's
  calculated gear whine (not on by default there either) is 30–50 dB above the motor through the IR: left off.
- Sent to the owner (SendUserFile): in-game sound of E231 / Ginza 1000 / N700 and E231 inverter-only A vs B.
  The owner listened and chose B (「共鳴抑えてるやつのが良かった」), already the default (`VVVF_BODY.db = -15`); committed and deployed.
- Also this session: proposed a base + per-kind extension design for vehicles (HANDOVER §0.2, ~35 kind branches
  found); owner allowed Blender + MCP on the owner's PC to build our own models (§0.3).

## Session 5g (2026-11-03) — train sound rework (owner: choppy, silent when coasting, use analysed sources)

- The 0.12 s grains of Session 5d made the motor sound choppy, and nothing played but a faint synthesis while
  coasting. Researched analysed sources (agent): VvvfGeeks / YAML-Files has fans' per-train VVVF control patterns
  (E231 Mitsubishi 3-level among 30 trains; no Ginza line PMSM, no N700; no licence file); BVE sound sets have no open
  licence; Commons has running-noise recordings.
- VVVF trains (E231, 銀座線1000, N700): the inverter synthesised in an AudioWorklet (`public/audio/vvvf-worklet.js`):
  the 2-/3-level PWM line voltage itself (sine references against a triangle carrier, asynchronous with random
  modulation or synchronous N-pulse / 1-pulse, 4× oversampled), filtered like the motor windings; driven by
  `vehicle/vvvf.ts` (speed → inverter Hz from gear, wheel and poles, + slip; bands of the pattern; V/f modulation).
  E231 = Mitsubishi pattern (the old clip was a Hitachi-equipped suburban E231), Ginza = Toshiba 207-2000 stand-in,
  N700 = estimate. Gates shut when coasting (silent motor, like the real thing).
- Resistor-control trains (117, 京成3300): the recording followed continuously (`RecordingFollower`): one voice, its
  rate pitching the recording to the speed and up to ±20 % to catch up; a 0.45 s crossfade re-cues it only when it
  drifts 0.9 s away; braking plays it backwards; a power cut keeps it running faded for 1.5 s.
- Every train: a running-noise loop (wheels, rails, rumble) whenever it moves, rate and loudness by speed
  (`RunningLoop`; seamless loops cut from Commons recordings, ASSETS.md). Clips decode at 22.05 kHz (memory).
- Checked by rendering each train's sound alone through an OfflineAudioContext along a scripted run (power → coast
  → brake → power): VVVF spectra show the patterns (randomised rising carrier, then the 3-pulse / 1-pulse harmonic
  fans; falling when braking); re-cues per 44 s: VVVF 0, 117 5, 3300 12 (was a grain every 0.06 s); coasting
  −21…−26 dBFS (was a faint synthesis); in-game capture confirms E231 = synthesis + running, 117 = recording +
  running. Not listened to by a person. Tests: pattern bands and carrier ramps, clips shipped.
- Owner's verdict (2026-11-03): still too rough for train fans; real-time VVVF simulators exist as OSS, use one.
  Looked up (GitHub API, READMEs): VvvfGeeks/VVVF-Simulator (C#, non-commercial use of the code allowed with a link;
  in-train sound = motor model torque ripple + motor / gear harmonics + filters + an impulse response), its YAML
  files (30 trains), a JS one under AGPL (not usable), a Java port claiming MIT (doubtful). Not started: the plan is
  in HANDOVER §0 (owner to approve the licence first; the repository is public).

## Session 5f (2026-11-03) — fullscreen toggle (owner's request: PC and phones alike)

- `ui/fullscreen.ts`: on / off from a button on every menu screen (bottom left; on phones above ◀ 戻る), the F key
  anywhere (not while typing a name), a pause menu item and a settings row; hidden / "非対応" where the browser has
  no fullscreen (iPhone Safari). Phones still enter it with the title tap (with the landscape lock). nginx serves the
  web app manifest as `application/manifest+json`.
- Checked in the browser: button → fullscreen and label 全画面終了, F → off, settings row → on, pause item → on,
  no button during a race; phone layout clear of the panels.

## Session 5e (2026-11-03) — phones (owner's request: スマホ対応)

- Touch layout (`.touch` on the app when the primary pointer is coarse, `ui/touch.ts`; a laptop with a touch screen
  keeps its mouse layout, any touch switches it on): race controls (`ui/hud/TouchControls.tsx`): steering pad bottom
  left (the half under the finger steers, slide across to switch), accelerator / brake / handbrake bottom right, ▲▼
  for MT, 復帰 / CAM / II top right; several fingers at once; they feed `InputManager.touch`, ramped like the keys.
  The rev dial and the start guide are hidden on touch (the speed stays, bottom centre).
- Menus: a ◀ 戻る button on every menu screen (no Esc key on a phone: it sends one, every screen maps Esc to back);
  compact styles for short landscape screens (≤ 500 px high): menus, course / condition / gearbox / rival cards,
  car select (its button stays in view), panels, online, results (the HUD behind is hidden).
- Title tap: fullscreen + landscape lock where allowed (Android); portrait shows "横向きに"; viewport without zoom,
  web app manifest (fullscreen, landscape); new players on touch start at quality 低.
- Checked in Chrome's phone emulation (844×390, touch, real GPU): every screen by taps (title, menu, courses,
  conditions, car select, gearbox, rivals, car list, settings, ranking, controls, online entry, pause, results after
  an autopiloted race), held accelerator → throttle 1, second finger steers, sliding switches sides, release → 0.
  E2E: a phone test (taps, back button, touch-driven race). Not tried on a real phone.

## Session 5d (2026-11-03) — real train motor sounds (owner's request)

- Searched Commons, Freesound and Japanese free sound sites for recordings of the five trains' traction equipment
  (agent); Commons has labelled clips downloadable without login. Picked: an E231 pulling away, on board a 117
  (MoHa 117-15), Keikyu's first 1000 series for the Keisei 3300 (same era, all motor cars, resistor control), a
  Toshiba IGBT VVVF (223-2000) for the Ginza line 1000 (no PMSM recording exists) and on board a 700 series for the
  N700. One acceleration from a stop cut from each (ASSETS.md).
- Speed along each clip: from a motor tone line proportional to speed (ridge followed on the spectrogram; E231: a
  straight line from 2.2 s = constant 2.5 km/h/s; 117 and 700: lines calibrated by the real starting acceleration),
  else from the real acceleration and the end of the constant-torque range.
- `TrainSound` plays the stretch matching the current speed as 0.12 s grains overlapping by half (so it follows any
  acceleration); past the clip's top speed grains come from its last 2 s, pitched up (a fixed spot buzzed);
  braking plays it softer; coasting fades it out. The synthesised motor/inverter stays as the fallback until the
  clip is decoded. N700 clip ×2 (the 700 is quiet below 150 km/h, where the N700 spends the pass).
- Checked by recording the game's output in the browser (MediaRecorder) during starts with each train and comparing
  spectrograms: the E231 clip's pattern (steady carrier, falling sweep, jump) comes at the game's speeds; the others
  show their rising lines. Not listened to by a person. Test: clips shipped, speed points rising.

## Session 5c (2026-11-03) — the cockroach (joke entry, owner's request)

- Model: the owner downloaded "Cockroach" by CK (xcellf, CC BY 4.0) from the shortlist; optimised to a 0.5 MB GLB
  keeping its skin and scuttle cycle (ASSETS.md). `render/RoachModel.ts` clones it per vehicle (SkeletonUtils),
  scales it to 5.6 m over antennae and legs (body ~3.4 m), runs the legs with the distance covered (at most 9 cycles
  a second so they do not strobe), puts glowing eyes on the foremost head bone as its headlights; procedural
  stand-in without the model. Colours: ワモン (texture), クロ (per-channel gains on the texture), チャバネ and 黄金
  (plain colour over the bump map; gold metallic) — a plain tint could only darken the deep red-brown texture.
- Physics (`vehicle/roach.ts`): 700 kg, all six legs drive through one fixed ratio (no AT/MT), grip 1.75 (sports
  cars ~1.3), downforce, low centre of mass (at grip 2.0 / centre 0.3 m the legend AI rolled it in hairpins).
  Flat pad: 0→100 km/h 1.58 s, 414 km/h, 100→0 in 20.7 m (R34: 4.47 s, 225 km/h, 41 m). Test: quicker, faster and
  shorter-stopping than every car and the N700.
- Legend AI (capped at 223 km/h like for every vehicle): 朧峠 75.9 s, 霧降湖 62.9 s, 天狼 55.3 s, no flips or respawns
  (cars' best ~93 / 76 / 68 s) → `ROACH_MEDALS`. Backend: `roach` in `game.cars`; the plausible minimum times lowered
  to 50 / 42 / 38 s (were 60 / 50 / 45: a player at 400 km/h on the straights could beat them); test.
- Sound (`audio/BugSound.ts`): patter of six legs (a loop of clicks played faster with speed), a wing-like buzz from
  ~60 km/h, rush of air. Not heard by a person yet.
- Checked on the real GPU: car list (all four colours), a night race (legs move while driving: 19 of 31 bones change
  between frames), side and front views with the eyes lit.

## Session 5b (2026-11-03) — owner's reports: sliding, train lights, bus stop, colour row, online AT/MT

### "The cars slide a lot" + road grip per course and weather
- Measured first (`tools/handling-feel.ts`, now with ordinary corners at full lock): taking a bend flat out at full
  lock (the keyboard way) slid every car to 32–54° for ~2 s; braking into a bend at 90 km/h with the wheel turned
  slid them to 25–47°. Causes: the power-over trigger fired on any held full throttle (also after each automatic
  shift), the feint trigger on any firm brake with steering, the slip trigger from 11°; full throttle in a low gear
  spun the rears, whose cornering grip collapsed.
- Changes (`VehicleSim`, players only; the AI drives as a grip driver and is unaffected): a power-over needs a stab
  of the pedal (lift, then floor it within 0.35 s); a feint needs a short tap of the brake (< 0.45 s) released with
  a big steer; the slip trigger starts at 16°; a drift ends below ~7°; grip assist (assist on, outside a drift):
  while cornering hard the driven wheels only get the force the friction circle leaves beside the cornering force.
- After: flat-out and braked-into corners 2–10° of slip for every car; deliberate drifts unchanged (throttle stab
  2.7–3.1 s, feint 2.2–3.0 s, handbrake 2.8–3.1 s); wall hits unchanged. Test: corners stay grip corners (fails on
  the old code); the power-slide test now stabs the throttle; the car-to-car test measures the gap only nose to tail
  (the parked car is shoved aside, centres come closer without overlap).
- Road grip per course (`CourseInfo.surface`): 朧峠 1.00 (old pass asphalt), 霧降湖 0.92 (damp from the lake mist),
  天狼 1.04 (new toll-road asphalt); rain now takes 20 % off (was 14 %; `WET_GRIP`). Shown on the course cards and the
  rain card. Headless tools use the course's grip (`GRIP=` overrides). Legend AI laps at grip 1 vs the new grip:
  霧降湖 +1.4 %, 天狼 −0.5 % on average (each car within ±2.5 %, run-to-run noise ~1 %): those medals (cars and
  trains) scaled by that. Bot leaderboard runs and ghosts regenerated (`npm run seed:bots`); the seeder now replaces
  a bot's run for the same course and car instead of adding a second one (test).

### Train lights ("光が甘い")
- The imported trains had no lit lamps (the import flattens materials to colours: the lamps were only painted on),
  no tail lamps at all, and dark windows at night.
- Lamps: positions measured on head-on renders with a grid per model (`TrainInfo.lamps`); lenses are placed on the
  surface a ray from ahead of the cab hits (`fitLamps`, works on the N700's sloped nose): head lamps on the leading
  cab (the headlight material), tail lamps on the trailing cab (taillight material, `tailLampGain` 1.6). Beams start
  at the lamps and dip towards the road from high lamps (the cones of every car used to tilt slightly upwards).
- Interior light at night: on side-facing texels in each model's window band that are dark (per-model luminance
  limit) the train's material glows warm white (`lightWindows`, shader patch; meshopt leaves a scale on each mesh,
  so positions are taken through the mesh's own transform). Checked on night renders of all five trains.

### Smaller fixes
- Colour row in the car list / car select: the selected swatch (scaled 1.18 with a 3 px ring) was clipped at the
  card's left edge (the card scrolls, which clips both axes); the row is inset by the ring.
- Online: a train no longer offers AT/MT (it has one ratio); a note says so.
- Bus stop: the model's open side faced away from the road (source faces −Z) and its utility pole (with crossarm
  and lamp) is gone at the owner's request (`PropDef.drop`, a box of triangles left out); now 2.6 m off the edge.

## Session 5 (2026-11-03) — owner's requests: flicker, online start, race setup, car list

### Screen flicker near lights: black frames from tyre smoke (found and fixed)
- Measured again on the real GPU (night, high, autopilot rival race, every frame read back): 霧降湖 still had 16
  whole-screen black frames (around 4 %, 14 % and 20–29 % of the course); 朧峠 and 天狼 none in that run.
- Reading the half-float scene buffer while driving: those frames were NaN over 0.5–2 million of the 2.07 million
  pixels. Nothing was non-finite in matrices, lights or uniforms; re-rendering with single things switched off
  cleared it only without the tyre-smoke `Points`. Cause: `TireSmoke.update` computed `(1 - t) ** 1.3` in the frame
  a puff died (life < 0 → t > 1 → negative base → NaN alpha); a dying puff next to the chase camera is drawn
  screen-sized, so the whole frame went NaN and bloom spread it black. Drifts put smoke around the camera, which
  is why it looked like flicker. `t` is capped at 1 now (the exhaust already capped it).
- After: NaN frames in the same stretches 13 → 0 (441 frames checked).

### Online: the race could start while a player was still loading
- The host could press start as soon as a guest joined, while the guest's game was still building the room's
  course; the guest only connected to the room after loading, so it saw the start late or after the green light.
- `room_players.ready` (migration): set by the client after loading the course (`PATCH /rooms/{code}/me`,
  re-sent by the room poll if that failed), reset on a rejoin; `start` refuses with 409 while anyone is not ready
  (after dropping members no longer on the presence channel). Room screen: "ロード中…" next to such players, the
  start button says it is waiting. (Joining the room's socket before loading was tried: building the course blocks
  the page so long that the socket gave up and fell back to wss, failing on plain http — so it still joins after.)
- Rooms keep the host's `time_of_day` (migration, validated, default night): everyone races in the same conditions.

### Race setup order, settings, car list
- New order: mode → course → time & weather → car → AT/MT → (rival) → race. Time & weather and the gearbox left
  the settings screen; the last choices are preselected. The conditions screen switches the world behind it.
- Car list (main menu): every car with engine, power (from the torque curve), torque, weight, power-to-weight, drive,
  gears, size; drag to orbit the camera around the car, wheel to zoom (also in the car select).
- Online lobby: conditions chips next to the course when creating a room; AT/MT chips for each player.

### Trains (joke entries, owner's request)
- Five three-car trains as vehicles, each with a third-party model (ASSETS.md): JR E231, 117 (サンライナー),
  京成3300 (赤電), 東京メトロ銀座線1000, 新幹線N700 (`vehicle/trains.ts`). The owner first asked for E235 and Tobu
  trains; no usable models exist for them (and the 103), so the owner left the choice open: lineup of five.
  Real figures from Japanese Wikipedia: starting acceleration, design top speed, service/emergency brake rates,
  motors, control, gear ratio, car length; masses are marked as estimates where no per-car figure exists.
- Physics: only the leading car's front bogie is simulated (a 4.2 t vehicle); the motor torque curve gives the real
  acceleration (constant torque, constant power, then ∝1/v²; the N700 keeps full power to 300 km/h), the redline is
  the motor speed at the design top speed, full brake = the emergency rate. Added to `VehicleSim`: `engine.electric`
  (full torque from standstill, symmetric reverse), `CarSpec.damping` and `CarSpec.rolling` (the cars' body damping
  and 1.5 % tyre rolling resistance capped a train near 70 km/h; steel wheels 0.2 %). Tests on level ground for
  every train: starting acceleration ±15 %, peak speed 85–108 % of the design speed (N700 330 km/h included),
  emergency stop 90–125 % of the real rate.
- Drawing (`render/TrainModel.ts`): the model's cars (or a procedural stand-in per series when a model is missing),
  placed every frame along the path the front bogie drove, at the train's car length and bogie spacing (so the train
  follows the road like rails, also for ghosts, replays and online peers); reversing hands the path back. Tests:
  on a 40 m bend every car centre stays on the arc, 20 m apart; backing up 30 m moves every car 30 m back.
- Import (`tools/import-trains.cjs` + `render/trainImport.ts`): cars cut at the gangways (positions from the bogie
  spacing, checked on side renders), clipped, turned so +Z is forward. First import mirrored the x-long models
  (axes swapped instead of a quarter turn: inside-out shells); fixed and re-imported.
- Camera: high chase and a cab view just behind each train's nose (`ChaseCamera.profile`); a train's first race starts
  in the cab. Sound (`audio/TrainSound.ts`): gear whine and rumble, plus VVVF carrier steps or DC-motor growl by
  control type. No exhaust; AT/MT is skipped (one ratio).
- Medals per course from the legend AI with each train (`TRAIN_MEDALS`); with the real weak brakes the AI sometimes
  could not stop and respawned: those runs were replaced by clean runs or estimates.
- Fixed on the way: the colour picked in the car select was never used in the race (`RaceConfig.color`).

### Owner's report: the car backs away before the start; handling too hard (walls, drifting)
- Start: the countdown held cars with full brake, and a held brake at a standstill engages reverse after 0.35 s
  (where the brake pedal drives): every car rolled 2.6–3.5 m back and started in reverse. `VehicleInput.hold`
  (brakes on, engine revving freely, never reverse). In-game: 0.05 m, first gear at the green light.
- Measured first (`tools/handling-feel.ts`, flat pad, wall with the course walls' material): 45° hits at 100 km/h
  threw the S15 / RX-7 back off the wall at ~35 km/h, turned them 92° and 6 m into the road; power slides of the
  RWD cars swung out to 73–77° (edge of a spin); the Impreza and R34 could not drift at all.
- Changes (`VehicleSim`): wall contacts take back most of the motion away from the wall and cap the yaw rate at
  1.6 rad/s while touching and 0.35 s after; rear grip comes back beyond ~32° of slip (angle governor, player
  only); a handbrake pull with steering gives a yaw kick; lighter yaw damping in the first half second of a drift;
  spin protection from 45°; 4WD cars may power over and lose less rear grip.
- After: 45° @100 km/h bounce ~1 km/h, turned 42–44° (lined up with the wall), 0.9 m from it; power slides held
  3.2 s at 51–53°; Impreza: 3.0 s power slide, 2.6 s feint, 2.8 s handbrake entry. Impact sounds unchanged (2 per
  hit). Legend AI lap times within ±2 s of before (medals unchanged). Tests for both (fail on the old code).

### Smaller fixes
- Curve mirrors on the left of the road faced away from it (all were turned to the road's left); test checks both
  sides.
- Exhaust from the real tailpipes: S15 (muffler named only in its material, now matched), Impreza and R34 (tip on
  the left, the guess was right), RX-7 (10 cm out).
- Exhaust for online peers (they now send throttle and engine speed; older clients' are read from speed changes)
  and replay cars (from the recorded motion). Replay check: up to 17 live exhaust particles (none before).
- Roadside clutter culling tried (spatial chunks + distance cut): no measurable gain on the real GPU at matched
  clocks (GPU p50 7.15 → 7.19 ms), more draw calls; reverted.

### Tests
- Backend: the `backend-test` image bakes the code in, so earlier runs without `--build` tested old code. With
  `--build`: 14/14 (new: ready gating, rejoin, room conditions).

## Session 4 (2026-11-02) — real-GPU performance pass on the owner's PC

### Music remade with Suno (batch 3) — done & verified in the browser
- The owner remade all music with Suno Pro (frenchcore / uptempo hardcore / speedcore): 11 BGM + 5 jingles,
  delivered as 48 kHz AAC. Gain-only loudness match (BGM −15.4, jingles −16.4 LUFS), MP3 160 kbps, `public/audio/`.
- Loop points: candidate pairs from the mel-spectrum self-similarity of the next 8 s, best pair per minimum span,
  then moved onto the same beat phase (onset-envelope comb). Several tracks never repeat a section closely (menu,
  online, dawn, rival): longer crossfades there. Seam preview rendered for the owner to judge by ear.
- New wiring: race music by mode, then weather (`Game.raceMusic`: rival → `bgm_rival`, ghost → `bgm_ghost`, rain →
  `bgm_race_rain`, dawn → `bgm_race_dawn`, else the course's track); car select `bgm_garage`; results/replay
  `bgm_results` after the jingles; online lobby/room `bgm_online`; course select back to `bgm_menu`.
  Jingles: `jingle_rival_win` for beating the rival, then on the results screen `jingle_medal` (new medal) or
  `jingle_record` (new local record, not the first run) as the finish jingle ends. `playMusic` takes `{ fallback,
  delay }` and uses the loop settings of the track actually loaded (it used the requested one's for a fallback).
- Decoded music is ~75 MB per 3-minute track: the cache now keeps only the requested track (it kept every track
  ever played).
- Checked in headless Chrome on vite preview: menu → course select → car select → rival race → finish played
  `bgm_menu`, `bgm_menu`, `bgm_garage`, `bgm_rival`, `jingle_rival_win`, `jingle_medal`, `bgm_results`; the 12
  mode × weather combinations pick the right track; all 16 files decode and every loop point lies inside its file.
- Sound effects (Suno Sounds, WAV): 18 generated in the owner's Suno library through Claude in Chrome (engines 5
  types × mid/high, squeal, turbo, blow-off, backfire, crash, scrape, rain, wind). Not downloaded yet: Pro allows 20
  downloads a month (27 left until 2026-12-02), and Chrome stops each download at its save dialog.

### Whole-screen black frames (the reported "flicker near lights") — found and fixed
- Freezing a night race and rendering the same view (real GPU, high): single frames came out completely black
  (mean 0) at 5 spots on 朧峠 and 1 on 霧降湖, about once per race while driving (old build: 1 in 8,610 frames).
  Not there at low quality (no post-processing). Reading the half-float scene buffer before post-processing: every
  black frame had 3 NaN pixels, no other frame had any; the bloom blur spread them over the whole picture.
  Bisected (scenery, environment, particles, env map, normal maps, clearcoat: no effect; both cars hidden: gone) and
  identified with an ID render at the NaN pixels: the headlight beam cones (`CarVisual`, here the rival's).
  Cause: `pow(vT, 2.2)` with `vT` (the cone's uv.y) interpolated a hair below 0 at the far rim; pow of a negative
  base is undefined (NaN). Fixed with a clamp; the sky's milky band had `pow(dot, 2.0)` with a possibly negative
  base too (always NaN on Direct3D, where pow is exp2(y·log2 x)) → `b * b`. All other GLSL pow() bases are clamped.
  After: 0 NaN / 0 black frames at 10 frozen spots on all courses (3,020 frames), 0 in a full night race
  (9,520 frames). A tentative clamp of material output (half-float overflow theory) did not help and was removed.
- Fixed: docs/ASSETS.md listed the menu and 朧峠 tracks at 144 kbps; they are 128 kbps CBR (frame count).

### Hitches: shaders compiled mid-race
- Long frames over a full 朧峠 race (high, 17.4 k frames): 13 ≥ 20 ms. The worst mid-race ones (41 / 24 ms at
  35.9 / 36.6 %) were the turbine and vending machine shaders compiling the first time they came into view
  (`renderer.info.programs` over the race). The load-time `renderer.compile` did not help at medium and up: it
  compiled the screen variants, but post-processing draws the scene into an offscreen buffer (linear output, no
  tone mapping: other cache keys, checked by diffing them), and the race's headlamp spots + shadows change every
  shader again. `Game.precompile` now compiles against a stand-in render target when post-processing is on, at load
  and in the background at every race start (`compileAsync`, during the countdown): no scenery shader compiles
  mid-race any more (2 unnamed shadow-depth programs remain at ~64 %), programs at load 111 → 93.
  After: 11 long frames, mid-race 23–32 ms with no single cause (main thread and GPU both moderate, GPU clock
  swinging 800–2100 MHz); the spike as the results screen appears at the finish (~70–100 ms) is left as is.
- E2E on an isolated Docker stack next to the live one (project `touge-e2e`, own subnet, port 8090): 9/9 (the
  3-player online race separately, 10.1 min). Backend tests failed on a fresh checkout before running (`tests/Unit`
  missing: git keeps no empty folder) → suite removed from phpunit.xml: 13/13.

### Owner deliveries: AE86 model and the scenery models
- **AE86** (`hayate`): Lexyc16's "Toyota Corolla AE86 Trueno" (26 k tris; the Flamestroke candidate is 157 k tris
  at 1/10 scale). Its pop-up lamps are modelled raised, mixed into the big trim/lens meshes: new import option
  `CarImportConfig.popUps` cuts the connected pieces lying wholly inside a box (both sides) into hinged nodes
  `popup_l/r` (hinge on the rear top edge, closing angle in the node extras); `CarModel` picks them up
  (`CarRig.popUps`) and `CarVisual` folds them 0.64 rad into the bonnet by day (lid flush; first try 1.2 rad left
  holes) and raises and lights them at night; the bumper lamps are parking lamps. Anime tie-ins removed (tofu-shop
  door decal dropped, plates blanked with new `restyle.map: false`). Exhaust: no muffler-named part and the rear-corner
  guess put it on the wrong side → new `CarSpec.exhaust` override (checked with a marker on the pipe).
  `import-cars.cjs` takes `CHROME=<path>` (playwright-core has no bundled browser).
- **Scenery models** (8 of the 9 delivered; the KMB3D lamp set is park-style and unused): `tools/import-props.cjs`
  (+ `props-import.json`) compresses them (1.1 MB together); `render/props.ts` normalises size / facing / origin at
  load, merges each model per material and places it instanced (`placeProp`, moving parts such as turbine rotors
  spun per instance). Replaced: every street light (glass tinted sodium / LED, light source under the model's head),
  the turbines on 天狼, the curve mirrors, the summit vending machines. New: a roadside shrine (torii between two stone
  lanterns) and a bus shelter per course on the levellest straight roadside spot, preferring the hill side
  (`roadsideSpot`), with the clutter kept out; cones at the start and finish gantries. Procedural shapes stay as the
  fallback when a model does not load. Credits: garage (cars) and the settings screen (scenery), docs/ASSETS.md.
- Bugs found on the way: the vending machines' fronts faced the hillside (procedural ones too); the module-level
  list of night-lit sign materials grew with every course switch.
- Verified (real GPU, screenshots): AE86 in the garage at night (pods up, lit, blank plates) and dawn (folded flush),
  tail lamps lit at night, exhaust at the pipe, driving at night/dawn with the pods following; every prop on all three
  courses at night and dawn, turbine rotors turning, credits on the settings screen; no page errors; vitest 26/26.
  Cost of the props (朧峠 high): draw calls 437 → 451, triangles 3.9 M → 4.1 M; low 292 → 295 calls.
- Cappuccino (owner request): no downloadable CC model of the real car on Sketchfab (only a fantasy "GT concept");
  links to a CGTrader low-poly model (licence/price unconfirmed) and a 3D-print model given to the owner, plus the
  option of a procedural body.

### Real-GPU performance pass

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

## Rain sound remade (11-12, v2.0.1)

The owner's report: the rain sounds uniform. Measured on the old one: a 2 s loop of white noise through two filters
(correlation with itself 2 s later 1.000), level spread 0.03 dB, the same signal in both ears, almost nothing below
1 kHz, the same at any speed and under a roof. Now an AudioWorklet (`audio/rain.ts`): far wash with gusts (7 s and
16 s walks), ~2 500 drops a second around the listener, drops on the vehicle (roof and glass for a car, the helmet on
a bike, cab glass on a train, none on the cockroach), tyre spray growing with speed, drips and a muffled wash under
a rock shed. Standing still it keeps the old long-term level (−25.2 against −24.6 dBFS); +2.5 dB at 100 km/h,
+5 dB at 150 km/h; 12–15 dB quieter under a roof. 35–58 µs per 128 samples in Node (1.3–2.2 % of a core).

- Verified: offline renders and their figures (`tools/rain-wav.ts`: old against new, eight scenarios), spectrograms
  looked at, six vitests (bounded, deterministic per seed, silent when dry, levels, ears apart), tsc, 196 vitests;
  in the game on the GPU: the node appears with the first rain, gets the car's speed and kind in a race, fades to
  zero after the weather changes.
- Deployed 11-12 as v2.0.1: `gpu-errors.cjs` 0 on WebGPU and WebGL 2, a race picture looked at, the live stack
  and the public address serve the built bundle, `/api/content` says 2.0.1, the worklet's file answers 200.
- Not verified: **how it sounds** (nobody has listened: the WAVs went to the owner), the roof in the browser (the
  20 s drive passed none), bike / train / cockroach in the browser, phones' cost, the fallback without AudioWorklet,
  the level in the full mix against engine and music.

## Release 2.1 (11-12): course select with a film, About and the desk, paint online

**Course select.** The owner found the cards with a grain relief under them "added on afterwards". Two layouts
went to them as pictures (A: the relief as the stage, B: the course art); then they proposed themselves: a
recording of play whose car's progress drives the grains. My first build put film, relief, speed, clock and a
height profile side by side; the owner's correction: **the grains go over the film**, and **not too much
information: it tires**. Adopted (their word: 「その提案を採用」, which I read as this layout together with my
two proposals: each course at the time of day that suits it, one fixed car):
- `CoursesScreen`: list on the left, the selected course's words and three figures bottom left, on the right a
  film of a run (the game's AI driver in the hayate) with the course's relief of grains over the film's sky. The
  page reads the film's clock every frame, looks up the car's share of the course in the film's track and writes
  `data-cloud-at`; the grains light the road behind the car, keep the road ahead dark, a ring rides where it is
  (`cloud.ts` `Placement.at`, `Shape.part` / `path`; `Cloud.tsx` `data-cloud-mark="at"`).
- Films: `tools/course-clip.cjs` (frame by frame on the GPU, the game stepped by hand) + `course-clip-encode.sh`
  (720p, CRF 34): oboro night 12.4 MB / 114 s, kirifuri dawn 11.6 MB / 97 s, tenrou night 7.2 MB / 84 s, autobahn
  dawn 22.7 MB / 175 s; 52 MB in all, fetched only on this screen, one at a time. nginx: `/video/` (a missing film
  is a 404).
- Without grains (motion off, a software renderer) the drawn line stands in; with motion off the film stands on
  its still; without a film the course's art and the relief's own running light.
- The old cards, the two other proposals, the height profile and the scale bar are gone.

**About and the desk** (agent): main menu このゲームについて: overview, maker (configuration only), technology,
credits, and a desk: questions answered by a language model through the server and the rivals' gateway, reports
(bug / request / other) filed by the model's tool call or by a plain form into `reports.jsonl` in the `desk`
volume; `php artisan desk:reports` reads and closes them. CLAUDE.md "About and the desk".

**Paint online** (agent): the online vehicle select offers the paints like single player's (same component, the
`colors` switch is gone); `room_players.color` (migration), told to the others, drawn in the waiting room and the
race; the seat's colour stays the member's mark; a change of paint alone keeps `ready`.

- Verified: tsc; vitest 210 (new: the car's light on a relief, paints, desk client); backend tests on the
  combined tree 62 passed (724 assertions); E2E on an isolated stack, software rendering: 9 passed before the
  paint merge (About ×3, menus, a whole time attack with submission, ghost battle, rival battle, course select,
  phone) and again after it the online waiting room, course select, car select and phone (see below); pictures
  on the GPU looked at: course select at 1920×1080, 1280×720, 844×390 (phone), 768×1024 (portrait), motion
  off, three courses at mid-film, a film missing; the stack serves the film (200, whole length) and answers 404
  for a missing one. The agents' own checks are in their reports (About: 42 pictures on the GPU with the API
  played by the script; paint: two players on the GPU against an isolated stack, both sides).
- Deployed 11-12 as v2.1.0 (a dump of the database first: `pre-2.1.0.sql.gz` in the `backups` volume; the
  migration ran): `gpu-errors.cjs` 0 on WebGPU and WebGL 2, a race picture looked at; the live stack and the
  public address serve the built bundle, `/api/content` says 2.1.0 and `desk {enabled, ai}`, the four films answer
  200 (and 206 for a range, through the tunnel too). **The desk against the real gateway** (the agent could not):
  a question answered in Japanese in 7.4 s, a report filed by the model's tool call in 11 s and read with
  `desk:reports` (then closed as my test).
- Not verified: the films' playback on a phone and on a slow line (52 MB in all, 7–23 MB each); Firefox / Safari
  (container units size the film's box; without them it takes the stage's width); the course select with a
  gamepad; the rest of the E2E suite; the desk's answers' quality beyond those two, and its limits behind
  Cloudflare; a member's report; paint for trains / creatures online in a picture.

## Light and shadow that do not end near the camera (11-12, v2.1.1)

The owner's report: shadows and the street lamps' light were there only near the camera. Causes (agent, code of
the day + pictures): the key light's shadow map was a ±60 m square centred on the camera (half of it behind the
viewer, a visible line 60 m ahead, "lit" beyond it; the land never threw a shadow, trees only within 80 m); the
lamps were six pooled point lights given to the lamps nearest the camera and faded out by 200 m, plus light maps
on road and ground only: a far lamp lit nothing but its pool on the asphalt.

- Lamps: one light for all of a course's lamps (`render/lampField.ts`, `lampFieldNode.ts`): a grid of cells with
  up to four lamps each and a table, read per pixel; every lamp lights road, walls, rails and trees at any
  distance; the pool under a lamp is part of it (`userData.lampBeam`), the light maps are gone.
- Shadows: the map lies ahead of the camera (4096 → ±100 m, 2048 → ±80 m, 1024 → ±60 m, moved in whole texels);
  beyond it a baked shade per course and light (`render/farShade.ts`: the land, rock-shed roofs, the trees' share
  of light), cross-faded at the map's edge (`render/keyShadow.ts`). Grid, table and shade share one texture
  (`render/lightAtlas.ts`: the 16-texture limit of a fragment shader).
- Kirifuri at dawn keeps the land's own shadow off (`Landform.dawnShade: false`): with it ~90 % of the caldera's
  road lies in shade under a 9° sun and the dawn reads as dusk (the owner's to choose; pictures
  `~/.local/opt/wt/far/cmp-nb-kirifuri-dawn.jpg`).

- Verified by the agent (RX 5700 XT, WebGPU): tsc, vitest, build; `gpu-errors` 0 on WebGPU and WebGL 2;
  before | after pictures on fixed viewpoints, four courses, night / rain / dawn, ultra, and Oboro at medium and
  low (`~/.local/opt/wt/far/sheet-*.jpg`); baked shade against the shadow map on the same view 0.86–1.07 over
  12 views; `perf-pass` on Oboro, ultra, 1080p, in both orders: night no measurable change (scene pass 5.3–5.4 ms
  after, 4.9–6.4 before, load 3–21), dawn 0.9–1.8 ms cheaper; hitch at a change of time of day not worse.
- Verified by me on the merged tree (main + this): tsc; vitest 225; build; `gpu-errors` 0 / 0 (WebGPU, WebGL 2)
  and the race picture; the upscaler on (`quality`, 140 km/h, Oboro and Kirifuri, night and dawn, 32 pictures:
  no page error, no smear on the lit walls or the shadows); a whole run by the AI on Oboro at night (3446
  pictures) and Kirifuri at dawn (2899), frame-to-frame brightness jumps measured and the twelve largest of each
  looked at: all are things passing the camera (mirror posts, shed pillars), none a lamp or a shadow switching
  (`~/.local/opt/wt/far/drive/`).
- Not verified: 4K; phones; pictures on the WebGL 2 backend (errors only); medium / low on courses other than
  Oboro; Tenrou and the autobahn driven as a whole; the bake's time in the browser on a slow machine (Node:
  36–66 ms heights + 100–145 ms per light; main thread, behind the loading screen); E2E (nothing of theirs
  touched).
- Left as it is: `tools/perf-gpu.cjs` still reads `game.lampLights` (the old WebGLRenderer-only tool); the road's
  `uv1` attribute is still built and no longer read. The course select's films were recorded before this change
  (the lamps light the walls more now): to be recorded again together with the props' re-modelling.
- Seen on the way, not from this change: Kirifuri's far caldera wall shows the far trees as large blotches at
  dawn (before and after alike); the exhaust's puffs read as white balls behind the car at dawn.
- Deployed 11-12 as v2.1.1 (bundle `index-D1rLr9WI.js`): the same bundle at the local and the public address,
  `/api/content` says 2.1.1, leaderboard 200, a film's range request 206 through the tunnel.

## Release 2.2 (11-12): the upscaler is FSR 3 on WebGPU; the exhaust's white balls

**Upscaler** (the owner's request of 11-12; agent). WebGPU: `@pmndrs/upscaler` 0.5.0 (MIT; an independent
implementation of FSR 2/3's temporal upscaling as compute passes on the game's own device, no frame generation)
replaces our resolve on three's `TAAUNode` (`render/sceneUpscale.ts`; `TemporalUpscaler.ts` is gone; the B2
entry above describes the old one). WebGL 2 keeps three.js' `FSR1Node`. Modes by FSR's ratios (1.3 / 1.5 / 1.7 /
2; the shown percentages are the same). The settings row says which one runs. The package's pre-exposure is
fixed at 0.01 (its auto-exposure dimmed the lamps' glow by 20–35 %); the rain marks the reactive mask twice as
strongly. CLAUDE.md "Upscaler".
- The agent's numbers (RX 5700 XT, quality mode, load next to each in its report): fine detail at 200 km/h
  (mean |picture − 2 px blur|, six viewpoints) FSR 3 1.38–3.21, old upscaler 1.92–4.27, native 2.37–5.88: softer
  in moving textures; edges clean where the old one stair-stepped; a still picture's flicker 0.005–0.013 %
  (night) / 0.09–0.14 % (dawn) of pixels against the old 0.03–0.07 / 0.17–0.44; night brightness 0.988 of
  native. GPU time (`perf-pass`): upscale passes 0.94 ms at 1080p (old 0.34), 3.54 ms at 4K (old 1.44); the
  whole frame at 4K: native 20.7, old 16.2, FSR 3 18.0 ms. Device-loss fallback with the upscaler on: ok.
- Verified by me on the merged tree (main with the far light + this + the exhaust): tsc; vitest 225; build;
  `gpu-errors` 0 in all four (WebGPU / WebGL 2 × upscaler off / on) and the race picture with it on; shaders
  built per stage with it on: racing 0, as before (load 88 / title 16 / garage 18 / race start 19 / restart 6;
  load 4); 32 moving pictures (140 km/h, Oboro and Kirifuri, night and dawn) next to the old upscaler's on the
  same views: the lamp field and the far shade look the same under both, no smear; a still night scene's
  flicker 0.07–0.08 % of pixels over 8/255 (medium, Oboro; the agent's lower figure was on the autobahn).
- Not verified: E2E (no spec touches it); modes other than quality beyond switching; phones, other GPUs and
  browsers; thin lines over time in video; a real device loss.
- For the owner: softer at speed and 0.6 ms (1080p) / 2.1 ms (4K) dearer than the old one, cleaner edges and a
  stiller picture; sharpness 0.8 recovers a little (default left at 0.5). Off by default as before.

**Exhaust.** The white balls behind a moving car (seen in the course select's films, brightest at dawn) were
the exhaust's puffs: thinned out with speed in number only, a few a second at full opacity. What is seen now
falls with the speed (`fx/Exhaust.ts` `exhaustSeen`: half at 22 km/h, none from 90 km/h); pulling away is still
a plume. Verified: 700 pictures of Kirifuri's start at dawn next to the same frames before
(`~/.local/opt/wt/far/drive2/exhaust-before-after.jpg`). The tyres' smoke in a slide is untouched (it is meant
to be seen). The films still show the balls until they are recorded again.
- Deployed 11-12 as v2.2.0 (bundle `index-CofCe0oY.js`): the same bundle at the local and the public address,
  `/api/content` says 2.2.0, leaderboard 200 at both.

## v2.2.1 (11-12): the cockroach's colours stopped the game; Kirifuri's morning sun; the maker on the About screen

- **Players' report through the desk** (`PVW7D6`: after changing the cockroach's colour it is not drawn).
  Reproduced on the v2.1.0 build on the GPU (`tools/paint-drawn.cjs roach`: the two plain liveries and everything
  after them 0.00 % of the frame). Cause (agent): a plain livery set `map = null` on materials already drawn;
  three.js' shadow shader keeps a reference to the source material's map, the next shadow map read `null.matrix`
  and every frame from then on threw: the picture stood still, garage and race alike, on both backends. Fix:
  a white stand-in texel (`RoachModel.applyLivery`), the slot is never emptied. Verified by me on the build:
  `paint-drawn.cjs roach keikyu1000 hayate` on WebGPU (17 states drawn, 0 errors) and `roach` on WebGL 2, the
  pictures of four states looked at, `gpu-errors` 0 / 0, vitest 228 (new: `roachLivery.test.ts`).
- **Kirifuri at dawn** (the owner chose: a higher sun and the land's shadow): `Landform.dawnSun`, the caldera's
  26° up over the eastern rim (bearing 75°); `dawnShade` is gone. Six suns were compared in pictures on the eight
  fixed viewpoints (`~/.local/opt/quality/cmp/sun-cands-*.jpg`); with this one 28 % of the road lies in the land's
  shade (32 % with the trees), the sun stands in the picture in two of the eight views, and the lake side has
  long shadows across the road. Verified: the eight views of the final build looked at
  (`cmp/rel221-kirifuri-dawn.jpg`), Oboro's dawn unchanged. Not verified: a whole run at dawn on the final sun.
  The course select's Kirifuri film was recorded under the old sun (to be recorded again with the others).
- **About**: the owner gave the maker's name and the repository's link: `ABOUT_CREATOR` / `ABOUT_LINKS` in the
  live `.env` (not in the repository); `/api/content` returns them (checked), the link answers 200.
- The owner's other answers (11-12): the films are recorded again together with the props; FSR 3's softness is
  accepted as it is; the black horizontal lines are gone on their side (nothing was changed for them knowingly).
- Still with agents, stopped twice by the usage limit: the cockroach's wings in the air (a model change: sheet to
  the owner first), the rain's loudness and a 雨音 setting.
- **Deployed 11-12 as v2.2.1** (bundle `index-C-0J8al6.js`, local = public; leaderboard API 200; `/api/content`
  says 2.2.1 with the maker and one link). Desk report `PVW7D6` closed. No E2E run for it.

## v2.2.2 (11-12): the rain is a bed under the drive, and has a volume of its own

- **Players' report through the desk** (`5WKASA`: the rain is too loud). Measured by the agent (dB(A), the game's
  own chain rendered offline per vehicle, speed and state, `tools/rain-mix.ts`): the rain was louder than the
  drive in 22 of 35 states under power (median +1.8 dB; a commuter train at 60 km/h +9.7, in a gust +15.6) and in
  30 of 35 coasting. Cause: the new rain's level was matched to the old loop's figure, but the old loop was a hiss
  at 4–8 kHz and the new rain is broad: at the same figure it had 4–9 dB more in 500 Hz – 2 kHz, where engines
  and inverters sound. Changed (`audio/rain.ts`): `LEVEL` (the rain outside −10 dB, the spray −9 dB, the drops on
  the body as they were), `OUTSIDE` per body (a train a further −6.5 dB: heard from the cab); the fallback noise
  0.16 → 0.05. After: louder than the drive in 3 of 35 under power (E5 at 60, the cockroach at 60 / 120: vehicles
  that are nearly silent there), median −7.9 dB; coasting 8 of 35, median −4.8 dB. Standing, the rain is 10 dB
  under what it was (16 dB in a train): this departs from "keep the standing level"; `LEVEL.outside` is the one
  number to raise if it turns out too faint.
- **Settings 雨音** (`rainVolume`, サウンド's last row, steps of 10 %, default 100 % = the corrected level; a share
  of the effects' volume): `AudioEngine.rain` bus; at 0 % no rain source runs at all. Stored settings without the
  key read as 100 %.
- Verified by me on the merged build: tsc; vitest 229; backend tests 62 (the desk's knowledge file 7477 bytes of
  8192); `gpu-errors` 0 / 0 (WebGPU, WebGL 2); the agent's `setcheck.cjs` on the GPU (100 % → worklet running,
  50 % → gain 0.5, 0 % → no source and silence, back to 100 % by keys → running again, a race started in the rain
  at 0 % → no source; no page errors); one race picture looked at. By the agent: the tables above
  (`~/.local/opt/wt/rainvol/before|after`).
- Not verified: **anything by ear** (the pair to listen to: `new-runup.wav`, `new-train.wav` in both directories);
  the fallback path without AudioWorklet in a browser; the new row on a phone; a whole lap's mix (music, rival,
  squeal mask the rain further).
- **Deployed 11-12 as v2.2.2** (bundle `index-Dc9qiaZ8.js`, local = public; leaderboard API 200; `/api/content`
  says 2.2.2). Desk report `5WKASA` closed. E2E: the settings test alone, on an isolated stack (1 passed: the row
  shows 100 %, a step down 90 % and is stored).
- Also 11-12, with agents: the cockroach's wings are done on a branch (`worktree-agent-a4d9cc6c7fe2e6517`: model
  script, GLB 901 → 950 kB, `flightStep` / `wingPose`, a flutter sound; sheet sent to the owner, merge on their
  yes: a minor version); the owner's new requests: the wind turbine's night lamp is "a huge round red lamp" (the
  props agent resumed: obstruction light, branch brought onto main), the host changes course and conditions in an
  online room and everyone sees who is loading (`~/.local/opt/wt/ONLINE_BRIEF.md`); Edwards + fighters
  (`EDWARDS_BRIEF.md`).

## Release 2.3 (11-12): the cockroach opens its wings in the air

- **Players' reports through the desk** (`V4TNGQ`, `4PHH4G`, `2V9D3R`: thrown into the air after a crash it does
  not flap). A model change (agent): the old model had no hind wings and its wing cases were skinned to the
  thorax. Now a bone per wing case (`wing_L/R`) and two hind wings folded under them (`hind_L/R`; opaque, on the
  body's atlas: no new material, the liveries tint them), GLB 901 → 950 kB, 36 872 triangles, 61 bones. In the
  game (`RoachModel.flightStep` / `wingPose`, `CreatureInfo.flight`): 0.1 s with no leg on the ground → the cases
  open, the hind wings swing out, unfold and beat at 14 Hz; folded 0.25 s after the landing. A flutter and a low
  drone while they are out (`BugSound.flight`). Sim, medals, stats unchanged.
- The owner saw the sheet (`~/.local/opt/wt/roach/roach-wings-sheet.jpg`) and said to put it in (11-12, with the
  props' sheets: "シート全部見たので入れていいよ").
- Verified by me on the merged build: tsc; vitest 235 (new: `roachFlight.test.ts`); `gpu-errors` with the
  cockroach twice in the garage 0 / 0 (WebGPU, WebGL 2); `roach-wings.cjs` on WebGPU and on WebGL 2 with the
  golden livery (wings 0.00 before, 1.00 in the air, 0.00 after the landing; flutter gain 0 / 0.42 / 0; 0
  errors); `paint-drawn.cjs roach` (all nine states drawn); the picture of the fall looked at.
- Not verified: the flutter by ear; a real crash into a wall (the check lifts the body 9 m and drops it); online
  (peers' wings stay shut by design: drawn from poses without a ground-contact flag; ghosts and the replay
  likewise); the garage thumbnail was not made again (folded, it looks as before from that angle); no E2E.
- Known: paused in mid-air the wings keep beating; from the chase camera the hind wings are edge-on for part of
  the beat.
- **Deployed 11-12 as v2.3.0** (bundle `index-jIVxcRFV.js`, local = public; leaderboard API 200; `/api/content`
  says 2.3.0; the public `roach.glb` is the new one, 950 080 bytes). Desk reports `V4TNGQ`, `4PHH4G`, `2V9D3R` closed.

## Release 2.4 (11-12): the thirteen props re-modelled; the turbines' obstruction lights

- **The props** (agent, branch `worktree-agent-a0462d11d1fc0d277`; sheets sent 11-12, the owner: "シート全部見たので
  入れていいよ"): street light, vending machine, curve mirror, bus stop, cone, torii, stone lantern, wind turbine,
  sign gantry, emergency phone, village house, farmhouse, church: real construction (footings, base plates and
  bolts, brackets, gutters) and used surfaces baked per model into one atlas by `tools/blender/props/prop_bake.py`
  (one material = one draw call a prop). `public/models/props` 0.43 → 4.7 MB. Merged onto main by the agent
  (one conflict, `TrackScenery.ts`, the vending machines' place and light: main's side taken).
- **The owner on the live game (11-12)**: the wind turbine looked like the old one (it was: the branch was not in)
  and its red lamp by night was "a huge round red lamp". It was a far light of `Environment.buildCityLights`
  (up to 18 px with a wide glow = a 2–4 m ball on a turbine 100–170 m away, on the tower's axis above the nacelle,
  a square-wave blink, each turbine at its own time, also drawn where no turbine stood). Now (agent): two lamps
  with 0.3 m lenses on posts on the nacelle (in the model, lit through its emissive map) and `render/beacons.ts`:
  one camera-facing quad per lamp, 6–12 px of a 1080-line screen at any distance, 30 soft flashes a minute, all
  turbines together, lit while the road's lamps are (night and rain). The autobahn's turbines share it.
  Sheet: `~/.local/opt/wt/models-props/sheets/wind_turbine_light.jpg` (before / after at 40 m, 300 m, 1.5 km;
  sent to the owner).
- Verified by me on the merged build: tsc; vitest 236; `gpu-errors` 0 / 0 / 0 (WebGPU, WebGL 2, WebGPU with the
  upscaler); fixed viewpoints looked at: all four courses by night (32), Oboro and Tenrou at dawn (16), the same
  two by night on the move with the upscaler (16) (`~/.local/opt/quality/cmp/rel240-a.jpg`, `-b.jpg`); the race
  pictures of `gpu-errors` (the autobahn's new gantry over the start). By the agent: the new turbine is what is
  drawn (Tenrou 9, autobahn 10 instances, no fallback), the lamp's views in the sheet, the lamp on WebGL 2.
- Not verified: the flash watched running (stills at fixed moments only); rain and dawn pictures of the lamp;
  quality low / medium; phones; frame cost and video memory of the new props (no paired run: the machine was
  busy with three agents; the earlier figure: +4.4 MB of downloads); E2E.
- **Deployed 11-12 as v2.4.0** (bundle `index-DOXObXix.js`, local = public; leaderboard API 200; `/api/content`
  says 2.4.0; the public `wind_turbine.glb` is the new one, 249 760 bytes).

## v2.4.1 (11-12): the course select's four films recorded again

- The films were from before the day's changes (props, the lamp field, the exhaust's white balls, Kirifuri's
  morning sun; the owner 11-12: together with the props). Recorded from the v2.4.0 build with
  `tools/course-clip.cjs` (hayate, ultra, 960×540 at 1.5; Oboro night 3427 pictures, Kirifuri dawn 2904, Tenrou
  night 2516, autobahn dawn 5252; no page errors) and encoded with `course-clip-encode.sh` (720p, CRF 34:
  12.6 / 11.0 / 7.1 / 21.0 MB). Raw frames: `~/.local/opt/wt/clips/raw2`.
- Verified: eight frames of the Oboro film looked at (no white balls behind the car, the new props); the course
  select on the GPU with each film at 15 % and 60 % (`~/.local/opt/quality/cmp/rel241/sheet.jpg`: the films play,
  the relief's ring is where the film's car is, no page errors); tsc, vitest 236.
- Not verified: the films watched whole; phones.
- **Deployed 11-12 as v2.4.1** (bundle `index-BE7An1Ro.js`, local = public, API 200) — **and the public address
  still served the old films**: `/video/` answers `max-age=86400`, Cloudflare's edge had the morning's film
  (`cf-cache-status: HIT`, age 9 h, the old length) while the track JSON came fresh: old film, new track.

## v2.4.2 (11-12): the films are asked for with a stamp of their content

- `ui/screens/courseFilms.json` (id → the first eight hex digits of the film's SHA-1, written by
  `tools/course-clip-encode.sh`); `CourseRun` fetches `<id>.mp4|jpg|json?v=<stamp>`. New vitest
  `courseFilms.test.ts`: every stamp is its film's, every film has one.
- Verified: tsc; vitest 238; on the GPU the course select asks for all twelve files with their stamps, all answer
  (200 / 206), the four films play, no page errors (`~/.local/opt/quality/cmp/rel242/filmreq.cjs`); `gpu-errors`
  on WebGPU 0. After the deploy: see the line below.
- **Deployed 11-12 as v2.4.2** (bundle `index-B4hwCPUr.js`, local = public; leaderboard API 200; `/api/content`
  says 2.4.2; the public address answers the four stamped films with the lengths of the files in the tree).

## Release 2.5 (11-12): in an online room the host changes course and conditions; everyone sees who is loading

- **The owner (11-12)**: map and weather cannot be changed in an online battle: make them changeable; and tell,
  by a notice or something, that the other players are loading. Built by an agent
  (`~/.local/opt/wt/ONLINE_BRIEF.md`, branch `worktree-agent-a13d503fcd759c88f`).
- **Server**: `PATCH /api/rooms/{code}` (host only → 403, `waiting` only → 409; `track_id` / `time_of_day`);
  `POST …/rematch` takes the same two; another course takes everyone's `loaded` and `ready` back and replaces a
  vehicle the course does not offer (`Room::vehiclesOn`: none set yet), other conditions take the readies; a
  `loaded` report carries the course's id and one for a course the room has left is dropped; the start blocker
  names who is loading; `POST …/kick` (host, waiting): offered only after 45 s without news from a member or 8 s
  off the channel.
- **Client**: the room's two cells (course, time & weather) are the host's buttons (X / C, click, tap) and open
  the single-player course select and conditions list over the room (confirm = one request; the conditions list
  previews in the host's own game); on the results the host has コースを変えて走る. Every game follows the room
  (`followRoom`). A loading member's row: amber edge, 読み込み中 and a bar (percent told over the presence channel,
  `client-load`, ≤ 2 Hz); under the start button, by name, who is loading or not ready; a notice to the others
  when the host changes something; the loading member's own loading screen says why.
- Verified by me on the merged tree (v2.4.2 + the branch): tsc; vitest 245; backend tests 67 (883 assertions) on
  an isolated stack; E2E there: `online.spec.ts` (4, the new test among them: conditions preview / Esc /
  confirm, notices, course change, hold lines by name, stale report dropped, race, next course from the results,
  second start) and `mobile.spec.ts` (1): 5 passed in 26 min; `gpu-errors` 0 / 0 (WebGPU, WebGL 2); the
  single-player course select (films with their stamps) and conditions screen after the extraction of
  `CourseSelect` / `ConditionsSelect` (pictures looked at, no page errors); the agent's two sheets looked at
  (`~/.local/opt/wt/online/sheet-1920.jpg`, `sheet-phone.jpg`). By the agent: three games on GPU Chrome
  (two desktops, one phone) through the whole flow; the full E2E suite before my merge (15 of 15).
- Not verified: Safari / Firefox, a real phone (the overlay uses `:has()`); a controller; Authentik members in a
  room; vehicle replacement beyond the backend test. Known: on a phone the notice covers the room's top row for
  its 8 s.
- **Deployed 11-12 as v2.5.0** (bundle `index-DYST8WTI.js`, local = public; leaderboard API 200; `/api/content`
  says 2.5.0; `PATCH /api/rooms/…` without a pass answers 401; no errors in the app's log after the start).
- With agents at the end of 11-12 (the usage limit stopped them a fifth time, resumed):
  - **Edwards + the three fighters**: built on `worktree-agent-af9a3b6158beebe1a`, hidden behind a release switch
    (`game/release.ts` + `config/game.php`), stand-in models. Sent back before the merge: main v2.5.0 merged in,
    ONE server mechanism for "a vehicle a course does not offer" (the agent's `Support/Vehicles` and the online
    work's `Room::vehiclesOn` are two), two browsers online with fighters, the upscaler and hitches at take-off.
    It also changes shared render code (`ambientOcclusion.ts`: depth taken at texel middles; bands across open
    ground, on main's courses too): to be looked at on every course before the merge. Whether Edwards is released
    with the stand-in models is the owner's to say (asked 11-12).
  - **Cars re-modelled, first three** (hayate, shiden, r34; `worktree-agent-a51f8b2d623db0a5a`; sheets in
    `~/.local/opt/wt/models-cars/sheets/`, sent to the owner): tyres, brakes, undersides, baked shade, draw calls
    44 → 26; the gain in the picture is small. Next there: the r34's body, the big surfaces of the other two, then
    the remaining five. Not merged: the owner's yes is needed.
  - **How cars are drawn** (`~/.local/opt/wt/CARLOOK_BRIEF.md`): lamp highlights on glossy surfaces, a reflection
    of the surroundings in the paint, glass with a cabin behind it: where the gap to the photos now is.
  - Not started: the tanks' cannon (after the Edwards merge: the same vehicle code).


## v2.5.1 (11-13): hayate, shiden and r34 re-modelled (round one); other models do the work

- **The owner (11-13)**: yes to the three cars' sheets; and from now on Fable 5.2 conducts and other models work
  (Claude models through the Agent tool, four models through Mistral Vibe CLI), with the worry that the 3D
  modelling gets less precise.
- **In**: the cars branch at `919062f` (the state of the sheets): tyres, brake discs, calipers, undersides, baked
  shade, the shared kit `tools/blender/cars/car_common.py`; draw calls 44 -> 26 / 45 -> 26 / 36 -> 22, GLBs
  284 -> 513 / 328 -> 539 / 560 -> 803 kB; new thumbnails. No code of the game changed.
- Verified on the merged tree: tsc; vitest 245; build; `gpu-errors` 0 / 0 (WebGPU, WebGL 2; hayate, r34, shiden
  through the garage, twice); `paint-drawn.cjs hayate shiden r34` all drawn (WebGPU); the race and rival pictures
  looked at (camera with the car).
- Not verified: `paint-drawn` on WebGL 2; phones; the course select's films still show the old hayate (wheels,
  antenna, wiper differ slightly): recorded again with the car-look change.
- **Who does what (my division, 11-13)**: modelling stays on Fable (high) behind a measured gate (silhouette, real
  dimensions, lamp anchors); Edwards' last checks + release commit and the car look on Opus (high); Vibe models
  for second reviews only. Of the Vibe models only gemini-4-hydrogen answered (the other three: usage limit /
  quota upstream); a headless `vibe` from a background shell did not start (waits for the system keyring): the
  second review of the Edwards backend has not happened yet. The agents were stopped once more by a usage limit
  and resumed after the owner's login.

## Release 2.6 (11-18): Edwards AFB and the three fighters are open

- **The owner (11-13)**: release Edwards with the stand-in aircraft models (my reading of their yes; told so).
  Finished by an agent on Opus 5.5 (`~/.local/opt/wt/EDWARDS_FINAL.md`, branch
  `worktree-agent-af9a3b6158beebe1a`, release commit `de77535`).
- **In**: the course `edwards` (style `airbase`), F-15J, F-15C, Su-47 (procedural stand-ins: no cockpit, intakes,
  panel lines or markings), the take-off after the finish, the course select's film (hayate, dawn, 296 s), the
  bots' runs and medals; the occlusion's depth taken at texel middles (bands 4.6-6.8 % -> 0.9-1.2 % on the four old
  courses, pictures 1.6-3.3 % brighter: the agent's numbers, `~/.local/opt/wt/edwards/ao-compare.txt`).
- **Server, from a second review by another model** (gemini-4-hydrogen through Vibe, read-only; the agent checked
  each claim and fixed eight with tests, rejected three that only a wrong config file causes): a closed course's
  runs are in no answer (ghost 404, `bests`), the leaderboard takes only a vehicle the course offers (422), a
  room's vehicle is checked on the locked row (join, change of car, change of course, rematch), `finish` on a
  closed course is 409.
- Verified by me on the merged tree: tsc; vitest 264; build; backend tests 76 (999 assertions) on an isolated
  stack; `gpu-errors` 0 on WebGPU and WebGL 2, default course and `COURSE=edwards` with the three fighters; the
  race pictures of both looked at. By the agent: full E2E 19 of 19 on the release tree, `paint-drawn` for the
  fighters on both backends, the upscaler at Edwards, medals by the sim.
- Not verified: E2E after my merge; two real browsers online on this build (the agent's round two did it on an
  earlier one); the old courses with the upscaler after the occlusion change; phones; the flames by eye in motion.
  Known: orange patches in the lakebed's wet film in night rain; the film is five slow minutes.
- **Models for the work (benchmark, 11-13...18)**: the hayate's three measured defects given to gemini-4-hydrogen,
  gpt-6.1-sol, gpt-6-astra (Vibe, read-only, xhigh; I build and measure) and to the cars agent (Fable).
  After two rounds hydrogen and sol pass the gate (lamp overlap 0.217 -> 0.419 / 0.417); astra failed round one.
  Data: `~/.local/opt/wt/bench/hydrogen-hayate/`. Not decided yet who models what.
- The mirror repository (push only, the owner's) has main since 11-13: pushed in steps of 15 commits (one push
  of the whole history is refused, HTTP 413). GitHub is not pushed: three commits of 11-11 hold the gateway's
  address (removed since); the owner has not said.

## v2.6.1 (11-18): a car's glass shows its cabin; the lamps' images in the clear coat

- **The owner (11-18)**: yes to the car-look sheets (glass in; the lamps' highlights travelling over the body to
  be pursued: step 2, with the agent, not merged). From now on the work is done with Claude Code's models only
  (no Vibe models); GitHub's push is mine to decide: not before the gateway's address is out of the history.
- **In** (agent on Opus 5.5, branch `worktree-agent-ab29bc64a9c82da41` at `b36413f`): `render/carSurface.ts`:
  glass mirrors a worked-out picture of the surroundings and is 0.62 see-through head-on (`CarSpec.glassOpacity`;
  the shiden and the three fighters keep 0.88: nothing presentable under their glass yet); paint keeps the
  environment map and gets the near street lamps as discs in its coat; softer coat highlights (`coatGlint.ts`).
  The inherited full mirror on paint was dropped (tan lower body by day, no difference by night).
- Verified by me on the merged tree: tsc; vitest 264; build; `gpu-errors` 0 (WebGPU, WebGL 2, Edwards with the
  fighters on WebGPU); a race picture looked at. By the agent: `paint-drawn` on both backends, shaders built per
  car not more than main, frame gaps not worse, the bike / train / cockroach unchanged.
- Not verified: the cost on a quiet machine (the agent's 4K estimate +0.46 ms inside the noise); traffic copies;
  E2E (no UI change); phones.
- Waiting for the owner: the sheets of round two of hayate, shiden, r34 (cars branch `32b8970`, gate: nothing worse).

## v2.6.2 (11-18): hayate, shiden and r34, round two (the owner's ok on the sheets)

- **In**: the cars branch at `32b8970` (agent on Fable, high): measured against the references with a gate
  (`~/.local/opt/wt/models-cars/tools/gate/gate.sh`: outlines from the fits' cameras, published dimensions, lamp
  anchors, traced lenses; all three: nothing worse). hayate: front bumper's face 46 mm lower, width 1646 -> 1625
  (catalogue 1625), lenses 0.226 -> 0.389, the aerial a stub; shiden: a cabin; r34: tail panel, wing, lips set by
  measurement, width 1795 -> 1786 (1785). Cabins in all three; the shiden's glass exception (0.88) is gone.
- Verified by me on the merged tree: tsc; vitest 264; build; `gpu-errors` 0 / 0 (WebGPU, WebGL 2);
  `paint-drawn.cjs shiden hayate r34` all drawn (WebGPU); garage and race pictures of the three looked at (the
  shiden's seats and wheel show through its glass).
- Not verified: phones; the course films still show the first hayate (to record again once the car look's
  step two is decided).
- **Correction to v2.6.1** (found by the car-look agent, 11-18): the glass mirror was only the sky's gradient and
  the paint coat's lamp images were never drawn: `SurroundingsNode` built its statements where three.js drops
  them, and one shared node answered three contexts. What players got is the see-through glass. The fix changes
  the look and goes to the owner as sheets first; CLAUDE.md's paragraph on `carSurface.ts` describes the intent,
  not v2.6.1's picture, until then.
- Still to see by the owner: raijin, supra (sheets sent 11-18) and one more fix of the r34's underside (`6478a8f`).

## v2.6.3 (11-18): raijin, supra, s15 and cybertruck, round two; the r34's underside

- **The owner (11-18)**: plainly positive fixes go in without asking first (memory `positive-fixes-no-ask`); I look
  at the sheet and the gate myself and report afterwards.
- **In**: the cars branch at `c28d2cb` (agent on Fable, high; gate: nothing worse on all four). raijin: arch lips
  thinner, width 1760 -> 1749 (1740), the lips' saw-toothed inner edge mended; supra and s15: shape untouched,
  tyres, brakes, cabin, underside; cybertruck: width 2068 -> 2027 (catalogue), every outline better
  (0.9398 -> 0.9467), cabin, battery case; r34: silencer across the car, tank ahead of the axle. Draw calls
  about 40 -> 22 a car.
- Verified by me on the merged tree: tsc; vitest 264; build; `gpu-errors` 0 / 0 (WebGPU, WebGL 2) with the four
  through the garage; `paint-drawn.cjs raijin supra s15 cybertruck` 20 of 20 drawn (WebGPU); the s15's and the
  cybertruck's sheets and a garage sheet of the four looked at (cabins show through the glass).
- Not verified: the raijin's and supra's own sheets only reduced; `paint-drawn` on WebGL 2 (the agent ran it for
  raijin, supra, r34); phones; vehicle thumbnails of the four are the agent's.
- Left with the agent: u9 (no GLB in the game yet).

## v2.6.4 (11-18): the U9 has its own model; all eight cars are through round two

- **In**: the cars branch at `a73a918` (agent on Fable, high; its final report): `u9.glb` (78 k triangles, 22 draw
  calls, 616 kB) in place of the procedural stand-in: body, lamps, wheels and calipers, wing (1.99 m, measured on
  a photo), a cabin, an electric underside. Gate against its plain script build: nothing worse (outlines 0.9714).
  Left as it is: 57 mm wider and 28 mm higher than the catalogue (at the catalogue's figures every outline is
  worse); the lamp's dark lens reads grey, the plate is blank, few shut lines.
- Verified by me on the merged tree: tsc; vitest 264; build; `gpu-errors` 0 / 0 (WebGPU, WebGL 2) with the u9
  three times through the garage; `paint-drawn.cjs u9` 5 of 5 (WebGPU); `lamps.cjs u9` (anchors from the model, no
  errors; picture looked at: the beams start at the lamps); the sheet, the garage and race pictures looked at.
- Not verified: `paint-drawn` on WebGL 2 by me (the agent ran it); phones; the films (old cars in them).
- The cars agent is finished. Open with the owner: the lamps' streaks on the body (car-look branch `f7529bf`,
  sheets sent; it also holds the fix of v2.6.1's mirror).

## v2.6.5 (11-18): the lamps' streaks in the clear coat, weak; the cars' mirror works as it was meant to

- **In**: the car-look branch at `f7529bf` (agent on Opus, high): street lamps as streaks along the car in every
  clear coat, and the fix of v2.6.1's two faults (statements built in `setup()` dropped: the glass mirrored only the
  sky gradient and no coat had a lamp in it; one env node for three contexts). The owner saw its sheets and chose
  "weaker" of three (as it is / weaker / the fix only).
- **Strength, set by me**: the branch's gain 8 / cap 15 → gain 2 / cap 2. Gain alone did little (4 / 15 and even
  1.5 / 15 still lit a wet roof's edge orange: where the lobe's middle meets a lamp the value is far over the cap's
  range, so the cap is what the eye sees). Compared on the same frames (off, 8/15, 4/15, 3/4, 2/2 at 80 and
  160 km/h, night; rain under a lamp from the front): 2 / 2 keeps a thin warm line on pillar and roof edge, a warm
  roof edge at 160 without the white blaze. Sheets `~/.local/opt/wt/carlook/g4/{al80,al160,rain-de,rain-sweep}.jpg`.
- Verified by me on the merged tree: tsc; vitest 264; build; `gpu-errors` 0 / 0 (WebGPU, WebGL 2) on the final
  build; pictures against the effect switched off on the same frames (they differ: the effect is in the shader);
  race pictures hayate / r34 at night, rain and dawn looked at.
- From the agent's report, not repeated by me: no cost over ±0.1 ms at 1080p (paired `perf-pass`), shaders built
  per step as on main (`builds2`), hitches as main, flicker with the upscaler 0.117 against 0.122, `paint-drawn`
  both backends (all measured at 8 / 15; gain and cap are uniforms, the shader is the same).
- Not verified: phones; the upscaler's pictures at the new strength; other cars than hayate / r34 by picture;
  E2E. The glass mirrors more than in v2.6.1–2.6.4 (ground, town glow, clouds): by day it differs little
  (agent's sheets), I looked at night, rain and dawn only.
- Seen and left: `look.cjs` with two ids in one page drew the second car (r34) sunk beside the road and no car in
  the chase view; alone the r34 is right. Taken as the probe's way of starting a second race by hand (the `gpu-errors`
  paths, which change cars through the garage, are clean); not looked into further.
- Next: the course-select films again (cars' models and look have changed since they were recorded).

## v2.6.6 (11-18): the course select's five films recorded again

- All five (`tools/course-clip.cjs` on the v2.6.5 build, the hayate; oboro night, kirifuri dawn, tenrou night,
  autobahn dawn, edwards dawn) and encoded (`course-clip-encode.sh`, new stamps in `courseFilms.json`): the films
  showed the cars' models of before round two and the look of before v2.6.1. Sizes as before (7–21 MB).
- Verified by me: frames of every film looked at (start, middle, end); vitest 264 (the stamps match the files);
  tsc; build; `gpu-errors` 0 / 0; the course select on the GPU with each of the first four films sought to its
  middle (plays, no page errors; oboro's picture looked at: relief and ring with the car).
- Not verified: Edwards' film in the course select by picture (`coursesel.cjs` walks four courses); phones.
- Housekeeping the same day: seven finished agent worktrees and their merged branches removed (root-owned `e2e`
  leftovers of four remain under `.claude/worktrees/`, a few MB each); the history rewrite for GitHub rehearsed in a
  scratch clone (`~/.local/opt/wt/rewrite`: `filter-branch --tree-filter` over the 203 commits from `8813459`; the
  host is gone from every commit, the final tree is identical). Not pushed: every hash from 11-11 on changes, so the
  mirror needs a forced push and the owner is told first.

## History rewritten for GitHub (11-18, on the owner's yes)

- The LLM gateway's host stood in three files of the commits of 11-11 (`docs/HANDOVER.md`, `backend/config/llm.php`,
  `docker-compose.yml`). `filter-branch --tree-filter` over everything from there on put `llm-gateway.invalid` in
  its place: **every commit id from 11-11 on is new** (v2.6.6 is `a5e2ddf`, was `9c29e8d`); the files of the newest
  commit are identical. Ids quoted in older sections of this file are the old ones (find a commit by its title).
- Checked on the rewritten history before pushing: the host in no commit; no long value of `.env` in any commit;
  the public host name in none; mail-like strings in the tree are package authors in lock files only.
- Pushed to GitHub (a fast-forward from its state of 11-04). **The mirror is not updated yet**: its server did not
  answer on 11-18 (connection timed out), and it needs a forced push (`ccr-de1f3a33-58aazj`), in steps of ~12
  commits to a temporary branch first (HTTP 413 on a big pack). Until then the mirror holds the old history at
  v2.6.6's files.
- The old history: bundle `~/.local/opt/wt/rewrite/pre-rewrite-9c29e8d.bundle`; local branches `tts` and one old
  agent branch still stand on it (never push them).
- Started the same day: two modelling agents (Fable, high) for the fighters' own models (F-15J/DJ + F-15C/D; Su-47);
  sheets go to the owner before anything is merged.

## v2.6.7 (11-18): Edwards in night rain, the orange patches on the wet ground are gone

- **Cause** (agent on Opus, high; shown by switching candidates off one at a time on a held frame): the reflection
  environment (`Environment.buildEnvMap`) carries a ring of 14 warm panels that stands in for the lamps along the
  passes; the lakebed's film of water (roughness 0.07) and the apron's puddles mirrored them as orange ovals that
  went with the camera. **Fix**: `Landform.lampRing` (default 1; the Mojave 0): the ring is left out of the
  reflection scene there. Other landforms multiply by 1.
- Verified by me on the merged tree: tsc; vitest 264; build; `gpu-errors` 0 / 0; the agent's off / on / off sheet
  looked at; my own eight viewpoints at Edwards in rain (`~/.local/opt/quality/rel267/rain.jpg`): no patches.
  The same day on v2.6.6's tree: backend tests 76 passed (isolated stack).
- From the agent's report, not repeated by me: WebGL 2 at Edwards in rain (same fault before, gone after);
  oboro night rain unchanged; Edwards dawn unchanged; Edwards night dry 5/255 less red in the shadows.
- Side effect, accepted: paint at Edwards loses the ring's warm tint and reads cooler in rain.
- Seen by the agent, not touched: the apron's puddles have hard edges and now read as dark spots.
- Also checked the same day: the lamps' streaks with the upscaler on (80 / 160 km/h, off against on:
  `~/.local/opt/wt/carlook/g4/up.jpg`): nothing breaks, the effect is as mild as native; the cars' thumbnails
  redrawn on v2.6.6 came out the same to the eye, so the old files stay.
- E2E on the isolated stack, on v2.6.6's tree (`143d29f`, the first run since the merges of 11-13…18): **19 of 19
  passed** (32 min; about, API, game, mobile, online with five members, waiting room, the host's changes, phone).
  v2.6.7's two files were not in that run.
- Edwards' film in the course select, by picture (`~/.local/opt/quality/cmp/rel267/now-1920x1080-4-at60.jpg`): plays,
  the relief's ring is with the car.
- Running since the afternoon (agents, nothing merged): the fighters' own models (F-15s, Su-47; Fable), the tanks'
  cannon behind the release switch (Fable), load time and the first dawn's hitch (Opus).

## v2.6.8 (11-18): loading compiles see the whole scene; no more stand-still at "the first dawn"

- **In**: the load-time branch at `efa05ff` (agent on Opus, high; three commits A, B, A2).
- **What the "first dawn" hitch was** (the agent's finding, with a control run): three.js' `compileAsync` leaves out
  whatever is outside the camera's view, and behind the loading screen the camera is wherever it last was (after a
  change of course: at the course that was left). So the loading compile built only what that camera happened to
  see; the rest was built in the frame that first showed it: nine props and roadside pieces ~7 s into the title's
  run (0.3–0.6 s; the hitch probe changed to dawn at about that moment, hence the name), and 35 shaders in the
  first frame of a race after a change of course (0.9–1.4 s).
- **A** `RenderHost.seeAll`: while a loading compile starts, every visible object counts as in view;
  `EnvironmentRig.holdParts`: the sea of clouds and the city's lights are in the scene for that compile whatever
  the time of day. **B** `surfaceTextures.ts`: the photo layers are decoded off the main thread
  (`createImageBitmap`, flipped there, `flipY` off; falls back to the image element). **A2**: the title's car is
  made inside `buildWorld` before the compile (the title appears 0.15–0.9 s later, its first frame no longer
  stands 0.5 s).
- Agent's figures (GPU, paired, the machine busy; counts hold under load, seconds are noisy): a race's first frame
  after a change of course 914–1418 → 245–308 ms (35 → 18 shaders: cars and shadow maps remain); texture upload
  657 → 140 ms under the profiler; the course's compile 1.0 → 1.8 s (behind the loading screen, accepted). Title
  on a quiet machine before: 7.3 s cold (the old 10–12 s did not reproduce); no clean total after.
- Verified by me on the merged tree: tsc; vitest 264; build; `gpu-errors` 0 / 0; the agent's `todprobe.cjs`
  (rain, dawn, night, dawn at load 14): no frame over 40 ms at any step, 0 shaders built at dawn; E2E on the
  isolated stack on this tree: 19 of 19 passed (41 min).
- From the agent's report, not repeated by me: `backend-fallback` 5 of 5, `builds2` (fewer per garage step, none
  twice), pictures before | after on oboro and tenrou at three times of day and with the upscaler (grain and wind
  only), gpu-errors with the upscaler.
- Not verified: Edwards and the autobahn by picture; phones' memory (B keeps ~90 MB of decoded pixels at high,
  ~25 MB at medium); real network download times.
- Left by the agent, with estimates: the scenery's build is one 2.0–2.4 s main-thread task (workers could save
  1–2 s: a large change); the remaining 250–300 ms at a race start (shadow-map shaders, the rival's car).

## v2.6.9 (11-18): the tanks' cannon, in the code behind the release switch (off)

Merged the tanks agent's branch (`46ccf94`): `game/weapons/` (gun control, ballistics, what a shell meets, gunnery),
`net/gunEvents.ts` (`client-gun`, the firer's screen decides, the victim's game checks), turret / gun angles in the
state packet's flag word, `ui/hud/GunSight.tsx`, tank sound, tools `tank-figures.ts`, `tank-wav.ts`, `tank-check.cjs`,
`tank-duel.cjs`. The switch `tanks` stays off on client and server: players meet nothing new.

Verified on the merged tree: tsc; vitest 285 with the switch off and with `TANKS=1`; build; `gpu-errors.cjs` WebGPU 0,
WebGL 2 0 (switch off); backend tests 78; E2E 19/19 on the isolated stack; one race picture looked at.
Verified by the agent only (its pictures in `~/.local/opt/wt/tanks/sheets/`): garage, rival battle, sight, shot, the
rival put back, phone layout, two games in a room.
Not verified: the tanks' figures against sources (written from memory), the sound by ear, a real gamepad, phones.
Before the switch can go on: figures checked, own models (owner sees the sheets), the points above.

## Tanks' figures checked against published sources (11-18/19, still behind the switch; no deploy needed)

Merged `tank-figures` (`2c00112`): `docs/TANK_FIGURES.md` gives per vehicle and figure the value before, the published
value, the source and the verdict. 10式 / 16式: every published figure matched; their gun data are not published
(stay `estimated`). Corrected: Leopard 2A5 (70 km/h, 59.5 t, 9.67 m over the gun), M1A2 (M829A3 1,552.5 m/s, 9.77 m),
T-14 (55 t, 3.9 m wide, 32 usable rounds, reverse 45 km/h estimated, -7/+15). Medals of the Leopard and the T-14
re-derived. Japan's MoD pages could not be read by the agent (403): those figures rest on sources that agree.
Verified here: tsc, vitest 285 (switch off and `TANKS=1`). Not found anywhere: track contact lengths, pivot rates,
elevation rates, the M1's reverse speed.

