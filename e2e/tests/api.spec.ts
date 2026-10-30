import { expect, test } from '@playwright/test';

test('API health and validation', async ({ request }) => {
  const health = await request.get('/api/health');
  expect(health.ok()).toBeTruthy();
  expect(await health.json()).toMatchObject({ status: 'ok', database: 'ok' });

  const reg = await request.post('/api/players', { data: { name: 'api-test' } });
  expect(reg.status()).toBe(201);
  const { token } = await reg.json();
  const bad = await request.post('/api/runs', {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
    data: { track_id: 'oboro-downhill', car_id: 'hayate', mode: 'time_attack', time_ms: 5000, sector_ms: [1, 2, 3, 5000] },
  });
  expect(bad.status()).toBe(422);
  const unauth = await request.post('/api/runs', { headers: { Accept: 'application/json' }, data: {} });
  expect(unauth.status()).toBe(401);
});
