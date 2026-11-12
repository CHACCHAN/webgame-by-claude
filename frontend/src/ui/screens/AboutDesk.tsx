import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { DESK_LIMITS, type DeskKind } from '../../api/client';
import { useDesk, type DeskLine } from '../../store/desk';
import { Notice } from '../kit';
import { sfx } from '../sfx';
import { deskFacts } from './aboutFacts';

/**
 * The desk (About → AI窓口): a chat with a language model behind the game's server that answers questions about
 * the game and takes bug reports and requests down, and a plain form that sends a report without the model.
 * Text is the rule, the model an extra: no model on the server, or none that answers, and the form remains.
 *
 * What the model answers is shown as plain text (React text nodes: never HTML). The conversation lives in the
 * page's memory (`store/desk.ts`).
 */

const KIND_JP: Record<DeskKind, string> = { bug: '不具合の報告', request: '要望', other: 'ご連絡' };
const KINDS: [DeskKind, string][] = [['bug', '不具合'], ['request', '要望'], ['other', 'その他']];

/** what a tap asks for the player: the first two begin a report, the others are questions */
const QUICK: [string, string][] = [
  ['バグを報告する', '不具合を報告したいです。'],
  ['要望を送る', '要望を送りたいです。'],
  ['操作を知りたい', '操作方法を教えてください。'],
  ['速く走るコツ', '速く走るコツを教えてください。'],
];

/** what is being written, kept while the player looks at another section (the page's memory, as the conversation) */
const drafts = { chat: '', form: '' };

/**
 * A field's keys stay in the field: the menus (arrows, W A S D, Enter, Backspace), the game (H is the horn) and
 * the fullscreen key (F) all listen on the window, which these events never reach.
 */
const keep = (e: KeyboardEvent) => e.stopPropagation();

/** Esc in a field leaves the field (the next Esc is the screen's way back) */
const leaveOnEsc = (e: KeyboardEvent<HTMLElement>) => {
  e.stopPropagation();
  if (e.key === 'Escape') e.currentTarget.blur();
};

export function DeskSection() {
  const { desk, offline, lines, busy } = useDesk();
  const [mode, setMode] = useState<'chat' | 'form' | null>(null);
  // what the form starts with (a question the model could not take)
  const [carry, setCarry] = useState('');
  if (!desk) {
    return offline ? (
      <div className="desk">
        <Notice title="サーバーに接続できません" action={<button className="mini" onClick={() => void useDesk.getState().load()}>もう一度</button>}>
          窓口はサーバーにつながっているときだけ使えます。通信状態を確認して、もう一度お試しください。
        </Notice>
      </div>
    ) : (
      <div className="desk">
        <p className="desk-wait"><i className="busy-glyph" aria-hidden />窓口を確認しています…</p>
      </div>
    );
  }
  if (!desk.enabled) {
    return (
      <div className="desk">
        <Notice kind="info" title="窓口は現在受け付けていません">しばらくしてからもう一度お試しください。</Notice>
      </div>
    );
  }
  const shown = desk.ai ? (mode ?? 'chat') : 'form';
  const toForm = (text = '') => {
    setCarry(text);
    setMode('form');
  };
  return (
    <div className="desk" data-mode={shown}>
      <div className="desk-head">
        <span className={`desk-status${desk.ai ? ' on' : ''}`}>
          <i aria-hidden />
          {desk.ai ? 'AI ONLINE' : 'FORM ONLY'}
          <b>{desk.ai ? 'AI が応答します' : 'いまはフォームのみ受け付けています'}</b>
        </span>
        {desk.ai && (
          <div className="desk-modes">
            <button className={`chip${shown === 'chat' ? ' on' : ''}`} onClick={() => { sfx.tab(); setMode('chat'); }}>AI に相談</button>
            <button className={`chip${shown === 'form' ? ' on' : ''}`} onClick={() => { sfx.tab(); toForm(); }}>フォームで送る</button>
          </div>
        )}
      </div>
      {shown === 'chat' ? <Chat lines={lines} busy={busy} toForm={toForm} /> : <ReportForm start={carry} ai={desk.ai} />}
    </div>
  );
}

