// The grains drawn with WebGPU, on the game's own device (cloud.ts is the simulation; cloudRender.ts the same
// picture on WebGL 2, for when the game runs on that backend).
//
// The grains are drawn with whatever the game is drawn with, never with the other API: a WebGL context made next to
// the game's WebGPU device lost that device (Chrome on the RX 5700 XT, 11-11: VK_ERROR_DEVICE_LOST the moment the
// context was made). On the game's device nothing new is made but a pipeline and three buffers; a validation error
// here would count as the game's (RenderHost watches the device), so keep this free of them (tools/gpu-errors.cjs).
import { FOCAL, type Cloud } from './cloud';
import type { CloudRenderer } from './cloudRender';

const SHADER = /* wgsl */ `
struct U { view: vec2f, lean: vec2f, ratio: f32, focal: f32, time: f32, pad: f32 };
@group(0) @binding(0) var<uniform> u: U;
struct VOut { @builtin(position) pos: vec4f, @location(0) col: vec4f, @location(1) uv: vec2f };

@vertex fn vs(@builtin(vertex_index) vi: u32, @location(0) p: vec3f, @location(1) col: vec4f, @location(2) look: vec4f) -> VOut {
  var corners = array<vec2f, 6>(vec2f(-1.0, -1.0), vec2f(1.0, -1.0), vec2f(-1.0, 1.0), vec2f(-1.0, 1.0), vec2f(1.0, -1.0), vec2f(1.0, 1.0));
  let s = u.focal / (u.focal + p.z);
  let c = u.view * 0.5;
  let q = c + (p.xy - c) * s + u.lean * p.z;
  // out of focus away from the screen's plane: larger, and as much fainter as it is larger
  let blur = abs(p.z) / (u.focal * 0.4);
  let size = look.x * 8.0 * s * (1.0 + blur * 1.3);
  let twinkle = 0.8 + 0.2 * sin(u.time * (1.3 + look.y * 3.1) + look.y * 41.0);
  var a = col.a * twinkle / (1.0 + blur * 1.25);
  var px = size * u.ratio;
  // (a grain finer than the smallest dot that draws evenly is a dimmer dot)
  if (px < 1.6) { a = a * px / 1.6; px = 1.6; }
  let corner = corners[vi];
  let at = q + corner * (px / u.ratio) * 0.5;
  var o: VOut;
  let seen = s > 0.0 && s < 6.0;
  o.pos = select(vec4f(2.0, 2.0, 2.0, 1.0), vec4f(at.x / u.view.x * 2.0 - 1.0, 1.0 - at.y / u.view.y * 2.0, 0.0, 1.0), seen);
  o.col = vec4f(col.rgb * a, a * 0.35);
  o.uv = corner;
  return o;
}

@fragment fn fs(i: VOut) -> @location(0) vec4f {
  let r2 = dot(i.uv, i.uv);
  return i.col * exp(-r2 * 2.8) * step(r2, 1.0);
}`;

/* eslint-disable @typescript-eslint/no-explicit-any */
/** `device`: the game's GPUDevice. null when the canvas gives no WebGPU context. */
export function createCloudRendererGpu(canvas: HTMLCanvasElement, n: number, device: any): CloudRenderer | null {
  const gpu = (navigator as any).gpu;
  const ctx = canvas.getContext('webgpu') as any;
  if (!gpu || !ctx || !device) return null;
  const format = gpu.getPreferredCanvasFormat();
  ctx.configure({ device, format, alphaMode: 'premultiplied' });
  const module = device.createShaderModule({ code: SHADER });
  const pipeline = device.createRenderPipeline({
    layout: 'auto',
    vertex: {
      module, entryPoint: 'vs',
      buffers: [
        { arrayStride: 12, stepMode: 'instance', attributes: [{ shaderLocation: 0, offset: 0, format: 'float32x3' }] },
        { arrayStride: 8, stepMode: 'instance', attributes: [{ shaderLocation: 1, offset: 0, format: 'unorm8x4' }, { shaderLocation: 2, offset: 4, format: 'unorm8x4' }] },
      ],
    },
    fragment: {
      module, entryPoint: 'fs',
      // light added to light; the page under the canvas is dimmed only a little where the grains are dense
      targets: [{ format, blend: { color: { srcFactor: 'one', dstFactor: 'one', operation: 'add' }, alpha: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha', operation: 'add' } } }],
    },
    primitive: { topology: 'triangle-list' },
  });
  const BUFFER = 0x8 | 0x20; // COPY_DST | VERTEX
  const posBuf = device.createBuffer({ size: n * 12, usage: BUFFER });
  const lookBuf = device.createBuffer({ size: n * 8, usage: BUFFER });
  const uniBuf = device.createBuffer({ size: 32, usage: 0x8 | 0x40 }); // COPY_DST | UNIFORM
  const group = device.createBindGroup({ layout: pipeline.getBindGroupLayout(0), entries: [{ binding: 0, resource: { buffer: uniBuf } }] });
  const uni = new Float32Array(8);
  let dead = false;
  return {
    resize(w, h, ratio) {
      canvas.width = Math.max(1, Math.round(w * ratio));
      canvas.height = Math.max(1, Math.round(h * ratio));
    },
    draw(c: Cloud, ratio, leanX, leanY) {
      if (dead) return;
      const m = c.active;
      try {
        if (m) {
          device.queue.writeBuffer(posBuf, 0, c.pos, 0, m * 3);
          device.queue.writeBuffer(lookBuf, 0, c.look, 0, m * 8);
        }
        uni.set([c.w, c.h, leanX, leanY, ratio, c.h * FOCAL, c.time, 0]);
        device.queue.writeBuffer(uniBuf, 0, uni);
        const encoder = device.createCommandEncoder();
        const pass = encoder.beginRenderPass({ colorAttachments: [{ view: ctx.getCurrentTexture().createView(), clearValue: { r: 0, g: 0, b: 0, a: 0 }, loadOp: 'clear', storeOp: 'store' }] });
        if (m) {
          pass.setPipeline(pipeline);
          pass.setBindGroup(0, group);
          pass.setVertexBuffer(0, posBuf);
          pass.setVertexBuffer(1, lookBuf);
          pass.draw(6, m);
        }
        pass.end();
        device.queue.submit([encoder.finish()]);
      } catch {
        // (the device went away: the game deals with that; the grains stop)
        dead = true;
      }
    },
    dispose() {
      dead = true;
      try {
        ctx.unconfigure();
        posBuf.destroy();
        lookBuf.destroy();
        uniBuf.destroy();
      } catch {
        // (already gone with the device)
      }
    },
  };
}
/* eslint-enable @typescript-eslint/no-explicit-any */
