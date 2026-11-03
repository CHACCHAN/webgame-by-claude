// The reference samples of src/game/__tests__/vvvf.test.ts from RefSim's float32 output (see README.md here):
//   node tools/vvvf-ref/fixture.cjs <out.json> <pattern> <train|line> <gear1|0> <gear2|0> <ref.f32> [<pattern> … again]
const fs = require('node:fs');
const STRIDE = 997;
const [out, ...rest] = process.argv.slice(2);
const scenario = fs
  .readFileSync(`${__dirname}/scenario-test.txt`, 'utf8')
  .split('\n')
  .map((l) => l.trim().split(/\s+/))
  .filter((p) => p.length >= 3 && !p[0].startsWith('#'))
  .map(([s, n, r]) => [+s, n, +r]);
const cases = [];
for (let i = 0; i < rest.length; i += 5) {
  const [pattern, mode, g1, g2, file] = rest.slice(i, i + 5);
  const b = fs.readFileSync(file);
  const x = new Float32Array(b.buffer, b.byteOffset, b.length / 4);
  let sumSq = 0, sumAbs = 0;
  const samples = [];
  for (let k = 0; k < x.length; k++) {
    sumSq += x[k] * x[k];
    sumAbs += Math.abs(x[k]);
    if (k % STRIDE === 0) samples.push(x[k]);
  }
  cases.push({ pattern, mode, gear: +g1 > 0 ? [+g1, +g2] : null, n: x.length, stride: STRIDE, sumSq, sumAbs, samples });
}
fs.writeFileSync(out, JSON.stringify({ fs: 96000, calc: 256, seed: 2463534242, scenario, cases }) + '\n');