function Chat({ lines, busy, toForm }: { lines: DeskLine[]; busy: boolean; toForm: (text?: string) => void }) {
  const [text, setDraft] = useState(drafts.chat);
  const setText = (t: string) => {
    drafts.chat = t;
    setDraft(t);
  };
  const log = useRef<HTMLDivElement>(null);
  const ask = (t: string) => void useDesk.getState().ask(t, deskFacts());
  const send = () => {
    if (!text.trim() || busy) return;
    sfx.confirm();
    ask(text);
    setText('');
  };
  // the newest line is in view
  useEffect(() => {
    const el = log.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines.length, busy]);
  // what did not arrive: asked again, or carried to the form
  const failed = [...lines].reverse().find((l) => l.kind === 'user' && l.failed) as Extract<DeskLine, { kind: 'user' }> | undefined;
  return (
    <>
      <div className="desk-log" ref={log} aria-live="polite">
        {lines.length === 0 && (
          <div className="desk-empty">
            <b>TOUGE NOCTURNE の総合窓口です。</b>
            <p>遊び方や設定、うまく動かないときの相談にお答えします。不具合の報告や要望もここで受け付けて、開発者に渡します。</p>
          </div>
        )}
        {lines.map((l, i) =>
          l.kind === 'user' ? (
            <div key={i} className={`desk-line user${l.failed ? ' failed' : ''}`}>
              <small>{l.failed ? 'YOU ・ 未送信' : 'YOU'}</small>
              <p>{l.text}</p>
            </div>
          ) : l.kind === 'assistant' ? (
            <div key={i} className="desk-line assistant">
              <small>DESK</small>
              <p>{l.text}</p>
            </div>
          ) : l.kind === 'filed' ? (
            <Receipt key={i} id={l.filed.id} kind={l.filed.kind} />
          ) : (
            <Notice
              key={i}
              className="desk-error"
              action={
                <>
                  {l.retry && failed && <button className="mini" onClick={() => ask(failed.text)}>もう一度送る</button>}
                  {l.form && <button className="mini" onClick={() => toForm(failed?.text ?? '')}>フォームで送る</button>}
                </>
              }
            >
              {l.text}
            </Notice>
          ),
        )}
        {busy && (
          <div className="desk-line assistant pending">
            <small>DESK</small>
            <p><i className="busy-glyph" aria-hidden />確認しています…</p>
          </div>
        )}
      </div>
      {lines.length === 0 && (
        <div className="desk-quick">
          {QUICK.map(([label, ask1]) => (
            <button key={label} className="chip" disabled={busy} onClick={() => { sfx.confirm(); ask(ask1); }}>{label}</button>
          ))}
        </div>
      )}
      <form
        className="desk-compose"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <textarea
          value={text}
          rows={2}
          maxLength={DESK_LIMITS.messageChars}
          placeholder="質問・不具合・要望をどうぞ（Enter で送信、Shift + Enter で改行）"
          aria-label="窓口へのメッセージ"
          enterKeyHint="send"
          onChange={(e) => setText(e.target.value)}
          onKeyUp={keep}
          onKeyDown={(e) => {
            leaveOnEsc(e);
            // (Enter that ends a conversion of kana to kanji is not a send)
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button className="cta small" type="submit" disabled={busy || !text.trim()}>送信</button>
      </form>
      <p className="desk-fine">
        会話の内容は、ゲームのサーバーを通じて外部の AI サービスに送られます。報告・要望は開発者が確認するために保存されます（ゲームのバージョンや描画方式などの環境情報を含みます）。本名や連絡先などの個人情報は書かないでください。
      </p>
    </>
  );
}

/** A report was taken down: the number the player is given. */
function Receipt({ id, kind }: { id: string; kind: DeskKind }) {
  return (
    <div className="desk-filed" role="status">
      <small>受付番号</small>
      <b>{id}</b>
      <span>{KIND_JP[kind]}を受け付けました。開発者が確認します。</span>
    </div>
  );
}

function ReportForm({ start, ai }: { start: string; ai: boolean }) {
  const form = useDesk((s) => s.form);
  const [kind, setKind] = useState<DeskKind>('bug');
  const [text, setDraft] = useState((start || drafts.form).slice(0, DESK_LIMITS.reportChars));
  const setText = (t: string) => {
    drafts.form = t;
    setDraft(t);
  };
  const send = async () => {
    if (!text.trim() || form.sending) return;
    sfx.confirm();
    if (await useDesk.getState().report(kind, text, deskFacts())) setText('');
  };
  return (
    <form
      className="desk-form"
      onSubmit={(e) => {
        e.preventDefault();
        void send();
      }}
    >
      {!ai && <p className="desk-form-note">AI 窓口はいま利用できません。報告・要望はこのフォームから送れます。</p>}
      <div className="desk-kinds" role="radiogroup" aria-label="種類">
        <span>種類</span>
        {KINDS.map(([k, label]) => (
          <button key={k} type="button" role="radio" aria-checked={k === kind} data-kind={k} className={`chip${k === kind ? ' on' : ''}`} onClick={() => { sfx.tab(); setKind(k); }}>
            {label}
          </button>
        ))}
      </div>
      <textarea
        value={text}
        maxLength={DESK_LIMITS.reportChars}
        placeholder={kind === 'bug' ? 'どこで（コース・車両・画面）、何をしたら、何が起きたか。どうなるはずだったか。' : kind === 'request' ? 'こうなったらうれしい、ということを書いてください。' : '開発者に伝えたいことを書いてください。'}
        aria-label="報告の内容"
        onChange={(e) => setText(e.target.value)}
        onKeyUp={keep}
        onKeyDown={leaveOnEsc}
      />
      <div className="desk-form-foot">
        <span className="desk-count">{text.length} / {DESK_LIMITS.reportChars}</span>
        <button className="cta small" type="submit" disabled={form.sending || text.trim().length < 4}>
          {form.sending ? '送信中…' : '送信する'}
        </button>
      </div>
      {form.filed && <Receipt id={form.filed.id} kind={form.filed.kind} />}
      {form.error && <Notice className="desk-error">{form.error}</Notice>}
      <p className="desk-fine">
        報告・要望は開発者が確認するために保存されます（ゲームのバージョンや描画方式、画面の大きさなどの環境情報を含みます）。返信は届きません。本名や連絡先などの個人情報は書かないでください。
      </p>
    </form>
  );
}
