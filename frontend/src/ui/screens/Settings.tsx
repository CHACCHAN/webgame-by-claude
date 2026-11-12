import { Fragment, useEffect, useRef, useState } from 'react';
import { serverBrain } from '../../api/rivalBrain';
import { useApp } from '../../store/app';
import { UPSCALE_SCALE, useSettings, type QualityLevel, type UpscaleMode } from '../../store/settings';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { gameHolder } from '../GameCanvas';
import { forgetFailures, planBackend, type BackendPref, type FallbackReason } from '../../game/render/backendChoice';
import { sfx } from '../sfx';
import { fullscreenSupported, toggleFullscreen, useFullscreen } from '../fullscreen';
import { TRAIN_INFO, TRAIN_ORDER } from '../../game/vehicle/trains';
import { FocusFrame, Hint, ScreenHead } from '../kit';
import { chooseVoice, forgetVoice, useSpeech } from '../../store/voice';
import { MODEL_BASE } from '../../game/audio/speech/protocol';

interface Row {
  label: string;
  value: string;
  /** what the setting does, in a line */
  note: string;
  /** a switch (on / off), a level (0…1, drawn as a meter) or a list stepped through */
  kind: 'switch' | 'level' | 'list';
  on?: boolean;
  level?: number;
  change: (dir: number) => void;
}

