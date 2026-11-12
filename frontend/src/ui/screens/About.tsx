import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { REVISION } from 'three';
import { useApp } from '../../store/app';
import { useDesk } from '../../store/desk';
import { useSettings, type QualityLevel } from '../../store/settings';
import { useMenuInput } from '../useMenuInput';
import { COURSES, COURSE_ORDER } from '../../game/track/courses';
import { VEHICLE_ORDER } from '../../game/vehicle/carSpecs';
import { PHYSICS_HZ } from '../../game/vehicle/PhysicsWorld';
import { TRAIN_INFO, TRAIN_ORDER } from '../../game/vehicle/trains';
import { MODEL_BASE } from '../../game/audio/speech/protocol';
import { versionLabel } from '../../version';
import { sfx } from '../sfx';
import { Count, FocusFrame, Hint, ScreenHead } from '../kit';
import { DeskSection } from './AboutDesk';
import { gpuName } from './aboutFacts';

/**
 * ABOUT (main menu): what the game is, who made it, what it is built with, whose work it stands on, and the desk
 * (AI窓口: questions about the game, bug reports and requests). Five sections on a tab row: ← → (Q / E) change the
 * section, ↑ ↓ scroll it, Enter on the desk goes into its text field.
 *
 * Who made it is the server's configuration (`/api/content` `about`): no name is written here.
 */

type Section = 'game' | 'maker' | 'tech' | 'credits' | 'desk';
const SECTIONS: { id: Section; en: string; jp: string }[] = [
  { id: 'game', en: 'OVERVIEW', jp: '概要' },
  { id: 'maker', en: 'MAKER', jp: 'つくった人' },
  { id: 'tech', en: 'TECH', jp: '技術' },
  { id: 'credits', en: 'CREDITS', jp: 'クレジット' },
  { id: 'desk', en: 'DESK', jp: 'AI窓口' },
];

/** the section left open last: back on the screen, it is open again */
let lastSection: Section = 'game';

