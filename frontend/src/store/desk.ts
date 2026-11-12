import { create } from 'zustand';
import { ApiError, api, type AboutInfo, type DeskFacts, type DeskFiled, type DeskInfo, type DeskKind, type DeskMessage } from '../api/client';

/**
 * The About screen's data and the desk's conversation (About → AI窓口). All of it lives in the page's memory: a
 * reload is a new conversation, nothing is kept by the browser.
 *
 * Text is the rule, the model an extra (as with the rivals' voice): when the server has no model, or it does not
 * answer, the plain report form remains.
 */

/** A line of the conversation as the screen shows it. */
export type DeskLine =
  | { kind: 'user'; text: string; /** it did not reach the desk: shown, but not part of what is sent next */ failed?: boolean }
  | { kind: 'assistant'; text: string }
  /** the desk took a report down: the number the player is given */
  | { kind: 'filed'; filed: DeskFiled }
  /** no answer: what happened, whether asking again can help, and whether the form is the way on */
  | { kind: 'error'; text: string; retry: boolean; form: boolean };

interface DeskState {
  /** what the server says: null until it has answered */
  about: AboutInfo | null;
  desk: DeskInfo | null;
  /** the server could not be reached (the screen still shows what it knows by itself) */
  offline: boolean;
  lines: DeskLine[];
  busy: boolean;
  /** what the plain form came to: the last report's number, or what went wrong */
  form: { sending: boolean; filed: DeskFiled | null; error: string | null };
  /** every report filed in this sitting, by the model or by the form */
  receipts: DeskFiled[];
  load: () => Promise<void>;
  ask: (text: string, facts: DeskFacts) => Promise<void>;
  report: (kind: DeskKind, text: string, facts: DeskFacts) => Promise<boolean>;
  clear: () => void;
}

let loading: Promise<void> | null = null;

/** the conversation as the server gets it: what was said on both sides, without what never arrived */
export const deskMessages = (lines: DeskLine[]): DeskMessage[] =>
  lines.flatMap((l): DeskMessage[] => (l.kind === 'user' && !l.failed ? [{ role: 'user', content: l.text }] : l.kind === 'assistant' ? [{ role: 'assistant', content: l.text }] : []));

export const useDesk = create<DeskState>((set, get) => ({
  about: null,
  desk: null,
  offline: false,
  lines: [],
  busy: false,
  form: { sending: false, filed: null, error: null },
  receipts: [],

  load: () =>
    (loading ??= api.about().then(
      (r) => set({ about: r.about, desk: r.desk, offline: false }),
      () => {
        // (asked again at the next visit of the screen)
        loading = null;
        set({ offline: true });
      },
    )),

  async ask(text, facts) {
    text = text.trim();
    if (!text || get().busy) return;
    // (what failed before is asked anew by this: its error and its line go)
    const lines: DeskLine[] = [...get().lines.filter((l) => l.kind !== 'error' && !(l.kind === 'user' && l.failed)), { kind: 'user', text }];
    set({ lines, busy: true });
    try {
      const r = await api.desk.chat(deskMessages(lines), facts);
      const more: DeskLine[] = [{ kind: 'assistant', text: r.reply }];
      if (r.filed) more.push({ kind: 'filed', filed: r.filed });
      set((s) => ({ lines: [...s.lines, ...more], busy: false, receipts: r.filed ? [...s.receipts, r.filed] : s.receipts }));
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      const said = e instanceof ApiError && status !== 0 && !/^HTTP \d+$/.test(e.message) ? e.message : null;
      const error: DeskLine =
        status === 429 ? { kind: 'error', text: said ?? '質問が続いています。少し待ってからもう一度お試しください。', retry: false, form: true }
        : status === 422 ? { kind: 'error', text: said ?? 'このメッセージは送れませんでした。', retry: false, form: false }
        : status === 0 ? { kind: 'error', text: 'サーバーに接続できませんでした。通信状態を確認して、もう一度お試しください。', retry: true, form: false }
        : { kind: 'error', text: 'AI窓口はいま応答できません。報告・要望はフォームから送れます。', retry: true, form: true };
      set((s) => ({ lines: [...s.lines.map((l, i): DeskLine => (i === s.lines.length - 1 && l.kind === 'user' ? { ...l, failed: true } : l)), error], busy: false }));
    }
  },

  async report(kind, text, facts) {
    text = text.trim();
    if (!text || get().form.sending) return false;
    set({ form: { sending: true, filed: null, error: null } });
    try {
      const r = await api.desk.report(kind, text, facts);
      set((s) => ({ form: { sending: false, filed: r.filed, error: null }, receipts: [...s.receipts, r.filed] }));
      return true;
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      const said = e instanceof ApiError && status !== 0 && !/^HTTP \d+$/.test(e.message) ? e.message : null;
      set({ form: { sending: false, filed: null, error: status === 0 ? 'サーバーに接続できませんでした。通信状態を確認して、もう一度お試しください。' : (said ?? '送信できませんでした。時間をおいてもう一度お試しください。') } });
      return false;
    }
  },

  clear: () => set({ lines: [] }),
}));
