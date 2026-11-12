import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { readFileSync } from 'node:fs';

// the one place the game's version is written: package.json (shown on the title, sent with a run)
const { version } = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as { version: string };

export default defineConfig({
  plugins: [react()],
  define: { __APP_VERSION__: JSON.stringify(version) },
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: process.env.API_PROXY ?? 'http://localhost:8080', changeOrigin: true },
      // Reverb WebSocket (online battles)
      '/app': { target: process.env.API_PROXY ?? 'http://localhost:8080', changeOrigin: true, ws: true },
      // the speech model (the rivals' voice): the stack's `tts` volume, or a folder served for a test (TTS_PROXY)
      '/tts': { target: process.env.TTS_PROXY ?? process.env.API_PROXY ?? 'http://localhost:8080', changeOrigin: true },
    },
  },
  // module workers (the speech model's: the ONNX runtime is an ES module that imports its own parts)
  worker: { format: 'es' },
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 2500,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/three/')) return 'three';
          if (id.includes('@dimforge/rapier3d')) return 'rapier';
          if (id.includes('postprocessing') || id.includes('@react-three')) return 'r3f';
          return undefined;
        },
      },
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    testTimeout: 120000,
  },
});
