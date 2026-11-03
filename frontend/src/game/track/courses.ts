import type { AILevel } from '../ai/AIDriver';
import type { CarId, RoadCarId } from '../vehicle/carSpecs';
import { KIRIFURI_LAKESIDE, OBORO_DOWNHILL, TENROU_SKYLINE, type CourseDesign } from './courseDesign';
import { BAY, CALDERA, RIDGE, type Landform } from './landforms';
import type { TrainId } from '../vehicle/trains';

export type CourseId = 'oboro-downhill' | 'kirifuri-lakeside' | 'tenrou-skyline';

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
}

export interface CourseInfo {
  id: CourseId;
  name: string;
  nameEn: string;
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
    tagline: '港町の夜景を見下ろすヘアピン地獄',
    description: '断崖の展望コーナーから 4 連続ヘアピン、ロックシェッド、渓谷の橋へ。眼下に港町の灯りが広がる、夜の峠の王道コース。',
    design: OBORO_DOWNHILL,
    landform: BAY,
    surface: { grip: 1, label: '年季の入った峠の舗装' },
    rivals: {
      rookie: { name: '森 健太', title: 'ROOKIE / 走り始めた新人', car: 'hayate', color: '#f2b705', portrait: '/img/rivals/oboro-rookie.webp', description: '免許を取ったばかりの新人。ラインは甘いが、峠への情熱は本物。' },
      ace: { name: '高嶺 遼', title: 'LOCAL ACE / 朧峠の地元最速', car: 'raijin', color: '#0c0c0e', portrait: '/img/rivals/oboro-ace.webp', description: '朧峠を知り尽くした地元最速の男。ミスを待っていても勝てない。' },
      legend: { name: '朧', title: 'LEGEND / 夜を走る幽霊', car: 'shiden', color: '#e9e9ea', portrait: '/img/rivals/oboro-legend.webp', description: '夜明け前にだけ現れるという白い影。誰も、その背中に追いついたことがない。' },
    },
    medals: {
      hayate: { gold: 108_000, silver: 115_000, bronze: 125_000 },
      raijin: { gold: 96_000, silver: 103_000, bronze: 113_000 },
      shiden: { gold: 97_000, silver: 104_000, bronze: 115_000 },
      supra: { gold: 98_500, silver: 105_000, bronze: 115_500 },
      r34: { gold: 95_000, silver: 101_500, bronze: 111_500 },
      s15: { gold: 101_500, silver: 109_000, bronze: 119_500 },
    },
    music: 'bgm_race',
    art: '/img/keyart.webp',
  },
  'kirifuri-lakeside': {
    id: 'kirifuri-lakeside',
    name: '霧降湖',
    nameEn: 'KIRIFURI LAKESIDE',
    tagline: '月を映すカルデラ湖へ駆け下りる',
    description: '外輪山の稜線から杉林のヘアピンを抜け、湖畔の高速セクションへ。水面に映る月と温泉街の灯りが待つ、テクニカルで速いコース。',
    design: KIRIFURI_LAKESIDE,
    landform: CALDERA,
    // the lake mist leaves the road damp
    surface: { grip: 0.92, label: '湖の霧で湿った路面（滑りやすい）' },
    rivals: {
      rookie: { name: '椎名 ほのか', title: 'ROOKIE / 温泉宿の配達係', car: 'hayate', color: '#f6d743', portrait: '/img/rivals/kirifuri-rookie.webp', description: '実家の温泉宿の配達で湖畔道を毎朝往復している。速さの自覚はまだない。' },
      ace: { name: '九条 迅', title: 'LOCAL ACE / 湖畔のチューナー', car: 'raijin', color: '#7a1e2c', portrait: '/img/rivals/kirifuri-ace.webp', description: '湖畔のチューニングショップの若き店長。自分で組んだ車を誰より速く走らせる。' },
      legend: { name: '霧姫', title: 'LEGEND / 霧の中の女王', car: 'shiden', color: '#c9d6e3', power: 1.18, portrait: '/img/rivals/kirifuri-legend.webp', description: '霧が湖を覆う夜にだけ現れる。テールランプを見た者は、その夜を一生忘れない。' },
    },
    medals: {
      hayate: { gold: 92_000, silver: 98_500, bronze: 107_500 },
      raijin: { gold: 81_500, silver: 87_500, bronze: 96_500 },
      shiden: { gold: 85_000, silver: 91_500, bronze: 100_500 },
      supra: { gold: 82_500, silver: 88_500, bronze: 97_500 },
      r34: { gold: 80_000, silver: 86_000, bronze: 94_500 },
      s15: { gold: 86_500, silver: 93_000, bronze: 102_000 },
    },
    music: 'bgm_race_kirifuri',
    art: '/img/courses/kirifuri.webp',
  },
  'tenrou-skyline': {
    id: 'tenrou-skyline',
    name: '天狼スカイライン',
    nameEn: 'TENROU SKYLINE',
    tagline: '星空の稜線を全開で駆け抜ける',
    description: '風車の並ぶ稜線を200km/h近くで駆け抜け、最後は七曲りのヘアピンで一気に谷へ。度胸とブレーキングが試される高速コース。',
    design: TENROU_SKYLINE,
    landform: RIDGE,
    // a toll skyline: fresh, coarse asphalt
    surface: { grip: 1.04, label: '新しい有料道路の舗装（高グリップ）' },
    rivals: {
      rookie: { name: '大河内 拓也', title: 'ROOKIE / 大学自動車部', car: 'hayate', color: '#2f6db5', portrait: '/img/rivals/tenrou-rookie.webp', description: '大学自動車部の二年生。理論派だが、実戦の経験はまだ浅い。' },
      ace: { name: '真壁 冴子', title: 'LOCAL ACE / 元ラリードライバー', car: 'raijin', color: '#e6e6e6', portrait: '/img/rivals/tenrou-ace.webp', description: '元ラリードライバー。高速コーナーでの迷いのなさは圧倒的。' },
      legend: { name: '天狼', title: 'LEGEND / 稜線の狼', car: 'shiden', color: '#202428', power: 1.18, portrait: '/img/rivals/tenrou-legend.webp', description: '頬に傷を持つ寡黙な男。「狼が走る夜は風が止む」と噂される。' },
    },
    medals: {
      hayate: { gold: 84_000, silver: 90_500, bronze: 99_500 },
      raijin: { gold: 72_500, silver: 78_000, bronze: 85_500 },
      shiden: { gold: 75_500, silver: 81_500, bronze: 89_500 },
      supra: { gold: 73_500, silver: 79_000, bronze: 87_000 },
      r34: { gold: 71_500, silver: 77_000, bronze: 85_000 },
      s15: { gold: 76_500, silver: 82_500, bronze: 90_500 },
    },
    music: 'bgm_race_tenrou',
    art: '/img/courses/tenrou.webp',
  },
};

