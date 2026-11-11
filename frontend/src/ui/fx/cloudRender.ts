// The grains drawn with WebGL 2: one call of points on a canvas over the interface (cloud.ts is the simulation).
// Used when the game itself runs on its WebGL 2 backend; on WebGPU the grains are drawn by cloudRenderGpu.ts
// (never make a WebGL context next to the game's WebGPU device: see there).
// Each grain is a soft dot, added to what is under it. Depth is drawn, not only computed: the perspective of the
// volume, grains off the screen's plane larger and fainter (out of focus), a little parallax with the pointer.
import { FOCAL, type Cloud } from './cloud';

const VERT = `#version 300 es
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec4 aCol;
layout(location = 2) in vec2 aLook;
uniform vec2 uView;
uniform float uRatio, uFocal, uTime;
uniform vec2 uLean;
out vec4 vCol;
void main() {
  float s = uFocal / (uFocal + aPos.z);
  vec2 c = uView * 0.5;
  vec2 p = c + (aPos.xy - c) * s + uLean * aPos.z;
  // out of focus away from the screen's plane: larger, and as much fainter as it is larger
  float blur = abs(aPos.z) / (uFocal * 0.4);
  float size = aLook.x * 8.0 * s * (1.0 + blur * 1.3);
  float twinkle = 0.8 + 0.2 * sin(uTime * (1.3 + aLook.y * 3.1) + aLook.y * 41.0);
  float a = aCol.a * twinkle / (1.0 + blur * 1.25);
  float px = size * uRatio;
  // (a grain finer than the smallest dot that draws evenly is a dimmer dot)
  if (px < 1.6) { a *= px / 1.6; px = 1.6; }
  gl_PointSize = px;
  gl_Position = s > 0.0 && s < 6.0 ? vec4(p.x / uView.x * 2.0 - 1.0, 1.0 - p.y / uView.y * 2.0, 0.0, 1.0) : vec4(2.0, 2.0, 2.0, 1.0);
  vCol = vec4(aCol.rgb * a, a * 0.35);
}`;

const FRAG = `#version 300 es
precision mediump float;
in vec4 vCol;
out vec4 o;
void main() {
  vec2 d = gl_PointCoord - 0.5;
  float r2 = dot(d, d) * 4.0;
  o = vCol * exp(-r2 * 2.8) * step(r2, 1.0);
}`;

export interface CloudRenderer {
  draw(c: Cloud, ratio: number, leanX: number, leanY: number): void;
  resize(w: number, h: number, ratio: number): void;
  dispose(): void;
}

/** null where WebGL 2 is not to be had: then there are no grains. */
export function createCloudRenderer(canvas: HTMLCanvasElement, n: number): CloudRenderer | null {
  const gl = canvas.getContext('webgl2', { alpha: true, premultipliedAlpha: true, antialias: false, depth: false, stencil: false });
  if (!gl) return null;
  const shader = (type: number, src: string) => {
    const s = gl.createShader(type)!;
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return s;
  };
  const prog = gl.createProgram()!;
  gl.attachShader(prog, shader(gl.VERTEX_SHADER, VERT));
  gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FRAG));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    console.warn('[grains]', gl.getProgramInfoLog(prog));
    return null;
  }
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  const posBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
  gl.bufferData(gl.ARRAY_BUFFER, n * 12, gl.DYNAMIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
  // colour, brightness, size, seed: eight bytes a grain
  const lookBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, lookBuf);
  gl.bufferData(gl.ARRAY_BUFFER, n * 8, gl.DYNAMIC_DRAW);
  gl.enableVertexAttribArray(1);
  gl.vertexAttribPointer(1, 4, gl.UNSIGNED_BYTE, true, 8, 0);
  gl.enableVertexAttribArray(2);
  gl.vertexAttribPointer(2, 2, gl.UNSIGNED_BYTE, true, 8, 4);
  const u = (name: string) => gl.getUniformLocation(prog, name);
  const uView = u('uView'), uRatio = u('uRatio'), uFocal = u('uFocal'), uTime = u('uTime'), uLean = u('uLean');
  gl.useProgram(prog);
  gl.disable(gl.DEPTH_TEST);
  gl.enable(gl.BLEND);
  // light added to light; the page under the canvas is dimmed only a little where the grains are dense
  gl.blendFuncSeparate(gl.ONE, gl.ONE, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  gl.clearColor(0, 0, 0, 0);
  let lost = false;
  canvas.addEventListener('webglcontextlost', (e) => {
    e.preventDefault();
    lost = true;
  });
  return {
    resize(w, h, ratio) {
      canvas.width = Math.max(1, Math.round(w * ratio));
      canvas.height = Math.max(1, Math.round(h * ratio));
      gl.viewport(0, 0, canvas.width, canvas.height);
    },
    draw(c, ratio, leanX, leanY) {
      if (lost) return;
      const m = c.active;
      gl.clear(gl.COLOR_BUFFER_BIT);
      if (!m) return;
      gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, c.pos, 0, m * 3);
      gl.bindBuffer(gl.ARRAY_BUFFER, lookBuf);
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, c.look, 0, m * 8);
      gl.uniform2f(uView, c.w, c.h);
      gl.uniform1f(uRatio, ratio);
      gl.uniform1f(uFocal, c.h * FOCAL);
      gl.uniform1f(uTime, c.time);
      gl.uniform2f(uLean, leanX, leanY);
      gl.drawArrays(gl.POINTS, 0, m);
    },
    dispose() {
      gl.deleteBuffer(posBuf);
      gl.deleteBuffer(lookBuf);
      gl.deleteVertexArray(vao);
      gl.deleteProgram(prog);
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    },
  };
}
