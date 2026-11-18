import * as THREE from 'three';
import { SpriteNodeMaterial } from 'three/webgpu';
import { cameraProjectionMatrix, clamp as clampNode, exp, fract, instancedBufferAttribute, max, modelViewMatrix, select, step, texture, uniform, uv, vec4 } from 'three/tsl';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { Track } from '../track/Track';
import type { TerrainData } from '../track/terrain';
import { EDWARDS_FIELD, EDWARDS_ROUTE, edwardsFrame, edwardsHeight } from '../track/courseDesign';
import { rng } from '../util/math';
import { gridGeometry, LED, SODIUM, type Lamp, type SceneryQuality, type SceneryResult } from './TrackScenery';
import { tiles } from './autobahnScenery';
import { desertMaterial, type LakeMarks } from './airbaseGround';
import { addSlab, addStrip, PAVE_APRON, PAVE_RUNWAY, PAVE_TAXI, pavementGeometry, pavementMaterial, runwayNumbers } from './airbasePavement';
import { shadeScene, type ShadeCaster } from './farShade';
import { makeGlowTexture } from './textures';
import { beaconPulse, buildBeacons } from './beacons';
import { parkedJets } from './JetModel';
import { CAR_SPECS, type CarId } from '../vehicle/carSpecs';
import type { Float, Vec3 } from './tslNoise';

/*
 * EDWARDS AFB scenery (CourseInfo.style 'airbase'): an airfield in the high desert, all procedural.
 *
 * Places are given in the airfield's frame (track/courseDesign.ts `edwardsFrame`): `a` metres along runway 04R from
 * its threshold, `b` metres to its left. The ground is the surface wherever there is no pavement (the terrain lies
 * at the road's height: `CourseDesign.bed` 0): the lakebed's lines and the compass rose are painted by the ground's
 * material (airbaseGround.ts), the pavements are one mesh a hand's breadth above the ground (airbasePavement.ts).
 * Nothing stands beside the course that a vehicle could hit: the buildings are behind the apron.
 *
 * Lights: the apron's and the finish's masts are lamps of the course's lamp field (their pools on the ground); the
 * airfield's own lights (runway edge, threshold, approach with its running flash, taxiway blue, the tower's beacon,
 * lanterns along the lakebed runways) are sprites that light nothing, as from a cockpit. The red obstruction lights
 * of the roofs and of the tower's mast are the game's own for tall things (`render/beacons.ts`).
 */

/** the pavement's height over the ground: slabs, and the strips that run onto them a little lower */
const LIFT_SLAB = 0.04, LIFT_STRIP = 0.03;
/** magnetic north at Edwards, east of true north (about 12° in the 2010s) */
const DECLINATION = 12;

interface Light {
  x: number;
  y: number;
  z: number;
  color: readonly [number, number, number];
  size: number;
  /** 0 steady · 2–3 blinking (phase) · 5–6 the beacon's flashes (phase) · 10–11 the approach's running flash (place in the row) */
  anim: number;
}

const WHITE = [2.1, 2.0, 1.75] as const, AMBER = [2.2, 1.25, 0.25] as const, RED = [2.4, 0.22, 0.14] as const;
const GREEN = [0.25, 2.1, 0.55] as const, BLUE = [0.22, 0.42, 2.4] as const;

function colored(geo: THREE.BufferGeometry, color: THREE.ColorRepresentation) {
  const g = geo.index ? geo.toNonIndexed() : geo;
  const c = new THREE.Color(color);
  const n = g.getAttribute('position').count;
  const col = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) col.set([c.r, c.g, c.b], i * 3);
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return g;
}

