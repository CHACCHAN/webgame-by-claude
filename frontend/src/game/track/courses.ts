import type { AILevel } from '../ai/AIDriver';
import type { CarId } from '../vehicle/carSpecs';
import { KIRIFURI_LAKESIDE, OBORO_DOWNHILL, TENROU_SKYLINE, type CourseDesign } from './courseDesign';
import { BAY, CALDERA, RIDGE, type Landform } from './landforms';

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
  medals: Record<CarId, { gold: number; silver: number; bronze: number }>;
  music: string;
  /** optional course key art (public path) */
  art: string;
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
    rivals: {
      rookie: { name: '椎名 ほのか', title: 'ROOKIE / 温泉宿の配達係', car: 'hayate', color: '#f6d743', portrait: '/img/rivals/kirifuri-rookie.webp', description: '実家の温泉宿の配達で湖畔道を毎朝往復している。速さの自覚はまだない。' },
      ace: { name: '九条 迅', title: 'LOCAL ACE / 湖畔のチューナー', car: 'raijin', color: '#7a1e2c', portrait: '/img/rivals/kirifuri-ace.webp', description: '湖畔のチューニングショップの若き店長。自分で組んだ車を誰より速く走らせる。' },
      legend: { name: '霧姫', title: 'LEGEND / 霧の中の女王', car: 'shiden', color: '#c9d6e3', power: 1.18, portrait: '/img/rivals/kirifuri-legend.webp', description: '霧が湖を覆う夜にだけ現れる。テールランプを見た者は、その夜を一生忘れない。' },
    },
    medals: {
      hayate: { gold: 90_500, silver: 97_000, bronze: 106_000 },
      raijin: { gold: 80_500, silver: 86_500, bronze: 95_000 },
      shiden: { gold: 84_000, silver: 90_000, bronze: 99_000 },
      supra: { gold: 81_500, silver: 87_500, bronze: 96_000 },
      r34: { gold: 79_000, silver: 85_000, bronze: 93_000 },
      s15: { gold: 85_500, silver: 91_500, bronze: 100_500 },
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
    rivals: {
      rookie: { name: '大河内 拓也', title: 'ROOKIE / 大学自動車部', car: 'hayate', color: '#2f6db5', portrait: '/img/rivals/tenrou-rookie.webp', description: '大学自動車部の二年生。理論派だが、実戦の経験はまだ浅い。' },
      ace: { name: '真壁 冴子', title: 'LOCAL ACE / 元ラリードライバー', car: 'raijin', color: '#e6e6e6', portrait: '/img/rivals/tenrou-ace.webp', description: '元ラリードライバー。高速コーナーでの迷いのなさは圧倒的。' },
      legend: { name: '天狼', title: 'LEGEND / 稜線の狼', car: 'shiden', color: '#202428', power: 1.18, portrait: '/img/rivals/tenrou-legend.webp', description: '頬に傷を持つ寡黙な男。「狼が走る夜は風が止む」と噂される。' },
    },
    medals: {
      hayate: { gold: 84_500, silver: 91_000, bronze: 100_000 },
      raijin: { gold: 73_000, silver: 78_500, bronze: 86_000 },
      shiden: { gold: 76_000, silver: 82_000, bronze: 90_000 },
      supra: { gold: 74_000, silver: 79_500, bronze: 87_500 },
      r34: { gold: 72_000, silver: 77_500, bronze: 85_500 },
      s15: { gold: 77_000, silver: 83_000, bronze: 91_000 },
    },
    music: 'bgm_race_tenrou',
    art: '/img/courses/tenrou.webp',
  },
};

export const COURSE_ORDER: CourseId[] = ['oboro-downhill', 'kirifuri-lakeside', 'tenrou-skyline'];
export const DEFAULT_COURSE: CourseId = 'oboro-downhill';
