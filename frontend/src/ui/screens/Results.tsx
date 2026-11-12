import { useEffect, useRef, useState } from 'react';
import { useApp } from '../../store/app';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { gameHolder } from '../GameCanvas';
import { api, currentMember, loadLocalBest, loadPlayer, saveCarBest, saveLocalBest, saveRivalResult, type SubmitResult } from '../../api/client';
import { MEDAL_LABEL, medalFor } from '../../game/race/medals';
import { encodeGhost, type EncodedGhost } from '../../game/race/Ghost';
import type { RaceResult } from '../../game/Game';
import { CAR_SPECS } from '../../game/vehicle/carSpecs';
import { COURSES } from '../../game/track/courses';
import { formatTime } from '../format';
import { Portrait, startRaceFromState } from './Menus';
import { useAccount } from '../../store/account';
import { sfx } from '../sfx';
import { Count, FocusFrame, Notice, Typed } from '../kit';
import { motionOn } from '../motion';

type SubmitState = { kind: 'idle' } | { kind: 'need-name' } | { kind: 'sending' } | { kind: 'done'; res: SubmitResult } | { kind: 'error'; msg: string };

/** Per-result state survives the screen being re-mounted (e.g. after watching the replay). */
const memo = new WeakMap<RaceResult, { submit: SubmitState; localPB: { isNew: boolean; prev: number | null }; encoded: Promise<EncodedGhost> }>();
const medalNew = new WeakMap<RaceResult, boolean>();

/** the character on the medal of grains */
const MEDAL_SIGN = { gold: '金', silver: '銀', bronze: '銅' } as const;

/** when the card comes in after the finish (ms): the finish banner has the screen until then */
const CARD_AT = 900;
/** how long the time counts up, and when the medal is stamped after the card came in (ms) */
const COUNT_MS = 1100, STAMP_AT = 1500;
/** the card's last part is in place (the latest `--at` in screens.css + the entrance) */
const BUILT_MS = 2600;

/**
 * The results build up step by step: the finish banner, then the card with the time counting to its figure, the
 * difference to the best / the ghost, the medal stamped on, the rival's word, the sectors and the online rank
 * (the steps are animation delays in screens.css; the buttons take input from the first frame).
 */