export function buildAirbaseScenery(track: Track, terrain: TerrainData, quality: SceneryQuality): SceneryResult {
  const group = new THREE.Group();
  group.name = 'scenery';
  const shadows = quality.shadows;
  const fld = EDWARDS_FIELD, route = EDWARDS_ROUTE, f = edwardsFrame();
  const nightEmissive: THREE.MeshStandardMaterial[] = [];
  const lamps: Lamp[] = [];
  const lights: Light[] = [];
  const roofLamps: THREE.Vector3[] = [], mastLamps: THREE.Vector3[] = [];
  const at = (a: number, b: number, up: number) => {
    const p = place(a, b, up);
    return new THREE.Vector3(p.x, p.y, p.z);
  };
  const casters: ShadeCaster[] = [];
  const ground = (x: number, z: number) => terrain.heightAt(x, z);
  /** a place of the airfield's frame in the world, `up` metres above the ground */
  const place = (a: number, b: number, up = 0) => {
    const [x, z] = f.at(a, b);
    return new THREE.Vector3(x, ground(x, z) + up, z);
  };
  const HEADING = Math.PI - (fld.bearing * Math.PI) / 180;
  const dirOf = (h: number) => ({ dx: Math.sin(h), dz: Math.cos(h) });

  // ---------------------------------------------------------------- where things are along the course
  const firstOf = (zone: string, from = 0) => {
    for (let i = from; i < track.count; i++) if (track.zone[i] === zone) return i;
    return track.count - 1;
  };
  const iRunway = firstOf('runway'), iLake = firstOf('lakebed');
  // the last straight begins where the sweep has ended
  const iLast = iLake + Math.round(route.overrun + (route.sweepR * route.sweepDeg * Math.PI) / 180) + 60;
  const lane = f.of(track.pos[0], track.pos[2])[1];
  const apronMid = (fld.apron.b0 + fld.apron.b1) / 2;

  // ---------------------------------------------------------------- the ground
  const last = track.getPos(iLast), lastDir = dirOf(track.heading[iLast]);
  const end22 = f.at(fld.runway.length, 0), rose = f.at(fld.rose.a, fld.rose.b);
  const fin = track.pointAt(track.finishS), finDir = dirOf(track.headingAt(track.finishS));
  const HALF = fld.runway.width / 2;
  const marks: LakeMarks = {
    runways: [
      // the main runway's lakebed part (9,588 ft)
      { x: end22[0], z: end22[1], dx: f.ax, dz: f.az, from: 0, to: 2922, half: HALF },
      // lakebed runway 36: from the south, past the course's sweep, north beyond the finish
      { x: last.x, z: last.z, dx: lastDir.dx, dz: lastDir.dz, from: -1500, to: track.length - iLast + 400, half: HALF },
    ],
    rose: { x: rose[0], z: rose[1], radius: fld.rose.radius, north: DECLINATION },
    finish: { x: fin.x, z: fin.z, dx: finDir.dx, dz: finDir.dz, half: HALF },
  };
  const terrainMat = desertMaterial(marks, false) as unknown as THREE.MeshStandardMaterial;
  const nearTiles = tiles(gridGeometry(terrain.near, terrain, true, true), terrain.near.nx, terrain.near.nz, 12, 12, terrainMat, 'terrain-near');
  nearTiles.traverse((o) => (o.receiveShadow = true));
  group.add(nearTiles);
  const farMat = desertMaterial(marks, true) as unknown as THREE.MeshStandardMaterial;
  farMat.polygonOffset = true;
  farMat.polygonOffsetFactor = 2;
  farMat.polygonOffsetUnits = 4;
  group.add(tiles(gridGeometry(terrain.far, terrain, false, true), terrain.far.nx, terrain.far.nz, 6, 6, farMat, 'terrain-far'));

  // ---------------------------------------------------------------- the pavements
  const slabs = track.design.slabs ?? [];
  const inSlab = (i: number, shrink: number) => {
    const x = track.pos[i * 3], z = track.pos[i * 3 + 2];
    return slabs.some((sl) => {
      const fx = Math.sin(sl.heading), fz = Math.cos(sl.heading);
      const along = (x - sl.x) * fx + (z - sl.z) * fz, across = Math.abs((x - sl.x) * fz - (z - sl.z) * fx);
      return along > shrink && along < sl.length - shrink && across < sl.width / 2 - shrink;
    });
  };
  const out = { pos: [] as number[], pv: [] as number[], idx: [] as number[] };
  const plane = (x: number, z: number) => edwardsHeight(f.of(x, z)[0]);
  for (const sl of slabs) addSlab(out, sl, sl.id === 'runway' ? PAVE_RUNWAY : PAVE_APRON, plane, LIFT_SLAB);
  // the taxiways: the course's own strip wherever it is not on a slab
  const strips: [number, number][] = [];
  let from = -1;
  for (let i = 0; i < iLake; i++) {
    const on = track.zone[i] !== 'lakebed' && !inSlab(i, 2.5);
    if (on && from < 0) from = i;
    if (!on && from >= 0) {
      strips.push([from, i - 1]);
      from = -1;
    }
  }
  for (const [a, b] of strips) if (b - a > 4) addStrip(out, track, a, b, PAVE_TAXI, LIFT_STRIP);
  const roadMaterial = pavementMaterial(
    {
      runwayLength: fld.runway.length,
      hold: iRunway - 125,
      lane: -(lane - apronMid),
      leadOff: route.startA - route.rampLen - fld.apron.a0,
      turn: route.turn,
      spots: { every: 66, depth: 92 },
      start: route.startA - track.startS - fld.apron.a0,
    },
    runwayNumbers(['04', 'R'], ['22', 'L']),
  ) as unknown as THREE.MeshStandardMaterial;
  const pavement = new THREE.Mesh(pavementGeometry(out), roadMaterial);
  pavement.receiveShadow = true;
  pavement.name = 'road';
  group.add(pavement);

  // ---------------------------------------------------------------- buildings
  const solid: THREE.BufferGeometry[] = [], lit: THREE.BufferGeometry[] = [], glass: THREE.BufferGeometry[] = [];
  /** a piece given in a building's own frame (x = away from the runway, z = along it), set down at (a, b) */
  const put = (list: THREE.BufferGeometry[], geo: THREE.BufferGeometry, color: THREE.ColorRepresentation, a: number, b: number, up = 0) => {
    const p = place(a, b, up);
    list.push(colored(geo, color).rotateY(HEADING).translate(p.x, p.y, p.z));
  };
  const r = rng(412);
  // hangars along the back of the apron: a long box under a barrel roof, the door to the apron
  const HW = 96, HD = 62, HH = 19;
  const hangarB = fld.apron.b1 + 8 + HD / 2;
  for (let k = 0; k < 6; k++) {
    const a = fld.apron.a0 + 82 + k * 125;
    const tone = 0.36 + r() * 0.07;
    put(solid, new THREE.BoxGeometry(HD, HH, HW), new THREE.Color(tone * 1.08, tone, tone * 0.9), a, hangarB, HH / 2);
    // (the roof stands a little proud of the gables: flush with them the two flickered)
    put(solid, new THREE.CylinderGeometry(HD / 2 + 0.4, HD / 2 + 0.4, HW + 1.2, 20, 1).rotateX(Math.PI / 2).scale(1, 0.26, 1), '#4a4d52', a, hangarB, HH);
    // two stand open with the lights on, the others are shut
    const open = k === 1 || k === 4;
    put(open ? lit : solid, new THREE.BoxGeometry(0.5, HH * 0.8, HW * 0.86), open ? '#ffffff' : '#33363a', a, hangarB - HD / 2 - 0.1, HH * 0.4);
    casters.push({ x: place(a, hangarB).x, z: place(a, hangarB).z, r: HW / 2, top: place(a, hangarB).y + HH + 6 });
    for (const k of [-1, 1]) roofLamps.push(at(a + (k * HW) / 2, hangarB - HD / 2, HH + 1));
  }
  // the control tower: a shaft, the cab's glass, its roof and aerials
  const towerA = fld.apron.a0 + 395, towerB = fld.apron.b1 + 150, TOWER = 38;
  put(solid, new THREE.BoxGeometry(8, TOWER, 8), '#6a6862', towerA, towerB, TOWER / 2);
  put(solid, new THREE.BoxGeometry(26, 9, 34), '#5e5c57', towerA, towerB + 12, 4.5);
  put(glass, new THREE.CylinderGeometry(7.4, 5.8, 5.6, 8), '#ffffff', towerA, towerB, TOWER + 2.8);
  put(solid, new THREE.CylinderGeometry(8, 8, 0.7, 8), '#3c3e42', towerA, towerB, TOWER + 5.9);
  put(solid, new THREE.CylinderGeometry(0.12, 0.12, 7, 6), '#8a8d92', towerA, towerB, TOWER + 9.7);
  casters.push({ x: place(towerA, towerB).x, z: place(towerA, towerB).z, r: 6, top: place(towerA, towerB).y + TOWER + 6 });
  mastLamps.push(at(towerA, towerB, TOWER + 13.4));
  // (an airfield's beacon: white and green in turn; a military field's shows two whites)
  lights.push({ ...place(towerA, towerB, TOWER + 7), color: WHITE, size: 9, anim: 5.0 });
  lights.push({ ...place(towerA, towerB, TOWER + 7), color: WHITE, size: 9, anim: 5.07 });
  lights.push({ ...place(towerA, towerB, TOWER + 7), color: GREEN, size: 9, anim: 5.5 });
  // workshops and offices behind the hangars
  for (let k = 0; k < 9; k++) {
    const w = 30 + r() * 40, d = 16 + r() * 18, h = 5 + r() * 6;
    const a = fld.apron.a0 - 40 + k * 95 + r() * 30, b = fld.apron.b1 + 150 + r() * 120;
    if (Math.abs(a - towerA) < 45) continue;
    const tone = 0.3 + r() * 0.1;
    put(solid, new THREE.BoxGeometry(d, h, w), new THREE.Color(tone * 1.05, tone, tone * 0.92), a, b, h / 2);
    if (r() < 0.6) put(lit, new THREE.BoxGeometry(0.3, 1.3, w * 0.7), '#ffffff', a, b - d / 2 - 0.1, h * 0.55);
  }
  // the research centre's hangars on the lake's shore, north of the runway's end, by the compass rose
  for (const [a, b, w] of [[4330, 1080, 110], [4345, 1235, 86], [4250, 1150, 60]] as const) {
    put(solid, new THREE.BoxGeometry(70, 22, w), '#74736d', a, b, 11);
    put(solid, new THREE.CylinderGeometry(35.4, 35.4, w + 1.2, 18, 1).rotateX(Math.PI / 2).scale(1, 0.22, 1), '#4e5157', a, b, 22);
    casters.push({ x: place(a, b).x, z: place(a, b).z, r: w / 2, top: place(a, b).y + 28 });
    roofLamps.push(at(a, b, 31));
  }

  // ---------------------------------------------------------------- lamps (the course's lamp field) and their masts
  const MAST = 11;
  const mast = (a: number, b: number, color: THREE.Color, s: number) => {
    put(solid, new THREE.BoxGeometry(0.32, MAST, 0.32), '#70757b', a, b, MAST / 2);
    put(lit, new THREE.BoxGeometry(1.5, 0.3, 0.9), '#ffffff', a, b, MAST + 0.1);
    lamps.push({ position: place(a, b, MAST - 0.2), color: color.clone(), s });
  };
  // the apron's floodlights: a row at the hangars, a row at its edge towards the taxiway
  for (let a = fld.apron.a0 + 20; a < fld.apron.a1; a += 83) {
    const s = THREE.MathUtils.clamp(route.startA - a, 0, route.rampLen);
    mast(a, fld.apron.b1 - 3, SODIUM, s);
    mast(a + 41, fld.apron.b0 - 4, SODIUM, s);
  }
  // the finish: a pair of light towers each side of the lakebed runway
  const finA = f.of(fin.x, fin.z);
  const sideA = f.of(fin.x + finDir.dz, fin.z - finDir.dx);
  const side = [sideA[0] - finA[0], sideA[1] - finA[1]];
  for (const k of [-1, 1]) for (const along of [-6, 16]) {
    const fwd = f.of(fin.x + finDir.dx, fin.z + finDir.dz);
    mast(finA[0] + side[0] * k * (HALF + 9) + (fwd[0] - finA[0]) * along, finA[1] + side[1] * k * (HALF + 9) + (fwd[1] - finA[1]) * along, LED, track.finishS);
  }

  // ---------------------------------------------------------------- the airfield's lights
  const L = fld.runway.length;
  // runway edge: every 200 ft, white, amber over the last 2,000 ft; red across the far end, green across the near one
  for (let a = 0; a <= L; a += 60.96) for (const s of [-1, 1]) lights.push({ ...place(a, s * (HALF + 1.5), 0.4), color: a > L - 610 ? AMBER : WHITE, size: 2.3, anim: 0 });
  for (let k = -5; k <= 5; k++) {
    lights.push({ ...place(L + 3, k * 8.2, 0.4), color: RED, size: 2.6, anim: 0 });
    lights.push({ ...place(-3, k * 8.2, 0.4), color: GREEN, size: 2.6, anim: 0 });
  }
  // the approach lights before the threshold of 04R: a bar every 100 ft, the flash running in to the runway
  for (let a = -30.5; a > -915; a -= 30.48) {
    for (let k = -2; k <= 2; k++) lights.push({ ...place(a, k * 1.6, 0.5), color: WHITE, size: 2.2, anim: 0 });
    if (a < -300) lights.push({ ...place(a, 0, 0.8), color: WHITE, size: 6, anim: 10 + (915 + a) / 640 });
  }
  // taxiway edges and the apron's rim: blue
  for (const [a, b] of strips) for (let i = a + 8; i < b; i += 30) for (const s of [-1, 1]) {
    const p = track.pointAt(i, s * (track.pave[i] / 2 + 1.2));
    lights.push({ x: p.x, y: p.y + 0.35, z: p.z, color: BLUE, size: 1.7, anim: 0 });
  }
  for (let a = fld.apron.a0; a <= fld.apron.a1; a += 32) lights.push({ ...place(a, fld.apron.b0 - 1, 0.35), color: BLUE, size: 1.7, anim: 0 });
  // the lakebed has no lights of its own: lanterns stand along the runways' lines where the course follows them
  for (let i = iLake + 40; i < track.count - 30; i += 140) for (const s of [-1, 1]) {
    const p = track.pointAt(i, s * (HALF + 1));
    lights.push({ x: p.x, y: p.y + 0.4, z: p.z, color: AMBER, size: 2.4, anim: 0 });
  }

  // ---------------------------------------------------------------- parked aircraft
  const parked = parkedJets(
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9].filter((k) => k !== 4).map((k) => {
      // on its spot's lead-in line, nose to the taxi lane
      const p = place(fld.apron.a0 + 33 + k * 66, lane + 78, 0);
      return { position: p, heading: HEADING - Math.PI / 2, id: (['f15c', 'f15c', 'f15j', 'su47'] as const)[k % 4] };
    }),
    (id) => CAR_SPECS[id as CarId],
  );
  if (parked) {
    parked.traverse((o) => {
      o.castShadow = shadows;
      o.receiveShadow = true;
    });
    group.add(parked);
  }

  // ---------------------------------------------------------------- meshes
  const wallMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.82, metalness: 0.05 });
  wallMat.name = 'airbase-buildings';
  const litMat = new THREE.MeshStandardMaterial({ color: '#15130f', emissive: '#ffd6a0', emissiveIntensity: 1.0, roughness: 0.6 });
  const glassMat = new THREE.MeshStandardMaterial({ color: '#0a1114', emissive: '#8fd0b8', emissiveIntensity: 0.5, roughness: 0.15, metalness: 0.4 });
  nightEmissive.push(litMat, glassMat);
  for (const [list, m, name] of [[solid, wallMat, 'buildings'], [lit, litMat, 'lit'], [glass, glassMat, 'tower-glass']] as const) {
    if (!list.length) continue;
    const mesh = new THREE.Mesh(mergeGeometries(list), m);
    mesh.name = name;
    mesh.castShadow = shadows && list === solid;
    mesh.receiveShadow = list === solid;
    group.add(mesh);
  }

  const field = fieldLights(lights);
  // the red obstruction lights (`render/beacons.ts`, as on every tall thing in the game): steady on the hangars'
  // roofs, flashing on the tower's mast
  const roofBeacons = buildBeacons(roofLamps), mastBeacons = buildBeacons(mastLamps);
  for (const b of [roofBeacons, mastBeacons]) if (b.object) group.add(b.object);
  group.add(field.object);
  // (the game dims what glows by the time of day through the materials in `nightEmissive`: this one stands for the sprites)
  const dial = new THREE.MeshStandardMaterial({ emissiveIntensity: 1 });
  nightEmissive.push(dial);

  return {
    group,
    lamps,
    roadMaterial,
    nightEmissive,
    terrainMaterial: terrainMat,
    covers: new Float32Array(0),
    shadeScene: shadows ? shadeScene(terrain, casters, []) : null,
    update(time) {
      field.uniforms.uTime.value = time;
      field.uniforms.uIntensity.value = 0.25 + 0.75 * Math.min(1, dial.emissiveIntensity);
      // (a photocell, as the wind turbines': on at night and in the rain's dark, off at dawn)
      const dark = Math.min(1, Math.max(0, (dial.emissiveIntensity - 0.3) / 0.4));
      roofBeacons.level.value = dark;
      mastBeacons.level.value = dark * beaconPulse(time);
    },
  };
}

