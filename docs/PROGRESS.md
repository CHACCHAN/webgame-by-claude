# Progress log

Newest first. "Verified" means actually executed in this environment; anything else is marked as unverified.

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