export function SettingsScreen() {
  const go = useApp((s) => s.go);
  const s = useSettings();
  const [sel, setSel] = useState(0);
  const [needsReload, setNeedsReload] = useState(false);
  const [backendReload, setBackendReload] = useState(false);
  const qualities: QualityLevel[] = ['low', 'medium', 'high', 'ultra'];
  const qLabel: Record<QualityLevel, string> = { low: '低', medium: '中', high: '高', ultra: '最高' };
  const upscaleModes: UpscaleMode[] = ['native', 'ultra', 'quality', 'balanced', 'performance'];
  const upscaleLabel: Record<UpscaleMode, string> = { native: 'ネイティブ', ultra: 'ウルトラ品質', quality: '品質', balanced: 'バランス', performance: 'パフォーマンス' };
  const cycle = <T,>(list: T[], cur: T, dir: number) => list[(list.indexOf(cur) + dir + list.length) % list.length];
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  const step = (v: number, dir: number, st = 0.1, lo = 0, hi = 1) => Math.round(Math.min(hi, Math.max(lo, v + dir * st)) * 100) / 100;
  const onOff = (v: boolean) => (v ? 'オン' : 'オフ');
  const game = gameHolder.game;
  // the rivals' voice: whether it can exist here, where its model stands, whether this browser holds a copy
  const speech = useSpeech();
  const [kept, setKept] = useState(false);
  useEffect(() => {
    void speech.probe();
  }, [speech]);
  useEffect(() => {
    let live = true;
    void speech.kept().then((k) => live && setKept(k));
    return () => { live = false; };
  }, [speech, speech.state]);
  const voiceOn = s.rivalVoice === 'on';
  const voiceCan = speech.state !== 'unsupported' && speech.state !== 'absent' && speech.state !== 'unknown';
  const voiceValue = !voiceCan ? (speech.state === 'unknown' ? '確認中' : '非対応')
    : !voiceOn ? 'オフ'
    : speech.state === 'loading' ? (speech.building || speech.progress >= 1 ? '準備中' : `取得中 ${Math.round(speech.progress * 100)}%`)
    : speech.state === 'failed' ? '失敗' : 'オン';
  const voiceNote = speech.state === 'unsupported' ? 'WebGPU で描画していないため（非対応、または描画方式が WebGL 2）、ライバルのセリフは文字だけで表示します'
    : speech.state === 'absent' ? 'このサーバーには音声モデルがありません。ライバルのセリフは文字だけで表示します'
    : voiceOn && speech.state === 'failed' ? '音声モデルを準備できませんでした（セリフは文字で出ます）。もう一度オンにすると再試行します'
    : 'ライバルのセリフを音声で喋らせます。音声合成モデル（約 400 MB）を一度だけ取得してこのブラウザに保存し、GPU（WebGPU）で動かします';
  // the renderer's backend: what runs (and why WebGL 2, when it does), and what the next load would start
  const running = useApp((a) => a.renderer);
  const backends: BackendPref[] = ['auto', 'webgpu', 'webgl2'];
  const backendLabel: Record<BackendPref, string> = { auto: '自動', webgpu: 'WebGPU', webgl2: 'WebGL 2' };
  const fallbackNote: Record<FallbackReason, string> = { query: 'URLの指定', setting: '設定', unsupported: 'このブラウザ・GPUはWebGPU非対応のため自動で切り替え', failed: 'WebGPUで問題が起きたため自動で切り替え' };
  const pref = s.backend ?? 'auto';
  const backendNote = !running ? 'WebGPUが使えない環境では自動でWebGL 2に切り替わります'
    : `現在: ${running.backend === 'webgpu' ? 'WebGPU' : `WebGL 2（${fallbackNote[running.reason ?? 'unsupported']}）`}`;
  const fullscreen = useFullscreen();
  const groups: { name: string; en: string; rows: Row[] }[] = [
    {
      name: '映像', en: 'GRAPHICS',
      rows: [
        { kind: 'list', label: 'グラフィック品質', value: qLabel[s.quality], note: '影・木の密度・ポストエフェクトの量。重いときはここから下げます', change: (d) => { s.set({ quality: cycle(qualities, s.quality, d) }); setNeedsReload(true); } },
        { kind: 'level', label: '解像度スケール', value: pct(s.resolutionScale), level: (s.resolutionScale - 0.5) / 0.5, note: '画面より小さく描いて引き伸ばします。下げるほど軽く、粗くなります', change: (d) => s.set({ resolutionScale: step(s.resolutionScale, d, 0.1, 0.5, 1) }) },
        { kind: 'switch', label: 'アップスケーリング', value: onOff(s.upscale), on: s.upscale, note: `低い解像度で描いて拡大し、負荷を下げます（${running?.backend === 'webgl2' ? 'FSR 1' : 'FSR 3'}）`, change: () => s.set({ upscale: !s.upscale }) },
        ...(s.upscale
          ? [
              { kind: 'list' as const, label: '描画解像度', value: `${upscaleLabel[s.upscaleMode]} ${pct(UPSCALE_SCALE[s.upscaleMode])}`, note: '低いほど軽く、細部は甘くなります', change: (d: number) => s.set({ upscaleMode: cycle(upscaleModes, s.upscaleMode, d) }) },
              { kind: 'level' as const, label: 'シャープネス', value: pct(s.sharpness), level: s.sharpness, note: '拡大したあとの輪郭の強さ', change: (d: number) => s.set({ sharpness: step(s.sharpness, d) }) },
            ]
          : []),
        { kind: 'list', label: '描画方式', value: backendLabel[pref], note: backendNote, change: (d) => {
          const v = cycle(backends, pref, d);
          s.set({ backend: v });
          // a choice by hand starts from a clean slate (what was remembered about WebGPU failing no longer counts)
          forgetFailures();
          const plan = planBackend(v, location.search);
          setBackendReload(!!running && plan.forceWebGL !== (running.backend === 'webgl2') && running.reason !== 'unsupported');
        } },
        { kind: 'switch', label: '全画面表示', value: !fullscreenSupported() ? '非対応' : onOff(fullscreen), on: fullscreen, note: 'F キーでも切り替えられます', change: () => fullscreenSupported() && toggleFullscreen() },
        { kind: 'switch', label: 'FPS表示', value: onOff(s.showFps), on: s.showFps, note: 'レース中、マップの下にフレームレートを出します', change: () => s.set({ showFps: !s.showFps }) },
        { kind: 'switch', label: 'UI アニメーション', value: onOff(s.uiMotion !== false), on: s.uiMotion !== false, note: '画面の切り替えや数値のカウントなどの動き。オフにすると単純なフェードだけになります', change: () => s.set({ uiMotion: s.uiMotion === false }) },
      ],
    },
    {
      name: '運転', en: 'DRIVING',
      rows: [
        { kind: 'list', label: '運転アシスト', value: ['オフ', '標準', '強'][s.assist], note: 'カウンターステア補助・スピン防止の強さ', change: (d) => { const v = ((s.assist + d + 3) % 3) as 0 | 1 | 2; s.set({ assist: v }); if (game) game.assist = v; } },
        { kind: 'switch', label: 'コーナー予告', value: onOff(s.cornerGuide), on: s.cornerGuide, note: '急カーブの手前で標識と警告音を出します', change: () => { s.set({ cornerGuide: !s.cornerGuide }); if (game) game.cornerGuide = !s.cornerGuide; } },
        { kind: 'switch', label: '操作ガイド（スタート時）', value: onOff(s.controlsGuide !== false), on: s.controlsGuide !== false, note: 'レース開始時に操作方法をしばらく表示します', change: () => s.set({ controlsGuide: s.controlsGuide === false }) },
        { kind: 'switch', label: 'ゴースト表示（タイムアタック）', value: onOff(s.showGhost), on: s.showGhost, note: '自己ベストの走りを半透明の車で一緒に走らせます', change: () => { s.set({ showGhost: !s.showGhost }); if (game) game.showGhost = !s.showGhost; } },
        { kind: 'switch', label: 'ライバルAI', value: onOff(s.rivalAi ?? true), on: s.rivalAi ?? true, note: 'ライバルのセリフと駆け引き（進路ブロック・クラクション）を言語モデルに任せます。オフや通信不可のときはゲーム内蔵のルールで動きます', change: () => { const v = !(s.rivalAi ?? true); s.set({ rivalAi: v }); if (game) game.rivalBrains = v ? [serverBrain] : []; } },
        { kind: 'switch', label: 'ライバルの声', value: voiceValue, on: voiceCan && voiceOn && speech.state !== 'failed', note: voiceNote, change: () => voiceCan && chooseVoice(!voiceOn || speech.state === 'failed') },
        ...(kept
          ? [{ kind: 'list' as const, label: '音声モデルのデータ', value: '保存済み 約 400 MB', note: '決定（または →）で、このブラウザに保存した音声モデルを削除します。ライバルの声はオフになります', change: (d: number) => { if (d > 0) void forgetVoice().then(() => setKept(false)); } }]
          : []),
      ],
    },
    {
      name: 'サウンド', en: 'SOUND',
      rows: [
        { kind: 'level', label: 'マスター音量', value: pct(s.masterVolume), level: s.masterVolume, note: 'すべての音の大きさ', change: (d) => s.set({ masterVolume: step(s.masterVolume, d) }) },
        { kind: 'level', label: '効果音', value: pct(s.sfxVolume), level: s.sfxVolume, note: 'エンジン・タイヤ・風・衝突の音', change: (d) => s.set({ sfxVolume: step(s.sfxVolume, d) }) },
        { kind: 'level', label: '音楽', value: pct(s.musicVolume), level: s.musicVolume, note: 'メニューとレースの音楽', change: (d) => s.set({ musicVolume: step(s.musicVolume, d) }) },
      ],
    },
  ];
  const rows = groups.flatMap((g) => g.rows);
  const at = Math.min(sel, rows.length - 1);
  useMenuInput((a) => {
    if (a === 'up') { setSel((x) => (Math.min(x, rows.length - 1) + rows.length - 1) % rows.length); sfx.move(); }
    if (a === 'down') { setSel((x) => (Math.min(x, rows.length - 1) + 1) % rows.length); sfx.move(); }
    if (a === 'left') { rows[at].change(-1); sfx.tab(); }
    if (a === 'right' || a === 'confirm') { rows[at].change(1); sfx.tab(); }
    if (a === 'back') { sfx.back(); go('modes'); }
  });
  // the list is longer than a short screen: the selected row stays in view
  const list = useRef<HTMLUListElement>(null);
  useEffect(() => {
    list.current?.querySelector('li.active')?.scrollIntoView({ block: 'nearest' });
  }, [at]);
  let n = -1;
  return (
    <div className="screen panel-screen">
      <ScreenHead jp="設定" en="SETTINGS" />
      <div className="panel settings">
        <div className="focus-box">
          <ul className="settings-list" ref={list}>
            {groups.map((g) => (
              <Fragment key={g.en}>
                <li className="sl-group" aria-hidden>
                  <b>{g.name}</b>
                  <small>{g.en}</small>
                </li>
                {g.rows.map((r) => {
                  const i = ++n;
                  return (
                    <li key={r.label} className={`sl-row ${r.kind}${i === at ? ' active' : ''}`} {...hoverSelect(() => setSel(i))}>
                      <div className="sl-label">
                        {r.label}
                        <small>{r.note}</small>
                      </div>
                      <div className="sl-value">
                        <button onClick={() => { setSel(i); r.change(-1); sfx.tab(); }} aria-label="decrease">‹</button>
                        {r.kind === 'level' && <i className="sl-meter"><i style={{ transform: `scaleX(${Math.max(0, Math.min(1, r.level ?? 0)).toFixed(2)})` }} /></i>}
                        {r.kind === 'switch' && <i className={`sl-switch${r.on ? ' on' : ''}`} />}
                        <span>{r.value}</span>
                        <button onClick={() => { setSel(i); r.change(1); sfx.tab(); }} aria-label="increase">›</button>
                      </div>
                    </li>
                  );
                })}
              </Fragment>
            ))}
          </ul>
          <FocusFrame on="li.active" deps={[at, rows.length]} kind="row" />
        </div>
        {backendReload && (
          <div className="notice info reload-note">
            <div>描画方式は再読み込み後に切り替わります。</div>
            <button className="mini" onClick={() => location.reload()}>今すぐ再読み込み</button>
          </div>
        )}
        {needsReload && (
          <div className="notice info reload-note">
            <div>グラフィック品質の一部（影・木の密度）は再読み込み後に反映されます。</div>
            <button className="mini" onClick={() => location.reload()}>今すぐ再読み込み</button>
          </div>
        )}
        <div className="gpu-note">目標は 1080p / 60fps です。カクつく場合は品質か解像度スケールを下げてください。</div>
        <div className="credits">
          ライバルの声: 音声合成モデル Supertonic 3（Supertone Inc.）を、<a href={`${MODEL_BASE}/LICENSE`} target="_blank" rel="noreferrer">OpenRAIL-M ライセンス</a>の利用制限のもとで使用。
        </div>
        <div className="credits">
          VVVF電車の音: VVVF Simulator（VvvfGeeks, https://github.com/VvvfGeeks/VVVF-Simulator）の計算（PWM・誘導電動機・車内音のインパルス応答）と同梱のスイッチング角テーブル（CHM）を移植して使用（非商用に限り無償の利用規約による）。制御パターン:{' '}
          {[...new Set(TRAIN_ORDER.flatMap((id) => [TRAIN_INFO[id].vvvf, ...TRAIN_INFO[id].liveries.map((l) => l.vvvf)].flatMap((v) => (v ? [v.source] : []))))].join('・')}
          （YAML-Files: VvvfGeeks, https://github.com/VvvfGeeks/YAML-Files、実車の再現で実物と同一ではありません）
        </div>
      </div>
      <Hint items={[['ud', '項目'], ['lr', '変更']]} />
    </div>
  );
}