/** a field of the desk has the keys: the screen's own keys rest (the fields keep their key events to themselves) */
const typing = () => {
  const el = document.activeElement;
  return el instanceof HTMLElement && (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT');
};

export function AboutScreen() {
  const go = useApp((s) => s.go);
  const [section, setSection] = useState<Section>(lastSection);
  const at = SECTIONS.findIndex((s) => s.id === section);
  const body = useRef<HTMLDivElement>(null);
  const open = (id: Section) => {
    lastSection = id;
    setSection(id);
  };
  const step = (d: number) => {
    open(SECTIONS[(at + d + SECTIONS.length) % SECTIONS.length].id);
    sfx.tab();
  };
  useEffect(() => {
    void useDesk.getState().load();
  }, []);
  useMenuInput((a) => {
    // (only a pad gets here while a field is being typed in: its B leaves the field, nothing else moves)
    if (typing()) {
      if (a === 'back') (document.activeElement as HTMLElement).blur();
      return;
    }
    if (a === 'left' || a === 'prevTab') step(-1);
    if (a === 'right' || a === 'nextTab') step(1);
    if (a === 'up' || a === 'down') {
      // the section's text, or on the desk its conversation
      const el = body.current?.querySelector<HTMLElement>('.desk-log') ?? body.current;
      el?.scrollBy({ top: (a === 'down' ? 1 : -1) * el.clientHeight * 0.45, behavior: 'smooth' });
    }
    if (a === 'confirm' && section === 'desk') body.current?.querySelector<HTMLElement>('textarea')?.focus();
    if (a === 'back') { sfx.back(); go('modes'); }
  });
  return (
    <div className="screen panel-screen about">
      <ScreenHead jp="このゲームについて" en="ABOUT" note={`TOUGE NOCTURNE ${versionLabel()}`} />
      <div className="about-panel">
        <div className="about-tabs focus-box" role="tablist">
          {SECTIONS.map((s, i) => (
            <button key={s.id} role="tab" aria-selected={s.id === section} data-tab={s.id} className={s.id === section ? 'on' : ''} onClick={() => { if (s.id !== section) sfx.tab(); open(s.id); }}>
              <i>{String(i + 1).padStart(2, '0')}</i>
              <b>{s.jp}</b>
              <small>{s.en}</small>
            </button>
          ))}
          <FocusFrame on="button.on" deps={[at]} kind="tab" />
        </div>
        <div className={`about-body is-${section}`} ref={body} key={section} role="tabpanel">
          {section === 'game' && <GameSection />}
          {section === 'maker' && <MakerSection toDesk={() => { sfx.confirm(); open('desk'); }} />}
          {section === 'tech' && <TechSection />}
          {section === 'credits' && <CreditsSection />}
          {section === 'desk' && <DeskSection />}
        </div>
      </div>
      <Hint items={[['lr', 'セクション'], ['ud', 'スクロール'], ...(section === 'desk' ? ([['ok', '入力する']] as ['ok', string][]) : [])]} />
    </div>
  );
}

const MODES: [string, string, string][] = [
  ['TIME ATTACK', 'タイムアタック', '一人で峠を駆け下り、自己ベストとメダル、ランキングの上位を狙う。'],
  ['RIVAL BATTLE', 'ライバルバトル', '峠ごとに棲む 3 人の走り屋と 1 対 1。先にゴールした方の勝ち。'],
  ['GHOST BATTLE', 'ゴーストバトル', 'ランキング上位者や自分のベストの走りを、半透明の車で追う。'],
  ['ONLINE BATTLE', 'オンライン対戦', 'ルームコードで集まって、最大 5 人で同時にダウンヒル。'],
];

function GameSection() {
  return (
    <div className="ab-game stagger">
      <div className="ab-hero">
        <span className="ab-kanji" aria-hidden>峠</span>
        <div>
          <h3>TOUGE<br />NOCTURNE</h3>
          <p className="ab-jp">朧 峠 夜 想 曲</p>
        </div>
      </div>
      <div className="ab-figures">
        <Figure en="COURSES" to={COURSE_ORDER.length} unit="コース" />
        <Figure en="MACHINES" to={VEHICLE_ORDER.length} unit="台" />
        <Figure en="RIVALS" to={COURSE_ORDER.length * 3} unit="人" />
        <Figure en="ONLINE" to={5} unit="人まで" />
      </div>
      <p className="ab-lead">
        夜の峠を全開で駆け下りる、ブラウザで動く 3D レースゲームです。インストールは要りません。キーボード、ゲームパッド、横向きに持ったスマートフォンで走れます。
        車とバイクのほかに、電車や、もっと妙なものにも乗れます。
      </p>
      <Heading jp="モード" en="MODES" />
      <ol className="ab-modes">
        {MODES.map(([en, jp, text]) => (
          <li key={en}>
            <small>{en}</small>
            <b>{jp}</b>
            <p>{text}</p>
          </li>
        ))}
      </ol>
      <Heading jp="コース" en="COURSES" />
      <ul className="ab-courses">
        {COURSE_ORDER.map((id) => (
          <li key={id} className="ab-course" style={{ '--art': `url(${COURSES[id].art})` } as CSSProperties}>
            <small>{COURSES[id].nameEn}</small>
            <b>{COURSES[id].name}</b>
            <span>{COURSES[id].tagline}</span>
          </li>
        ))}
      </ul>
      <p className="ab-fine">峠・人物は架空です。車名・車両デザインは各メーカーの商標・意匠です（私的利用の非公開作品）。</p>
    </div>
  );
}

/** a part of a section: its name with a hairline, as the settings' groups */
function Heading({ jp, en }: { jp: string; en: string }) {
  return (
    <h4 className="ab-h">
      <b>{jp}</b>
      <small>{en}</small>
    </h4>
  );
}

function Figure({ en, to, unit }: { en: string; to: number; unit: string }) {
  return (
    <div className="ab-cell">
      <small>{en}</small>
      <Count to={to} ms={520} delay={160} />
      <span>{unit}</span>
    </div>
  );
}

function MakerSection({ toDesk }: { toDesk: () => void }) {
  const about = useDesk((s) => s.about);
  const offline = useDesk((s) => s.offline);
  // (until the server has said who: nothing, rather than a name that changes under the reader's eyes)
  const known = about ?? (offline ? { creator: 'Touge Nocturne Project', note: '', links: [] } : null);
  return (
    <div className="ab-maker stagger">
      <div className="ab-who">
        <small>CREATED BY</small>
        <h3>{known ? known.creator : <i className="busy-glyph" aria-label="確認中" />}</h3>
        {known?.note && <p>{known.note}</p>}
        {known && known.links.length > 0 && (
          <div className="ab-links">
            {known.links.map((l) => (
              <a key={l.url} className="chip" href={l.url} target="_blank" rel="noopener noreferrer">
                {l.label}
                <span aria-hidden>↗</span>
              </a>
            ))}
          </div>
        )}
        <p className="ab-fine">© 2026 {known?.creator ?? ''}</p>
      </div>
      <div className="ab-contact">
        <small>CONTACT</small>
        <b>連絡は窓口へ</b>
        <p>不具合の報告、要望、感想は「AI窓口」で受け付けています。遊び方や設定の相談もできます。届いた報告は開発者が確認します。</p>
        <button className="cta small" onClick={toDesk}>AI窓口をひらく</button>
      </div>
    </div>
  );
}

const QUALITY_JP: Record<QualityLevel, string> = { low: '低', medium: '中', high: '高', ultra: '最高' };

/** [tag, name, text] */
const TECH: [string, string, ReactNode][] = [
  ['RENDER', '描画', 'three.js の WebGPURenderer と TSL（ノードマテリアル）で描いています。WebGPU が使えない環境や、動作中に問題が起きたときは、自動で WebGL 2 に切り替わります。'],
  ['PIPELINE', '画づくり', 'シーン → アンビエントオクルージョン → 霞の中の光 → ブルーム → トーンマッピング（AgX）と時間帯の色調 → SMAA。アップスケーリングは WebGPU では数フレームを重ねる方式、WebGL 2 では FSR 1 です。'],
  ['PHYSICS', '物理', `Rapier の剛体と衝突判定の上に、自前の車両シミュレーションを載せています。毎秒 ${PHYSICS_HZ} 回の固定ステップで計算し、描画はその間を補間します。タイムの計測も同じ刻みです。`],
  ['MODELS', '3D モデル', '車・バイク・電車・沿道の構造物・草木は、すべて Blender の Python スクリプトから作った自作モデルです。地形と道路はコースの設計から計算で作っています。'],
  ['SOUND', 'サウンド', 'エンジン、タイヤ、風、電車の走行音は WebAudio による合成で、録音は使っていません。電車のインバータ音は VVVF Simulator の計算を移植したものです。'],
  ['NETWORK', 'サーバー・通信', 'Laravel 13 の JSON API と、Laravel Reverb（WebSocket）。オンライン対戦では車両の状態を毎秒 30 回送り合い、相手の車を「いま居る位置」に描きます。'],
  ['AI', '言語モデルと音声', 'ライバルのセリフと駆け引き（進路をふさぐ・クラクション）、そしてこの窓口は、ゲームのサーバーを通して言語モデルに尋ねています。運転そのものは任せていません。ライバルの声は音声合成モデル Supertonic 3 を、ブラウザの WebGPU の上で動かしています。'],
  ['INTERFACE', '画面', 'React 19 と zustand。レース中の表示は、毎フレーム、ゲームの状態を直接読んで描いています。'],
];

function TechSection() {
  const renderer = useApp((s) => s.renderer);
  const quality = useSettings((s) => s.quality);
  const [gpu] = useState(gpuName);
  return (
    <div className="ab-tech stagger">
      <div className="ab-readout" aria-label="この端末での動作">
        <div className="ab-cell">
          <small>RENDERER</small>
          <b data-live="backend">{renderer ? (renderer.backend === 'webgpu' ? 'WebGPU' : 'WebGL 2') : '—'}</b>
        </div>
        <div className="ab-cell wide">
          <small>GPU</small>
          <b className="text" data-live="gpu">{gpu ?? '（ブラウザが名前を知らせていません）'}</b>
        </div>
        <div className="ab-cell">
          <small>QUALITY</small>
          <b>{QUALITY_JP[quality]}</b>
        </div>
        <div className="ab-cell">
          <small>BUILD</small>
          <b>{versionLabel()}</b>
        </div>
        <div className="ab-cell">
          <small>THREE.JS</small>
          <b>r{REVISION}</b>
        </div>
        <div className="ab-cell">
          <small>PHYSICS</small>
          <b>{PHYSICS_HZ}<span>Hz</span></b>
        </div>
      </div>
      <dl className="ab-rows two">
        {TECH.map(([tag, name, text]) => (
          <div key={tag}>
            <dt>
              <small>{tag}</small>
              {name}
            </dt>
            <dd>{text}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** an address outside the game: a new tab, and the page there learns nothing of this one */
function Out({ href, children }: { href: string; children: ReactNode }) {
  return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
}

function CreditsSection() {
  // the control patterns of the trains in the game, as the simulator's files name them
  const patterns = [...new Set(TRAIN_ORDER.flatMap((id) => [TRAIN_INFO[id].vvvf, ...TRAIN_INFO[id].liveries.map((l) => l.vvvf)].flatMap((v) => (v ? [v.source] : []))))];
  return (
    <div className="ab-credits stagger">
      <dl className="ab-rows">
        <div>
          <dt><small>VVVF</small>電車のインバータ音</dt>
          <dd>
            <Out href="https://github.com/VvvfGeeks/VVVF-Simulator">VVVF Simulator</Out>（VvvfGeeks）の計算（PWM・誘導電動機・車内音のインパルス応答）と、同梱のスイッチング角テーブル（CHM）を移植して使っています（非商用に限り無償の利用規約による）。
            制御パターン: {patterns.join('・')}（<Out href="https://github.com/VvvfGeeks/YAML-Files">YAML-Files</Out>: VvvfGeeks。実車の再現で、実物と同一ではありません）。
          </dd>
        </div>
        <div>
          <dt><small>VOICE</small>ライバルの声</dt>
          <dd>
            音声合成モデル Supertonic 3（Supertone Inc.）を、<Out href={`${MODEL_BASE}/LICENSE`}>OpenRAIL-M ライセンス</Out>の利用制限のもとで使っています。実行には onnxruntime-web（Microsoft、MIT）。
          </dd>
        </div>
        <div>
          <dt><small>FONTS</small>フォント</dt>
          <dd>Saira、Zen Kaku Gothic New、Shippori Mincho（いずれも SIL Open Font License 1.1、Fontsource 経由）。</dd>
        </div>
        <div>
          <dt><small>TEXTURES</small>写真テクスチャ</dt>
          <dd>路面・地面・岩肌などの写真テクスチャは <Out href="https://ambientcg.com">ambientCG</Out>（CC0 1.0）。標識、ナンバープレート、空などは計算で描いています。</dd>
        </div>
        <div>
          <dt><small>GENERATED</small>生成した素材</dt>
          <dd>ライバルの肖像、コースの絵、キーアートは ChatGPT、ロード画面の映像は Gemini、音楽は Suno（アウトバーンの曲は Gemini）で生成したものです。</dd>
        </div>
        <div>
          <dt><small>MODELS</small>3D モデル</dt>
          <dd>車両・沿道・草木のモデルはすべてこのプロジェクトの自作です。第三者のモデルは使っていません。</dd>
        </div>
        <div>
          <dt><small>LIBRARIES</small>ライブラリ</dt>
          <dd>three.js、React、zustand、meshoptimizer、pusher-js、Laravel、Laravel Reverb（MIT）、Rapier（Apache-2.0）。</dd>
        </div>
        <div>
          <dt><small>NAMES</small>名称について</dt>
          <dd>峠・人物は架空です。車名・車両デザインは各メーカーの商標・意匠です（私的利用の非公開作品）。</dd>
        </div>
      </dl>
    </div>
  );
}
