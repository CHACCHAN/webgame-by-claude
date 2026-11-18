import type { AILevel } from '../ai/AIDriver';
import type { CarId, RoadCarId } from '../vehicle/carSpecs';
import { AUTOBAHN, EDWARDS, KIRIFURI_LAKESIDE, OBORO_DOWNHILL, TENROU_SKYLINE, type CourseDesign } from './courseDesign';
import { BAY, CALDERA, MOJAVE, PLATEAU, RIDGE, type Landform } from './landforms';
import type { JetId } from '../vehicle/jets';
import { RELEASED } from '../release';
import type { TrainId } from '../vehicle/trains';
import type { BikeId } from '../vehicle/bikes';
import type { VoiceId } from '../audio/speech/text';

export type CourseId = 'oboro-downhill' | 'kirifuri-lakeside' | 'tenrou-skyline' | 'autobahn' | 'edwards';

/**
 * a Japanese mountain pass, a German motorway (no Japanese roadside dressing, motorway structures instead), or an
 * air base in the desert (render/airbaseScenery.ts: aprons, a runway, a dry lake; no roadside at all)
 */
export type CourseStyle = 'touge' | 'autobahn' | 'airbase';

export interface RivalInfo {
  name: string;
  title: string;
  car: CarId;
  color: string;
  description: string;
  /** optional portrait (public path); a silhouette is shown when missing */
  portrait: string;
  /** engine tune of the rival's car (legend cars are tuned) */
  power?: number;
  /** the voice its lines are spoken in (audio/speech: one of the speech model's ten) */
  voice: VoiceId;
}

export interface CourseInfo {
  id: CourseId;
  name: string;
  nameEn: string;
  style: CourseStyle;
  tagline: string;
  description: string;
  design: CourseDesign;
  landform: Landform;
  rivals: Record<AILevel, RivalInfo>;
  /** medal target times per car (ms, standing start) */
  /** per car; the trains' come from TRAIN_MEDALS below (filled from simulated runs) */
  medals: Record<RoadCarId, { gold: number; silver: number; bronze: number }>;
  music: string;
  /** optional course key art (public path) */
  art: string;
  /** road surface: tyre grip factor (1 = ordinary dry asphalt; rain takes a further share off) and its label */
  surface: { grip: number; label: string };
}