export const COURSE_ORDER: CourseId[] = ['oboro-downhill', 'kirifuri-lakeside', 'tenrou-skyline'];
export const DEFAULT_COURSE: CourseId = 'oboro-downhill';

/**
 * Medal times of the trains (joke entries) per course: gold = the legend AI's time with that train
 * (tools/sim-run.ts, 2026-11-03), silver +7 %, bronze +16 %. Runs where the AI could not stop in time and
 * respawned (N700 on 朧峠; E231 on 天狼) were replaced by their clean earlier runs or an estimate.
 * With the road grip per course (`surface`) the 霧降湖 and 天狼 medals of cars and trains were scaled by its mean
 * effect on the legend AI's laps (×1.014 and ×0.995). The Keikyu N1000 came later (same date, already with the
 * road grip): 147.93 / 119.33 / 118.73 s, no respawns.
 */
export const TRAIN_MEDALS: Record<CourseId, Record<TrainId, { gold: number; silver: number; bronze: number }>> = {
  'oboro-downhill': {
    e231: { gold: 151_500, silver: 162_000, bronze: 175_500 },
    keikyu1000: { gold: 148_000, silver: 158_500, bronze: 171_500 },
    ginza1000: { gold: 147_500, silver: 158_000, bronze: 171_000 },
    n700: { gold: 148_000, silver: 158_500, bronze: 171_500 },
  },
  'kirifuri-lakeside': {
    e231: { gold: 128_500, silver: 137_500, bronze: 148_500 },
    keikyu1000: { gold: 119_500, silver: 128_000, bronze: 138_500 },
    ginza1000: { gold: 130_500, silver: 139_500, bronze: 151_000 },
    n700: { gold: 116_000, silver: 124_000, bronze: 135_000 },
  },
  'tenrou-skyline': {
    e231: { gold: 127_000, silver: 136_000, bronze: 147_500 },
    keikyu1000: { gold: 119_000, silver: 127_500, bronze: 138_000 },
    ginza1000: { gold: 126_500, silver: 135_500, bronze: 146_500 },
    n700: { gold: 124_500, silver: 133_500, bronze: 144_500 },
  },
};

/**
 * Medal times of the cockroach (joke entry) per course: gold = the legend AI's time with it (tools/sim-run.ts,
 * 2026-11-03), silver +7 %, bronze +16 %. The AI keeps to its 223 km/h cap on the straights: a player can beat gold.
 */
export const ROACH_MEDALS: Record<CourseId, { gold: number; silver: number; bronze: number }> = {
  'oboro-downhill': { gold: 76_000, silver: 81_500, bronze: 88_000 },
  'kirifuri-lakeside': { gold: 63_000, silver: 67_500, bronze: 73_000 },
  'tenrou-skyline': { gold: 55_500, silver: 59_500, bronze: 64_500 },
};
