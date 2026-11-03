import { useState } from 'react';
import { useApp } from '../../store/app';
import { useSettings, type QualityLevel } from '../../store/settings';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { gameHolder } from '../GameCanvas';
import { Hint } from './Menus';
import { sfx } from '../sfx';
import { PROP_CREDITS } from '../../game/render/props';
import { fullscreenSupported, toggleFullscreen, useFullscreen } from '../fullscreen';
import { TRAIN_INFO, TRAIN_ORDER } from '../../game/vehicle/trains';

interface Row {
  label: string;
  value: string;
  note?: string;
  change: (dir: number) => void;
}

export function SettingsScreen() {
  const go = useApp((s) => s.go);
  const s = useSettings();
  const [sel, setSel] = useState(0);
  const [needsReload, setNeedsReload] = useState(false);
  const qualities: QualityLevel[] = ['low', 'medium', 'high', 'ultra'];
  const qLabel: Record<QualityLevel, string> = { low: '低', medium: '中', high: '高', ultra: '最高' };
  const cycle = <T,>(list: T[], cur: T, dir: number) => list[(list.indexOf(cur) + dir + list.length) % list.length];
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  const step = (v: number, dir: number, st = 0.1, lo = 0, hi = 1) => Math.round(Math.min(hi, Math.max(lo, v + dir * st)) * 100) / 100;
  const game = gameHolder.game;
  const fullscreen = useFullscreen();
  const rows: Row[] = [
    { label: 'グラフィック品質', value: qLabel[s.quality], note: '影・木の密度・ポストエフェクト', change: (d) => { s.set({ quality: cycle(qualities, s.quality, d) }); setNeedsReload(true); } },
    { label: '解像度スケール', value: pct(s.resolutionScale), change: (d) => s.set({ resolutionScale: step(s.resolutionScale, d, 0.1, 0.5, 1) }) },
    { label: '運転アシスト', value: ['オフ', '標準', '強'][s.assist], note: 'カウンターステア補助・スピン防止', change: (d) => { const v = ((s.assist + d + 3) % 3) as 0 | 1 | 2; s.set({ assist: v }); if (game) game.assist = v; } },
    { label: 'ゴースト表示（タイムアタック）', value: s.showGhost ? 'オン' : 'オフ', change: () => { s.set({ showGhost: !s.showGhost }); if (game) game.showGhost = !s.showGhost; } },
    { label: '操作ガイド（スタート時）', value: s.controlsGuide !== false ? 'オン' : 'オフ', note: 'レース開始時に操作方法をしばらく表示します', change: () => s.set({ controlsGuide: s.controlsGuide === false }) },
    { label: 'コーナー予告', value: s.cornerGuide ? 'オン' : 'オフ', note: '急カーブの手前で標識と警告音を出します', change: () => { s.set({ cornerGuide: !s.cornerGuide }); if (game) game.cornerGuide = !s.cornerGuide; } },
    { label: 'マスター音量', value: pct(s.masterVolume), change: (d) => s.set({ masterVolume: step(s.masterVolume, d) }) },
    { label: '効果音', value: pct(s.sfxVolume), change: (d) => s.set({ sfxVolume: step(s.sfxVolume, d) }) },
    { label: '音楽', value: pct(s.musicVolume), change: (d) => s.set({ musicVolume: step(s.musicVolume, d) }) },
    { label: 'FPS表示', value: s.showFps ? 'オン' : 'オフ', change: () => s.set({ showFps: !s.showFps }) },
    { label: '全画面表示', value: !fullscreenSupported() ? '非対応' : fullscreen ? 'オン' : 'オフ', note: 'F キーでも切り替えられます', change: () => fullscreenSupported() && toggleFullscreen() },
  ];
  useMenuInput((a) => {
    if (a === 'up') { setSel((x) => (x + rows.length - 1) % rows.length); sfx.move(); }
    if (a === 'down') { setSel((x) => (x + 1) % rows.length); sfx.move(); }
    if (a === 'left') { rows[sel].change(-1); sfx.move(); }
    if (a === 'right' || a === 'confirm') { rows[sel].change(1); sfx.move(); }
    if (a === 'back') { sfx.back(); go('modes'); }
  });
  return (
    <div className="screen panel-screen">
      <div className="panel">
        <div className="panel-title">SETTINGS <small>設定</small></div>
        <ul className="settings-list">
          {rows.map((r, i) => (
            <li key={r.label} className={i === sel ? 'active' : ''} {...hoverSelect(() => setSel(i))}>
              <div className="sl-label">
                {r.label}
                {r.note && <small>{r.note}</small>}
              </div>
              <div className="sl-value">
                <button onClick={() => r.change(-1)} aria-label="decrease">‹</button>
                <span>{r.value}</span>
                <button onClick={() => r.change(1)} aria-label="increase">›</button>
              </div>
            </li>
          ))}
        </ul>
        {needsReload && (
          <div className="reload-note">
            グラフィック品質の一部（影・木の密度）は再読み込み後に反映されます。
            <button className="mini" onClick={() => location.reload()}>今すぐ再読み込み</button>
          </div>
        )}
        <div className="gpu-note">※ 目標は 1080p / 60fps です。カクつく場合は品質か解像度スケールを下げてください。</div>
        <div className="credits">
          背景の3Dモデル（Sketchfab, CC BY 4.0）: {PROP_CREDITS.map((c) => `“${c.title}” by ${c.author}`).join(' / ')}
          <br />
          電車の音（Wikimedia Commons の録音を切り出し・加工）:{' '}
          {[...new Set(TRAIN_ORDER.flatMap((id) => [TRAIN_INFO[id].motorSound?.credit, TRAIN_INFO[id].runningSound?.credit]))]
            .flatMap((c) => (c ? [`“${c.title}” by ${c.author} (${c.license})`] : []))
            .filter((c, i, all) => all.indexOf(c) === i)
            .join(' / ')}
          <br />
          VVVFインバータ音の制御パターンの数値: VvvfGeeks / YAML-Files（https://github.com/VvvfGeeks/YAML-Files）を参照（E231系 三菱・JR西日本207系2000番台 東芝）
        </div>
      </div>
      <Hint items={[['↑↓', '項目'], ['←→', '変更'], ['Esc', '戻る']]} />
    </div>
  );
}
