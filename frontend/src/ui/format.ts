export function formatTime(ms: number | null | undefined, opts: { sign?: boolean } = {}) {
  if (ms === null || ms === undefined || !isFinite(ms)) return '--:--.---';
  const neg = ms < 0;
  const a = Math.abs(Math.round(ms));
  const m = Math.floor(a / 60000);
  const s = Math.floor((a % 60000) / 1000);
  const t = a % 1000;
  const body = `${m}:${String(s).padStart(2, '0')}.${String(t).padStart(3, '0')}`;
  if (opts.sign) return (neg ? '-' : '+') + (m === 0 ? `${s}.${String(t).padStart(3, '0')}` : body);
  return body;
}

export const AI_LEVEL_LABEL = { rookie: 'ROOKIE', ace: 'LOCAL ACE', legend: 'LEGEND' } as const;