export const COURSES: Record<CourseId, CourseInfo> = {
  'oboro-downhill': {
    id: 'oboro-downhill',
    name: '朧峠',
    nameEn: 'OBORO PASS',
    style: 'touge',
    tagline: '港町の夜景を見下ろすヘアピン地獄',
    description: '断崖の展望コーナーから 4 連続ヘアピン、ロックシェッド、渓谷の橋へ。眼下に港町の灯りが広がる、夜の峠の王道コース。',
    design: OBORO_DOWNHILL,
    landform: BAY,
    surface: { grip: 1, label: '年季の入った峠の舗装' },
    rivals: {
      rookie: { name: '森 健太', voice: 'M1', title: 'ROOKIE / 走り始めた新人', car: 'hayate', color: '#f2b705', portrait: '/img/rivals/oboro-rookie.webp', description: '免許を取ったばかりの新人。ラインは甘いが、峠への情熱は本物。' },
      ace: { name: '高嶺 遼', voice: 'M2', title: 'LOCAL ACE / 朧峠の地元最速', car: 'raijin', color: '#0c0c0e', portrait: '/img/rivals/oboro-ace.webp', description: '朧峠を知り尽くした地元最速の男。ミスを待っていても勝てない。' },
      legend: { name: '朧', voice: 'M3', title: 'LEGEND / 夜を走る幽霊', car: 'shiden', color: '#e9e9ea', portrait: '/img/rivals/oboro-legend.webp', description: '夜明け前にだけ現れるという白い影。誰も、その背中に追いついたことがない。' },
    },
    medals: {
      hayate: { gold: 108_000, silver: 115_000, bronze: 125_000 },
      raijin: { gold: 96_000, silver: 103_000, bronze: 113_000 },
      shiden: { gold: 97_000, silver: 104_000, bronze: 115_000 },
      supra: { gold: 98_500, silver: 105_000, bronze: 115_500 },
      r34: { gold: 95_000, silver: 101_500, bronze: 111_500 },
      cybertruck: { gold: 97_500, silver: 104_500, bronze: 114_000 },
      u9: { gold: 79_500, silver: 85_000, bronze: 93_000 },
      su7: { gold: 91_000, silver: 97_500, bronze: 106_500 },
      s15: { gold: 101_500, silver: 109_000, bronze: 119_500 },
    },
    music: 'bgm_race',
    art: '/img/keyart.webp',
  },
  'kirifuri-lakeside': {
    id: 'kirifuri-lakeside',
    name: '霧降湖',
    nameEn: 'KIRIFURI LAKESIDE',
    style: 'touge',
    tagline: '月を映すカルデラ湖へ駆け下りる',
    description: '外輪山の稜線から杉林のヘアピンを抜け、湖畔の高速セクションへ。水面に映る月と温泉街の灯りが待つ、テクニカルで速いコース。',
    design: KIRIFURI_LAKESIDE,
    landform: CALDERA,
    // the lake mist leaves the road damp
    surface: { grip: 0.92, label: '湖の霧で湿った路面（滑りやすい）' },
    rivals: {
      rookie: { name: '椎名 ほのか', voice: 'F1', title: 'ROOKIE / 温泉宿の配達係', car: 'hayate', color: '#f6d743', portrait: '/img/rivals/kirifuri-rookie.webp', description: '実家の温泉宿の配達で湖畔道を毎朝往復している。速さの自覚はまだない。' },
      ace: { name: '九条 迅', voice: 'M4', title: 'LOCAL ACE / 湖畔のチューナー', car: 'raijin', color: '#7a1e2c', portrait: '/img/rivals/kirifuri-ace.webp', description: '湖畔のチューニングショップの若き店長。自分で組んだ車を誰より速く走らせる。' },
      legend: { name: '霧姫', voice: 'F2', title: 'LEGEND / 霧の中の女王', car: 'shiden', color: '#c9d6e3', power: 1.18, portrait: '/img/rivals/kirifuri-legend.webp', description: '霧が湖を覆う夜にだけ現れる。テールランプを見た者は、その夜を一生忘れない。' },
    },
    medals: {
      hayate: { gold: 92_000, silver: 98_500, bronze: 107_500 },
      raijin: { gold: 81_500, silver: 87_500, bronze: 96_500 },
      shiden: { gold: 85_000, silver: 91_500, bronze: 100_500 },
      supra: { gold: 82_500, silver: 88_500, bronze: 97_500 },
      r34: { gold: 80_000, silver: 86_000, bronze: 94_500 },
      cybertruck: { gold: 83_000, silver: 89_000, bronze: 97_000 },
      u9: { gold: 68_500, silver: 73_500, bronze: 80_000 },
      su7: { gold: 77_000, silver: 82_500, bronze: 90_500 },
      s15: { gold: 86_500, silver: 93_000, bronze: 102_000 },
    },
    music: 'bgm_race_kirifuri',
    art: '/img/courses/kirifuri.webp',
  },
  'tenrou-skyline': {
    id: 'tenrou-skyline',
    name: '天狼スカイライン',
    nameEn: 'TENROU SKYLINE',
    style: 'touge',
    tagline: '星空の稜線を全開で駆け抜ける',
    description: '風車の並ぶ稜線を200km/h近くで駆け抜け、最後は七曲りのヘアピンで一気に谷へ。度胸とブレーキングが試される高速コース。',
    design: TENROU_SKYLINE,
    landform: RIDGE,
    // a toll skyline: fresh, coarse asphalt
    surface: { grip: 1.04, label: '新しい有料道路の舗装（高グリップ）' },
    rivals: {
      rookie: { name: '大河内 拓也', voice: 'M5', title: 'ROOKIE / 大学自動車部', car: 'hayate', color: '#2f6db5', portrait: '/img/rivals/tenrou-rookie.webp', description: '大学自動車部の二年生。理論派だが、実戦の経験はまだ浅い。' },
      ace: { name: '真壁 冴子', voice: 'F3', title: 'LOCAL ACE / 元ラリードライバー', car: 'raijin', color: '#e6e6e6', portrait: '/img/rivals/tenrou-ace.webp', description: '元ラリードライバー。高速コーナーでの迷いのなさは圧倒的。' },
      legend: { name: '天狼', voice: 'M3', title: 'LEGEND / 稜線の狼', car: 'shiden', color: '#202428', power: 1.18, portrait: '/img/rivals/tenrou-legend.webp', description: '頬に傷を持つ寡黙な男。「狼が走る夜は風が止む」と噂される。' },
    },
    medals: {
      hayate: { gold: 84_000, silver: 90_500, bronze: 99_500 },
      raijin: { gold: 72_500, silver: 78_000, bronze: 85_500 },
      shiden: { gold: 75_500, silver: 81_500, bronze: 89_500 },
      supra: { gold: 73_500, silver: 79_000, bronze: 87_000 },
      r34: { gold: 71_500, silver: 77_000, bronze: 85_000 },
      cybertruck: { gold: 73_000, silver: 78_000, bronze: 85_500 },
      u9: { gold: 60_500, silver: 64_500, bronze: 71_000 },
      su7: { gold: 68_000, silver: 73_000, bronze: 80_000 },
      s15: { gold: 76_500, silver: 82_500, bronze: 90_500 },
    },
    music: 'bgm_race_tenrou',
    art: '/img/courses/tenrou.webp',
  },
  autobahn: {
    id: 'autobahn',
    name: 'アウトバーン',
    nameEn: 'AUTOBAHN',
    style: 'autobahn',
    tagline: '速度無制限、夜の高原を一直線に',
    description: '森の高原から川の谷へ、約8kmを下る3車線の高速道路。跨道橋をくぐり、高架橋で谷を越える。カーブはすべて半径1200m以上、全開のまま踏み抜け。',
    design: AUTOBAHN,
    landform: PLATEAU,
    surface: { grip: 1, label: '高速道路の舗装' },
    rivals: {
      // a drag race: no corner sorts the field, so the rivals' cars and tunes set the battle (tools/sim-run.ts):
      // the rookie loses to any car driven flat out, the ace to the R34 and the RX-7, the legend only to a clean RX-7
      rookie: { name: '早瀬 ユリア', voice: 'F4', title: 'ROOKIE / 留学帰りの新人', car: 'hayate', color: '#d8dde4', power: 0.95, portrait: '/img/rivals/autobahn-rookie.webp', description: 'ドイツ留学から帰ったばかり。速度無制限の道に憧れて、初めて夜のアウトバーンに挑む。' },
      ace: { name: '神崎 ルカ', voice: 'M4', title: 'LOCAL ACE / 深夜便の運び屋', car: 'supra', color: '#14161a', portrait: '/img/rivals/autobahn-ace.webp', description: '夜ごとこの道を往復する運び屋。追い越し車線の空け方まで知り尽くしている。' },
      legend: { name: 'ファルケ', voice: 'F5', title: 'LEGEND / 無制限区間の亡霊', car: 'r34', color: '#9aa4ae', power: 1.02, portrait: '/img/rivals/autobahn-legend.webp', description: '鷹の名で呼ばれる正体不明のドライバー。ミラーに映ったと思った時には、もう前にいる。' },
    },
    // flat out from a standing start, the legend AI's race time +1.5 % (a clean run; no corner to gain time in),
    // silver +7 %, bronze +17 % (tools/sim-run.ts, 2026-11-06)
    medals: {
      hayate: { gold: 177_000, silver: 189_500, bronze: 207_500 },
      raijin: { gold: 134_000, silver: 143_500, bronze: 157_000 },
      shiden: { gold: 130_500, silver: 140_000, bronze: 153_000 },
      supra: { gold: 134_500, silver: 144_000, bronze: 157_500 },
      r34: { gold: 132_500, silver: 142_000, bronze: 155_500 },
      cybertruck: { gold: 142_500, silver: 152_500, bronze: 166_500 },
      u9: { gold: 65_500, silver: 70_000, bronze: 76_500 },
      su7: { gold: 116_000, silver: 124_500, bronze: 136_000 },
      s15: { gold: 145_000, silver: 155_500, bronze: 170_000 },
    },
    music: 'bgm_race_autobahn',
    art: '/img/courses/autobahn.webp',
  },
  edwards: {
    id: 'edwards',
    name: 'エドワーズ空軍基地',
    nameEn: 'EDWARDS AFB',
    style: 'airbase',
    tagline: '滑走路04Rから乾湖へ、音速の手前まで',
    description: 'モハーヴェ砂漠の試験飛行の聖地。駐機場から誘導路を抜け、4.6kmのコンクリート滑走路を全開で駆け、ロジャース乾湖のコンパスローズをかすめて湖面滑走路へ。約12km、壁はひとつもない。戦闘機はここでだけ走れる。',
    design: EDWARDS,
    landform: MOJAVE,
    // dry concrete; the lakebed's clay gives less (`CourseDesign.zoneGrip`)
    surface: { grip: 1, label: '乾いたコンクリートと乾湖の粘土（湖面は滑りやすい）' },
    rivals: {
      // the ace and the legend come in fighters. Their AI needs 208 s / 189 s (tools/sim-run.ts): slow on the taxiway,
      // out of sight on the runway. A sports car's legend lap is 227–232 s, the Ninja H2's 168 s, the U9's 128 s: with
      // most cars it is a race into the first turn and a long look at two afterburners
      rookie: { name: 'ノーラ・ヘイズ', voice: 'F4', title: 'ROOKIE / 整備班の新人', car: 'cybertruck', color: '#c8ccd0', portrait: '', description: 'フライトラインの整備班に来たばかり。夜勤明けに、牽引車がわりのトラックで滑走路を走るのが楽しみ。' },
      ace: { name: 'デイル・マッケンジー', voice: 'M2', title: 'LOCAL ACE / 412試験航空団のテストパイロット', car: 'f15c', color: '#7f8890', portrait: '', description: 'EDのテイルコードを背負うイーグル乗り。この滑走路の継ぎ目の数まで知っている。' },
      legend: { name: 'ベールクト', voice: 'M3', title: 'LEGEND / 乾湖に現れる黒い前進翼', car: 'su47', color: '#3b4049', portrait: '', description: '記録にない夜、湖面にだけ現れるという黒い機体。誰が乗っているのか、基地の誰も知らない。' },
    },
    // mostly flat out, like the autobahn: the legend AI's time +1.5 % (clean runs), silver +7 %, bronze +17 %
    // (EDWARDS=1 COURSE=edwards npx tsx tools/sim-run.ts <cars> legend, 2026-11-12)
    medals: {
      hayate: { gold: 293_500, silver: 309_500, bronze: 338_500 },
      raijin: { gold: 234_000, silver: 246_500, bronze: 269_500 },
      shiden: { gold: 230_500, silver: 243_000, bronze: 266_000 },
      supra: { gold: 235_000, silver: 248_000, bronze: 271_000 },
      r34: { gold: 233_500, silver: 246_000, bronze: 269_500 },
      cybertruck: { gold: 237_500, silver: 250_000, bronze: 273_500 },
      u9: { gold: 129_500, silver: 136_500, bronze: 149_500 },
      su7: { gold: 201_500, silver: 212_000, bronze: 232_500 },
      s15: { gold: 252_000, silver: 265_500, bronze: 290_500 },
    },
    // (no track of its own: the motorway's, the other flat-out course)
    music: 'bgm_race_autobahn',
    art: '/img/courses/edwards.webp',
  },
};