export function ResultsScreen() {
  const { result, go, set, ghostChoice, rivalLine } = useApp();
  const [submit, setSubmit] = useState<SubmitState>({ kind: 'idle' });
  const [name, setName] = useState(() => loadPlayer()?.name ?? '');
  const accountOn = useAccount((s) => s.enabled);
  const [localPB, setLocalPB] = useState<{ isNew: boolean; prev: number | null }>({ isNew: false, prev: null });
  const [sel, setSel] = useState(0);
  const encoded = useRef<Promise<EncodedGhost> | null>(null);
  const [visible, setVisible] = useState(false);
  // back from the replay: the card at once, nothing counted or stamped again
  const [again] = useState(() => !!result && memo.has(result));

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), again ? 0 : CARD_AT);
    return () => clearTimeout(t);
  }, [again]);
  // the card may scroll (a low window) only once it stands: its parts rise into place from below, and the last
  // of them reached under the card's edge on the way, which brought a scrollbar up for a moment (owner 11-12)
  const [settled, setSettled] = useState(again);
  useEffect(() => {
    if (again) return;
    const t = setTimeout(() => setSettled(true), CARD_AT + BUILT_MS);
    return () => clearTimeout(t);
  }, [again]);
  // the medal of grains gathers when the stamp lands
  const [stamped, setStamped] = useState(again);
  useEffect(() => {
    if (again) return;
    const t = setTimeout(() => setStamped(true), CARD_AT + STAMP_AT);
    return () => clearTimeout(t);
  }, [again]);

  useEffect(() => {
    if (!result) return;
    const cached = memo.get(result);
    if (cached) {
      encoded.current = cached.encoded;
      setSubmit(cached.submit);
      setLocalPB(cached.localPB);
      void gameHolder.game?.audio?.playMusic('bgm_results');
      return;
    }
    encoded.current = encodeGhost(result.ghost);
    const prevCarBest = saveCarBest(result.trackId, result.carId, result.timeMs);
    if (result.rivalLevel) saveRivalResult(result.trackId, result.rivalLevel, result.rivalWon === false);
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
    // a member's record goes to their account; a guest is asked for the name every time (the last one typed is filled in)
    if (currentMember()) void send(currentMember()!.name);
    else setSubmit({ kind: 'need-name' });
    // the finish jingle is playing (a longer one for beating the rival): a new medal or record gets its own
    // sting as it ends, then the results music
    const audio = gameHolder.game?.audio;
    const sting = medalNew.get(result) ? 'jingle_medal' : isNew && prev ? 'jingle_record' : null;
    const t = setTimeout(async () => {
      const len = audio && sting ? await audio.playJingle(sting) : 0;
      void audio?.playMusic('bgm_results', { delay: Math.max(0, len - 0.5) });
    }, result.rivalLevel && !result.rivalWon ? 6000 : 4300);
    // the medal's stamp lands as the time stops counting
    const stamp = now && motionOn() ? setTimeout(() => sfx.stamp(), CARD_AT + STAMP_AT) : undefined;
    return () => {
      clearTimeout(t);
      clearTimeout(stamp);
    };
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
    if (a === 'left' || a === 'up') { setSel((s) => (s + actions.length - 1) % actions.length); sfx.move(); }
    if (a === 'right' || a === 'down') { setSel((s) => (s + 1) % actions.length); sfx.move(); }
    if (a === 'confirm') { sfx.confirm(); actions[sel].action(); }
  }, submit.kind !== 'need-name');

  if (!result) return null;
  const won = result.rivalLevel ? result.rivalWon === false : null;
  const sectors = result.splitsMs.map((s, i) => s - (i ? result.splitsMs[i - 1] : 0));
  const ghostDelta = result.mode === 'ghost' && ghostChoice ? result.timeMs - ghostChoice.timeMs : null;
  const medal = medalFor(result.trackId, result.carId, result.timeMs);
  const verdict = won === null ? 'FINISH' : won ? 'YOU WIN' : 'YOU LOSE';
  const tone = won === null ? 'finish' : won ? 'win' : 'lose';
  const rival = result.rivalLevel ? COURSES[result.trackId].rivals[result.rivalLevel] : null;

  return (
    <div className={`screen results ${visible ? 'in' : ''}${again ? ' again' : ''}${settled ? ' settled' : ''}`} data-wipe="none">
      {!again && (
        <div className={`finish-banner ${tone}`} aria-hidden>
          <i />
          <b>{verdict}</b>
          <i />
        </div>
      )}
      {medal && stamped && <div className={`medal-grains medal-${medal}`} data-cloud={`medal:${medal}`} data-cloud-text={MEDAL_SIGN[medal]} aria-hidden />}
      <div className="results-card">
        <div className="results-head">
          <div className={`verdict ${tone}`}>{verdict}</div>
          <div className="results-sub">
            {COURSES[result.trackId].name} ・ {CAR_SPECS[result.carId].name}
            {rival && ` ・ VS ${rival.name}`}
          </div>
        </div>
        <div className="results-main">
          <Count as="div" className="results-time" to={result.timeMs} format={formatTime} ms={again ? 0 : COUNT_MS} delay={again ? 0 : CARD_AT + 250} tick />
          {medal && (
            <div className={`medal medal-${medal}`}>
              <b>{MEDAL_LABEL[medal]}</b>
              {medalNew.get(result) && <em>獲得！</em>}
            </div>
          )}
        </div>
        <div className="results-notes">
          {localPB.isNew && <div className="badge-pb">NEW PERSONAL BEST{localPB.prev !== null && ` (${formatTime(result.timeMs - localPB.prev, { sign: true })})`}</div>}
          {ghostDelta !== null && (
            <div className={`ghost-delta ${ghostDelta <= 0 ? 'faster' : 'slower'}`}>
              GHOST {ghostChoice!.label} {ghostDelta <= 0 ? 'に勝利' : 'に届かず'} <b>{formatTime(ghostDelta, { sign: true })}</b>
            </div>
          )}
          {result.rivalTimeMs !== undefined && (
            <div className="rival-time">ライバル <b>{formatTime(result.rivalTimeMs)}</b></div>
          )}
        </div>
        {rival && rivalLine && rivalLine.moment !== 'before' && (
          <div className="rival-line">
            <Portrait src={rival.portrait} className="vs-portrait" />
            <p>
              <small>{rival.name}</small>
              <Typed text={rivalLine.text} wrap={['「', '」']} />
            </p>
          </div>
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
              {accountOn && <p className="name-note">ゲストとして記録します。メンバーはメインメニューの「メンバーログイン」から。</p>}
              <div>
                <input autoFocus maxLength={16} value={name} placeholder="名無しの走り屋" onChange={(e) => setName(e.target.value)} />
                <button className="mini" type="submit">登録</button>
                <button className="mini ghost" type="button" onClick={() => setSubmit({ kind: 'idle' })}>登録しない</button>
              </div>
            </form>
          )}
          {submit.kind === 'sending' && <div className="online-msg sending">記録を送信中…</div>}
          {submit.kind === 'done' && (
            <div className="online-msg ok">
              ONLINE RANK <b>#{submit.res.rank}</b> / {submit.res.total_players}
              {submit.res.is_personal_best ? <em>オンライン自己ベスト更新！</em> : <em>自己ベスト {formatTime(submit.res.previous_best_ms)}</em>}
            </div>
          )}
          {submit.kind === 'error' && (
            <Notice className="online-msg err" title="記録を送信できませんでした" action={<button className="mini" onClick={() => void send(name)}>再送信</button>}>
              {submit.msg}。記録はこの端末に保存されています。
            </Notice>
          )}
        </div>
        <div className="results-actions focus-box">
          {actions.map((a, i) => (
            <button key={a.label} className={`cta small ${i === sel && submit.kind !== 'need-name' ? 'focus' : ''}`} {...hoverSelect(() => setSel(i))} onClick={() => { sfx.confirm(); a.action(); }}>
              {a.label}
            </button>
          ))}
          <FocusFrame on=".focus" deps={[sel, submit.kind]} pad={4} />
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
      const text = formatTime((gameHolder.game?.replayTime ?? 0) * 1000);
      if (timeRef.current && timeRef.current.textContent !== text) timeRef.current.textContent = text;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);
  useMenuInput((a) => {
    if (a === 'back' || a === 'confirm') { sfx.back(); go('results'); }
  });
  return (
    <div className="screen replay" data-wipe="none" onClick={() => go('results')}>
      <div className="letterbox top" />
      <div className="letterbox bottom" />
      <div className="replay-tag"><i /> REPLAY <span ref={timeRef} /></div>
      <div className="replay-hint">
        <kbd className="k-key">Esc</kbd><kbd className="k-key">Enter</kbd><kbd className="k-pad pad">B</kbd> クリックでも結果に戻る
      </div>
    </div>
  );
}
