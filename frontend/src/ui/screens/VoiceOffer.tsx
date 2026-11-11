import { useState } from 'react';
import { MODEL_BASE } from '../../game/audio/speech/protocol';
import { chooseVoice, useSpeech } from '../../store/voice';
import { useSettings } from '../../store/settings';
import { useMenuInput, hoverSelect } from '../useMenuInput';
import { sfx } from '../sfx';

/**
 * The rivals' voice, offered once where the rivals are chosen: the speech model is ~400 MB, so it is fetched only
 * after a yes. Not shown where there can be no voice (no WebGPU, no model on the server).
 */
export function VoiceOffer({ onClose }: { onClose: () => void }) {
  const [i, setI] = useState(0);
  const pick = (k: number) => {
    sfx.confirm();
    chooseVoice(k === 0);
    onClose();
  };
  useMenuInput((a) => {
    if (a === 'left' || a === 'right' || a === 'up' || a === 'down') { setI((x) => 1 - x); sfx.move(); }
    if (a === 'confirm') pick(i);
    // (not now: asked again at the next rival battle)
    if (a === 'back') { sfx.back(); onClose(); }
  });
  return (
    <div className="voice-offer" role="dialog" aria-label="ライバルの声">
      <div className="voice-panel">
        <div className="vo-head">
          <b>ライバルの声</b>
          <small>RIVAL VOICE</small>
        </div>
        <p>
          ライバルのセリフを音声で喋らせることができます。音声合成モデル（約 400 MB）を一度だけ取得してこのブラウザに保存し、
          お使いの GPU で動かします。あとから設定で変更・削除できます。
        </p>
        <div className="vo-buttons focus-box">
          <button className={`cta small ${i === 0 ? 'focus' : ''}`} {...hoverSelect(() => setI(0))} onClick={() => pick(0)}>
            喋らせる<small>約 400 MB を取得</small>
          </button>
          <button className={`cta small ${i === 1 ? 'focus' : ''}`} {...hoverSelect(() => setI(1))} onClick={() => pick(1)}>
            文字だけ
          </button>
        </div>
        <div className="vo-credit">
          音声合成: Supertonic 3（Supertone Inc.）。モデルの利用は{' '}
          <a href={`${MODEL_BASE}/LICENSE`} target="_blank" rel="noreferrer">OpenRAIL-M ライセンス</a>
          {' '}の利用制限に従います。
        </div>
      </div>
    </div>
  );
}

/** Where the voice stands, in a line (while it is fetched and set up, when it is there, when it could not be). */
export function VoiceStatus() {
  const speech = useSpeech();
  const wanted = useSettings((s) => s.rivalVoice) === 'on';
  if (!wanted || speech.state === 'unknown' || speech.state === 'unsupported' || speech.state === 'absent' || speech.state === 'idle') return null;
  const pct = Math.round(speech.progress * 100);
  return (
    <div className={`voice-status ${speech.state}`} role="status">
      <b>ライバルの声</b>
      {speech.state === 'loading' && (
        <>
          <span>{speech.building || pct >= 100 ? '準備中' : `取得中 ${pct}%`}</span>
          <i className="vs-bar"><i style={{ transform: `scaleX(${speech.progress.toFixed(3)})` }} /></i>
        </>
      )}
      {speech.state === 'ready' && <span>READY</span>}
      {speech.state === 'failed' && <span>準備できませんでした（セリフは文字で出ます）</span>}
    </div>
  );
}