/** every course there is, shown to players or not yet (tests and tools) */
export const ALL_COURSES: CourseId[] = ['oboro-downhill', 'kirifuri-lakeside', 'tenrou-skyline', 'autobahn', 'edwards'];
/** the courses a player can choose (Edwards with its fighters once released: `release.ts`) */
export const COURSE_ORDER: CourseId[] = ALL_COURSES.filter((id) => id !== 'edwards' || RELEASED.edwards);
export const DEFAULT_COURSE: CourseId = 'oboro-downhill';

/**
 * Medal times of the trains (joke entries) per course: gold = the legend AI's time with that train
 * (tools/sim-run.ts, with the course's road grip), silver +7 %, bronze +16 %. Re-run on 2026-11-03 after the trains'
 * tractive effort got its jerk-limited build-up (`TRACTION_RISE`): the clean laps moved by −2…+3 %, the AI's own
 * spread. The E231 keeps its earlier medals (its runs respawned then). E235, Tobu 30000 and E5 from 2026-11-04 runs,
 * all clean; the L0 from 2026-11-10 runs (no respawn; it floats from 150 km/h, which the passes hardly reach).
 */
export const TRAIN_MEDALS: Record<CourseId, Record<TrainId, { gold: number; silver: number; bronze: number }>> = {
  'oboro-downhill': {
    e231: { gold: 151_500, silver: 162_000, bronze: 175_500 },
    e235: { gold: 148_500, silver: 159_000, bronze: 172_500 },
    keikyu1000: { gold: 145_500, silver: 155_500, bronze: 169_000 },
    tobu30000: { gold: 152_500, silver: 163_000, bronze: 177_000 },
    e5: { gold: 158_500, silver: 169_500, bronze: 184_000 },
    l0: { gold: 148_000, silver: 158_500, bronze: 171_500 },
  },
  'kirifuri-lakeside': {
    e231: { gold: 126_500, silver: 135_500, bronze: 146_500 },
    e235: { gold: 122_500, silver: 131_000, bronze: 142_000 },
    keikyu1000: { gold: 121_000, silver: 129_500, bronze: 140_500 },
    tobu30000: { gold: 123_500, silver: 132_000, bronze: 143_500 },
    e5: { gold: 129_000, silver: 138_000, bronze: 149_500 },
    l0: { gold: 121_000, silver: 129_500, bronze: 140_500 },
  },
  'tenrou-skyline': {
    e231: { gold: 127_000, silver: 136_000, bronze: 147_500 },
    e235: { gold: 122_500, silver: 131_000, bronze: 142_000 },
    keikyu1000: { gold: 118_500, silver: 127_000, bronze: 137_500 },
    tobu30000: { gold: 117_500, silver: 125_500, bronze: 136_500 },
    e5: { gold: 128_500, silver: 137_500, bronze: 149_000 },
    l0: { gold: 114_500, silver: 122_500, bronze: 133_000 },
  },
  // the autobahn (2026-11-06): the legend AI's time from a standing start at GO, as a race times it (the trains' slow
  // getaway is a share of the time here; the AI drives the course flat out without a fault, so a flying lap would
  // put gold out of reach). The E5 reaches 305 km/h before the finish.
  autobahn: {
    e231: { gold: 262_000, silver: 280_500, bronze: 304_000 },
    e235: { gold: 257_500, silver: 276_000, bronze: 299_000 },
    keikyu1000: { gold: 240_000, silver: 257_000, bronze: 278_500 },
    tobu30000: { gold: 255_000, silver: 273_000, bronze: 296_000 },
    e5: { gold: 174_000, silver: 186_500, bronze: 202_000 },
    l0: { gold: 130_000, silver: 139_000, bronze: 151_000 },
  },
  // Edwards (2026-11-12; `LIMIT=700`: the commuter trains need seven minutes): the E235, the Tobu, the Keikyu, the
  // E5 and the L0 each ran off a quarter turn of the taxiway once and were put back (a train does not take 51 m)
  edwards: {
    e231: { gold: 436_500, silver: 467_000, bronze: 506_000 },
    e235: { gold: 431_000, silver: 461_000, bronze: 500_000 },
    keikyu1000: { gold: 406_000, silver: 434_500, bronze: 471_000 },
    tobu30000: { gold: 425_000, silver: 454_500, bronze: 493_000 },
    e5: { gold: 331_000, silver: 354_500, bronze: 384_000 },
    l0: { gold: 265_000, silver: 283_500, bronze: 307_500 },
  },
};