/** The airfield's lights: one camera-facing quad each, a few pixels wide at any distance, steady or flashing. */
function fieldLights(list: Light[]) {
  const n = list.length;
  const pos = new Float32Array(n * 3), col = new Float32Array(n * 3), size = new Float32Array(n), anim = new Float32Array(n);
  list.forEach((l, i) => {
    pos.set([l.x, l.y, l.z], i * 3);
    col.set(l.color, i * 3);
    size[i] = l.size;
    anim[i] = l.anim;
  });
  const aPos = instancedBufferAttribute(new THREE.InstancedBufferAttribute(pos, 3), 'vec3') as unknown as Vec3;
  const aCol = instancedBufferAttribute(new THREE.InstancedBufferAttribute(col, 3), 'vec3') as unknown as Vec3;
  const aSize = instancedBufferAttribute(new THREE.InstancedBufferAttribute(size, 1), 'float') as unknown as Float;
  const aAnim = instancedBufferAttribute(new THREE.InstancedBufferAttribute(anim, 1), 'float') as unknown as Float;
  const uniforms = { uTime: uniform(0), uIntensity: uniform(1) };
  const mat = new SpriteNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false });
  const t = uniforms.uTime;
  // obstruction lights blink slowly; the beacon turns (a flash every 2.4 s per lens); the approach's flash runs twice a second
  const blink = step(0.5, fract(t.mul(0.5).add(aAnim)));
  const beacon = step(fract(t.mul(0.42).add(aAnim)), 0.07);
  const running = step(fract(t.mul(2).sub(aAnim)), 0.07);
  const on = select(aAnim.greaterThanEqual(10), running, select(aAnim.greaterThanEqual(5), beacon, select(aAnim.greaterThanEqual(2), blink, 1)));
  const dist = modelViewMatrix.mul(vec4(aPos, 1)).z.negate();
  const projY = (cameraProjectionMatrix as unknown as Float[][])[1][1];
  mat.positionNode = aPos;
  // sized in pixels of a 1080-line screen, whatever the distance and the drawing resolution (as the towns' lights)
  mat.sizeAttenuation = false;
  mat.scaleNode = clampNode(aSize.mul(260).div(max(dist, 1)), 2.1, aSize.mul(4.5)).div(1080).mul(2).div(projY);
  const fade = exp(dist.mul(-0.00012));
  mat.colorNode = aCol.mul(on).mul(texture(makeGlowTexture(), uv()).r).mul(uniforms.uIntensity).mul(fade.mul(0.8).add(0.2));
  const object = new THREE.Sprite(mat as unknown as THREE.SpriteMaterial);
  object.count = n;
  object.frustumCulled = false;
  object.name = 'airfield-lights';
  return { object, uniforms };
}
