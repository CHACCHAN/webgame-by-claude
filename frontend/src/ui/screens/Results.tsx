import { useEffect, useRef, useState } from 'react';
import { useApp } from '../../store/app';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { gameHolder } from '../GameCanvas';
import { api, loadLocalBest, loadPlayer, saveCarBest, saveLocalBest, type SubmitResult } from '../../api/client';
import { MEDAL_LABEL, medalFor } from '../../game/race/medals';
import { encodeGhost, type EncodedGhost } from '../../game/race/Ghost';
import type { RaceResult } from '../../game/Game';
import { CAR_SPECS } from '../../game/vehicle/carSpecs';
import { COURSES } from '../../game/track/courses';
import { formatTime } from '../format';
import { startRaceFromState } from './Menus';
import { sfx } from '../sfx';

type SubmitState = { kind: 'idle' } | { kind: 'need-name' } | { kind: 'sending' } | { kind: 'done'; res: SubmitResult } | { kind: 'error'; msg: string };

/** Per-result state survives the screen being re-mounted (e.g. after watching the replay). */
const memo = new WeakMap<RaceResult, { submit: SubmitState; localPB: { isNew: boolean; prev: number | null }; encoded: Promise<EncodedGhost> }>();
const medalNew = new WeakMap<RaceResult, boolean>();