/**
 * Medal times of the cockroach (joke entry) per course: gold = the legend AI's time with it (tools/sim-run.ts,
 * 2026-11-10, after its grip, pull and brakes were doubled and its top speed set to Mach 1), silver +7 %, bronze +16 %.
 * On the mountain passes the AI keeps to its 223 km/h cap on the straights and brushes the walls (on 霧降 it rolls once):
 * a player can beat gold by far. The autobahn's cap lets it run (989 km/h: the AI's corner speeds leave out the
 * downforce; a player can hold Mach 1 for ~5 km there).
 */
export const ROACH_MEDALS: Record<CourseId, { gold: number; silver: number; bronze: number }> = {
  'oboro-downhill': { gold: 58_500, silver: 62_500, bronze: 68_000 },
  'kirifuri-lakeside': { gold: 50_000, silver: 53_500, bronze: 58_000 },
  'tenrou-skyline': { gold: 44_000, silver: 47_000, bronze: 51_000 },
  // the autobahn: from a standing start (as TRAIN_MEDALS)
  autobahn: { gold: 35_500, silver: 38_000, bronze: 41_000 },
  // Edwards: the legend AI's run, clean (1226 km/h on the runway), 2026-11-12
  edwards: { gold: 71_500, silver: 76_500, bronze: 83_000 },
};

