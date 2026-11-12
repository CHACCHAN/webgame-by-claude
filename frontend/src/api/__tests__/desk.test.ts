import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DESK_LIMITS, api, deskWindow, type DeskMessage } from '../client';
import { deskMessages, useDesk } from '../../store/desk';

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const user = (content: string): DeskMessage => ({ role: 'user', content });
const desk = (content: string): DeskMessage => ({ role: 'assistant', content });

// The desk (About → AI窓口): what is sent keeps to the server's limits, and a desk without a model still takes reports.
describe('the conversation that is sent', () => {
  it('is the conversation while it is short', () => {
    const talk = [user('a'), desk('b'), user('c')];
    expect(deskWindow(talk)).toEqual(talk);
  });

  it('is the newest messages when there are too many, beginning with one of the player', () => {
    const talk = Array.from({ length: 21 }, (_, i) => (i % 2 ? desk(`d${i}`) : user(`u${i}`)));
    const sent = deskWindow(talk);
    // (the newest 16 begin with the desk's d5: it goes, the first word is the player's)
    expect(sent.length).toBe(15);
    expect(sent[0]).toEqual(user('u6'));
    expect(sent.at(-1)).toEqual(user('u20'));
  });

  it('stays under the total and cuts a message that is too long', () => {
    const long = 'あ'.repeat(1500);
    const talk = Array.from({ length: 12 }, (_, i) => (i % 2 ? desk(long) : user(long)));
    const sent = deskWindow(talk);
    expect(sent.every((m) => m.content.length === DESK_LIMITS.messageChars)).toBe(true);
    expect(sent.reduce((n, m) => n + m.content.length, 0)).toBeLessThanOrEqual(DESK_LIMITS.totalChars);
    expect(sent[0].role).toBe('user');
    // 6 × 1200 fit, a seventh would not
    expect(sent.length).toBe(6);
  });

  it('is nothing when the player has said nothing', () => {
    expect(deskWindow([desk('hello')])).toEqual([]);
  });
});

describe('the desk', () => {
  let calls: { url: string; body: any }[];
  let answer: (url: string, body: any) => Response;

  beforeEach(() => {
    calls = [];
    useDesk.setState({ lines: [], busy: false, receipts: [], form: { sending: false, filed: null, error: null } });
    vi.stubGlobal('fetch', async (url: string, init: RequestInit = {}) => {
      const body = init.body ? JSON.parse(init.body as string) : null;
      calls.push({ url, body });
      expect((init.headers as Record<string, string>)['X-Touge-Client']).toBe('1');
      return answer(url, body);
    });
  });

  it('reads who made the game and what the desk offers, and takes only web links', async () => {
    answer = () => json(200, { about: { creator: 'someone', note: 'n', links: [{ label: 'site', url: 'https://example.org/' }, { label: 'bad', url: 'javascript:alert(1)' }, null] }, desk: { enabled: true, ai: true } });
    expect(await api.about()).toEqual({ about: { creator: 'someone', note: 'n', links: [{ label: 'site', url: 'https://example.org/' }] }, desk: { enabled: true, ai: true } });
    // a server of before the desk: the project's name, no desk
    answer = () => json(200, { version: '2.0.0' });
    expect(await api.about()).toEqual({ about: { creator: 'Touge Nocturne Project', note: '', links: [] }, desk: { enabled: false, ai: false } });
    // a model without a desk is no desk
    answer = () => json(200, { desk: { enabled: false, ai: true } });
    expect((await api.about()).desk).toEqual({ enabled: false, ai: false });
  });

  it('asks with the conversation and the facts, and shows the answer and the number of a report', async () => {
    answer = (_url, body) => (body.messages.length === 1 ? json(200, { reply: 'どのコースですか？' }) : json(200, { reply: '受け付けました。', filed: { id: 'K7M2QD', kind: 'bug' } }));
    await useDesk.getState().ask('  橋で落ちます ', { backend: 'webgpu', w: 1920 });
    await useDesk.getState().ask('霧降湖です', { backend: 'webgpu', w: 1920 });
    expect(calls.map((c) => c.url)).toEqual(['/api/desk/chat', '/api/desk/chat']);
    expect(calls[1].body).toEqual({ messages: [user('橋で落ちます'), desk('どのコースですか？'), user('霧降湖です')], facts: { backend: 'webgpu', w: 1920 } });
    const s = useDesk.getState();
    expect(s.lines.map((l) => l.kind)).toEqual(['user', 'assistant', 'user', 'assistant', 'filed']);
    expect(s.receipts).toEqual([{ id: 'K7M2QD', kind: 'bug' }]);
    expect(s.busy).toBe(false);
  });

  it('keeps what did not arrive out of the next question and offers the form when nobody answers', async () => {
    answer = () => json(503, { message: 'AI窓口はいま応答できません。フォームから報告・要望を送れます。' });
    await useDesk.getState().ask('もしもし', {});
    let lines = useDesk.getState().lines;
    expect(lines).toEqual([{ kind: 'user', text: 'もしもし', failed: true }, { kind: 'error', text: 'AI窓口はいま応答できません。報告・要望はフォームから送れます。', retry: true, form: true }]);
    expect(deskMessages(lines)).toEqual([]);

    // asked again: the failed line and its error go, the question is sent once
    answer = () => json(200, { reply: 'はい。' });
    await useDesk.getState().ask('もしもし', {});
    lines = useDesk.getState().lines;
    expect(lines).toEqual([{ kind: 'user', text: 'もしもし' }, { kind: 'assistant', text: 'はい。' }]);
    expect(calls[1].body.messages).toEqual([user('もしもし')]);
  });

  it('says what the server says when it is asked too often', async () => {
    answer = () => json(429, { message: '質問が続いています。1分ほど待ってからもう一度お試しください。' });
    await useDesk.getState().ask('a', {});
    expect(useDesk.getState().lines[1]).toEqual({ kind: 'error', text: '質問が続いています。1分ほど待ってからもう一度お試しください。', retry: false, form: true });
  });

  it('sends a plain report without the model', async () => {
    answer = () => json(201, { filed: { id: 'ABC123', kind: 'request' } });
    expect(await useDesk.getState().report('request', ' コースを増やしてほしい ', { quality: 'high' })).toBe(true);
    expect(calls).toEqual([{ url: '/api/desk/report', body: { kind: 'request', text: 'コースを増やしてほしい', facts: { quality: 'high' } } }]);
    expect(useDesk.getState().form).toEqual({ sending: false, filed: { id: 'ABC123', kind: 'request' }, error: null });
    expect(useDesk.getState().receipts).toEqual([{ id: 'ABC123', kind: 'request' }]);

    answer = () => json(429, { message: '短い時間に多くの報告が送られました。しばらく時間をおいてからお試しください。' });
    expect(await useDesk.getState().report('bug', '止まります', {})).toBe(false);
    expect(useDesk.getState().form).toEqual({ sending: false, filed: null, error: '短い時間に多くの報告が送られました。しばらく時間をおいてからお試しください。' });
  });
});