export function ResultsScreen() {
  const { result, go, set, ghostChoice } = useApp();
  const [submit, setSubmit] = useState<SubmitState>({ kind: 'idle' });
  const [name, setName] = useState(() => loadPlayer()?.name ?? '');
  const [localPB, setLocalPB] = useState<{ isNew: boolean; prev: number | null }>({ isNew: false, prev: null });
  const [sel, setSel] = useState(0);
  const encoded = useRef<Promise<EncodedGhost> | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 900);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!result) return;
    const cached = memo.get(result);
    if (cached) {
      encoded.current = cached.encoded;
      setSubmit(cached.submit);
      setLocalPB(cached.localPB);
      return;
    }
    encoded.current = encodeGhost(result.ghost);
    const prevCarBest = saveCarBest(result.trackId, result.carId, result.timeMs);
    const before = prevCarBest === null ? null : medalFor(result.trackId, result.carId, prevCarBest);
    const now = medalFor(result.trackId, result.carId, result.timeMs);
    const rank = { gold: 3, silver: 2, bronze: 1 } as const;
    medalNew.set(result, !!now && (before === null || rank[now] > rank[before]));
    const prev = loadLocalBest(result.trackId);
    const isNew = !prev || result.timeMs < prev.timeMs;
    setLocalPB({ isNew, prev: prev?.timeMs ?? null });
    memo.set(result, { submit: { kind: 'idle' }, localPB: { isNew, prev: prev?.timeMs ?? null }, encoded: encoded.current });
    if (isNew) {
      void encoded.current.then((ghost) =>
        saveLocalBest(result.trackId, { carId: result.carId, timeMs: result.timeMs, splits: result.splitsMs, ghost, date: new Date().toISOString() }),
      );
    }
    if (loadPlayer()) void send(loadPlayer()!.name);
    else setSubmit({ kind: 'need-name' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  async function send(playerName: string) {
    if (!result) return;
    setSubmit({ kind: 'sending' });
    try {
      const player = await api.ensurePlayer(playerName.trim() || '名無しの走り屋');
      const ghost = await encoded.current!;
      const res = await api.submitRun(player, {
        track_id: result.trackId,
        car_id: result.carId,
        mode: result.mode,
        time_ms: result.timeMs,
        sector_ms: result.splitsMs,
        rival_level: result.rivalLevel,
        rival_won: result.rivalWon,
        ghost,
      });
      setSubmit({ kind: 'done', res });
      if (res.is_personal_best) gameHolder.game?.audio?.chime([1046, 1318, 1568, 2093], 0.09);
    } catch (e) {
      setSubmit({ kind: 'error', msg: (e as Error).message });
    }
  }

  useEffect(() => {
    const m = result && memo.get(result);
    if (m) m.submit = submit;
  }, [submit, result]);

  const actions = [
    { label: 'リトライ', action: () => void startRaceFromState() },
    { label: 'リプレイ', action: () => { if (result) { gameHolder.game?.startReplay(result); go('replay'); } } },
    { label: 'ランキング', action: () => { gameHolder.game?.startAttract(); set({ mode: 'time_attack' }); go('leaderboard'); } },
    { label: '車両選択', action: () => go('garage') },
    { label: 'メニュー', action: () => { gameHolder.game?.startAttract(); go('modes'); } },
  ];
  useMenuInput((a) => {
    if (a === 'left') { setSel((s) => (s + actions.length - 1) % actions.length); sfx.move(); }
    if (a === 'right') { setSel((s) => (s + 1) % actions.length); sfx.move(); }
    if (a === 'confirm') { sfx.confirm(); actions[sel].action(); }
  }, submit.kind !== 'need-name');

  if (!result) return null;
  const won = result.rivalLevel ? result.rivalWon === false : null;
  const sectors = result.splitsMs.map((s, i) => s - (i ? result.splitsMs[i - 1] : 0));
  const ghostDelta = result.mode === 'ghost' && ghostChoice ? result.timeMs - ghostChoice.timeMs : null;

  return (
    <div className={`screen results ${visible ? 'in' : ''}`}>
      <div className="results-card">
        <div className="results-head">
          {result.rivalLevel ? (
            <div className={`verdict ${won ? 'win' : 'lose'}`}>{won ? 'YOU WIN' : 'YOU LOSE'}</div>
          ) : (
            <div className="verdict finish">FINISH</div>
          )}
          <div className="results-sub">
            {COURSES[result.trackId].name} ・ {CAR_SPECS[result.carId].name}
            {result.rivalLevel && ` ・ VS ${COURSES[result.trackId].rivals[result.rivalLevel].name}`}
          </div>
        </div>
        <div className="results-time">{formatTime(result.timeMs)}</div>
        {medalFor(result.trackId, result.carId, result.timeMs) && (
          <div className={`medal medal-${medalFor(result.trackId, result.carId, result.timeMs)}`}>
            ● {MEDAL_LABEL[medalFor(result.trackId, result.carId, result.timeMs)!]}
            {medalNew.get(result) && <em> 獲得！</em>}
          </div>
        )}
        {localPB.isNew && <div className="badge-pb">NEW PERSONAL BEST{localPB.prev !== null && ` (${formatTime(result.timeMs - localPB.prev, { sign: true })})`}</div>}
        {ghostDelta !== null && (
          <div className={`ghost-delta ${ghostDelta <= 0 ? 'faster' : 'slower'}`}>
            👻 {ghostChoice!.label} {ghostDelta <= 0 ? 'に勝利' : 'に届かず'} {formatTime(ghostDelta, { sign: true })}
          </div>
        )}
        {result.rivalTimeMs !== undefined && (
          <div className="rival-time">ライバル: {formatTime(result.rivalTimeMs)}</div>
        )}
        <div className="results-grid">
          {sectors.map((s, i) => (
            <div key={i} className="cell">
              <small>SECTOR {i + 1}</small>
              <b>{formatTime(s).replace(/^0:/, '')}</b>
            </div>
          ))}
          <div className="cell">
            <small>TOP SPEED</small>
            <b>{result.topSpeedKmh} km/h</b>
          </div>
          <div className="cell">
            <small>DRIFT</small>
            <b>{result.driftScore.toLocaleString()} pt</b>
          </div>
        </div>
        <div className="online">
          {submit.kind === 'need-name' && (
            <form
              className="name-form"
              onSubmit={(e) => {
                e.preventDefault();
                void send(name);
              }}
            >
              <label>ランキング登録名（16文字まで）</label>
              <div>
                <input autoFocus maxLength={16} value={name} placeholder="名無しの走り屋" onChange={(e) => setName(e.target.value)} />
                <button className="mini" type="submit">登録</button>
                <button className="mini ghost" type="button" onClick={() => setSubmit({ kind: 'idle' })}>登録しない</button>
              </div>
            </form>
          )}
          {submit.kind === 'sending' && <div className="online-msg">記録を送信中…</div>}
          {submit.kind === 'done' && (
            <div className="online-msg ok">
              ONLINE RANK <b>#{submit.res.rank}</b> / {submit.res.total_players}
              {submit.res.is_personal_best ? <em>オンライン自己ベスト更新！</em> : <em>自己ベスト {formatTime(submit.res.previous_best_ms)}</em>}
            </div>
          )}
          {submit.kind === 'error' && <div className="online-msg err">送信できませんでした：{submit.msg}（記録はこの端末に保存されています）</div>}
        </div>
        <div className="results-actions">
          {actions.map((a, i) => (
            <button key={a.label} className={`cta small ${i === sel ? 'focus' : ''}`} {...hoverSelect(() => setSel(i))} onClick={() => { sfx.confirm(); a.action(); }}>
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ReplayOverlay() {
  const go = useApp((s) => s.go);
  const timeRef = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    let raf = 0;
    const loop = () => {
      if (timeRef.current) timeRef.current.textContent = formatTime((gameHolder.game?.replayTime ?? 0) * 1000);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);
  useMenuInput((a) => {
    if (a === 'back' || a === 'confirm') { sfx.back(); go('results'); }
  });
  return (
    <div className="screen replay" onClick={() => go('results')}>
      <div className="replay-tag"><i /> REPLAY <span ref={timeRef} /></div>
      <div className="letterbox top" />
      <div className="letterbox bottom" />
      <div className="replay-hint">Esc / Enter / クリック：結果に戻る</div>
    </div>
  );
}