/**
 * Medal times of the motorcycles per course: gold = the legend AI's time with the bike (tools/sim-run.ts, 2026-11-10,
 * all clean: no wall touched), silver +7 %, bronze +16 % (as the cockroach's). On the passes the AI keeps to its
 * 223 km/h cap like every vehicle; the autobahn from a standing start.
 */
export const BIKE_MEDALS: Record<CourseId, Record<BikeId, { gold: number; silver: number; bronze: number }>> = {
  'oboro-downhill': {
    nsr250r: { gold: 97_500, silver: 104_500, bronze: 113_000 },
    ninjah2: { gold: 84_500, silver: 90_500, bronze: 98_000 },
    hayabusa: { gold: 87_000, silver: 93_000, bronze: 101_000 },
  },
  'kirifuri-lakeside': {
    nsr250r: { gold: 82_500, silver: 88_500, bronze: 95_500 },
    ninjah2: { gold: 72_500, silver: 77_500, bronze: 84_000 },
    hayabusa: { gold: 74_500, silver: 79_500, bronze: 86_500 },
  },
  'tenrou-skyline': {
    nsr250r: { gold: 71_500, silver: 76_500, bronze: 83_000 },
    ninjah2: { gold: 60_500, silver: 64_500, bronze: 70_000 },
    hayabusa: { gold: 62_000, silver: 66_500, bronze: 72_000 },
  },
  autobahn: {
    nsr250r: { gold: 154_000, silver: 165_000, bronze: 178_500 },
    ninjah2: { gold: 90_500, silver: 97_000, bronze: 105_000 },
    hayabusa: { gold: 95_500, silver: 102_000, bronze: 111_000 },
  },
  // Edwards (2026-11-12, clean)
  edwards: {
    nsr250r: { gold: 262_500, silver: 281_000, bronze: 304_500 },
    ninjah2: { gold: 167_500, silver: 179_500, bronze: 194_500 },
    hayabusa: { gold: 176_500, silver: 189_000, bronze: 205_000 },
  },
};

/**
 * Medal times of the fighters at Edwards, the only course they run on: gold = the legend AI's time (tools/sim-run.ts,
 * 2026-11-12, no respawn), silver +7 %, bronze +16 %. The AI keeps a wide margin in the taxiway's quarter turns
 * (0.42 g at 52 km/h) and brakes from the middle of the runway for the lake's sweep: a player who dares more beats
 * gold by far. The three come out alike because the taxiway and the sweep, not the thrust, set the time.
 */
export const JET_MEDALS: Record<JetId, { gold: number; silver: number; bronze: number }> = {
  f15j: { gold: 189_000, silver: 202_000, bronze: 219_000 },
  f15c: { gold: 188_500, silver: 201_500, bronze: 218_500 },
  su47: { gold: 188_500, silver: 202_000, bronze: 219_000 },
};
