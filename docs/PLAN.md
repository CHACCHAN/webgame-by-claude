# TOUGE NOCTURNE — Design & Plan

## Concept
A night downhill on the fictional mountain pass **朧峠 (Oboro Pass)** above a harbour city.
Visual hook: driving a hairpin ladder high above a carpet of city lights, moon over the bay, sodium lamps,
cedar forest silhouettes. A second time-of-day preset, **dawn above a sea of clouds**, gives a contrasting mood.
All names, cars, characters and the course are original.

## Pillars (priority order from the brief)
1. Playable, 2. fun to drive (drift-friendly arcade physics), 3. beautiful, 4. few bugs, 5. usable UI, 6. features.

## Course (3.27 km, 208 m drop, ~1:40–2:10)
Summit start (pass sign, LED lamps) → fast sweepers → **vista**: cliff-side left-hander with the bay below →
**4-hairpin ladder** → forest esses → **rock shed** gallery → **bridge** over a gorge with the city in view →
final hairpin → finish. 4 timing sectors. Authored as straights/arcs + grade in `track/courseDesign.ts`;
curvature/grade smoothed; road widened in hairpins; banking from curvature.

## Technical design
- **Terrain**: road-first. Road heights are interpolated into the hillside (IDW within 320 m) blended with a
  large-scale landform (mountains north, coastal plain, sea); road corridor cut/filled with embankments; gorge
  carved under the bridge. Near grid 4 m, far grid 24 m.
- **Physics**: Rapier rigid body + 4 raycast wheels; custom tyre model (slip-angle curve with post-peak falloff,
  friction circle with retained lateral grip, power oversteer for RWD, handbrake), anti-roll, aero, auto/manual
  gearbox, launch, rev limiter, turbo boost. Assists: auto counter-steer, drift momentum push, spin-out guard,
  yaw damping. Invisible trimesh walls keep cars on the road; end caps.
- **AI**: elastic-band minimum-curvature racing line + grip-limited speed profile, pure-pursuit steering,
  rubber-banding, simple overtaking offset, unstick logic. Levels: rookie / ace / legend.
- **Ghosts**: 20 Hz samples, quantised + delta encoded + gzip → base64 (~20–40 KB/run). Stored in PostgreSQL.
- **Backend**: Laravel API — anonymous players with bearer tokens (hash stored), runs with sector splits and
  plausibility checks, per-player-best leaderboard (window function), ghost download, rate limiting, seeds.
- **Rendering**: R3F canvas + imperative engine; PBR materials, PMREM env map from the sky, moon/sun shadow
  following the camera, headlight spotlights + beam cones, pooled lamp point lights, instanced trees/bushes/rocks,
  city light points shader, sea, sea of clouds, bloom/tonemapping/SMAA/vignette/CA. Quality presets low→ultra.
- **Audio**: WebAudio synthesis — engine harmonics with distortion/filter by rpm & load, intake noise, turbo
  whistle + blow-off, tyre squeal, wind, impacts, UI chimes, ambient pad.

## Phases
1. Driving demo (Docker, API, track, physics, camera, HUD) — **done**
2. Visual quality (scenery, lighting, post, UI art direction, external asset requests)
3. Game modes (time attack, rival, ghost, ranking, results/replay)
4. Polish (handling, perf, tests, docs)
