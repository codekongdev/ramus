import { fileURLToPath } from 'node:url';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Ports come from RAMUS_* variables in process.env or the repository-root .env,
// so each worktree can run its own web and API servers side by side.
const REPO_ROOT = fileURLToPath(new URL('../..', import.meta.url));
const HOST = '127.0.0.1';
const DEFAULT_WEB_PORT = 5173;
const DEFAULT_API_PORT = 8000;
const MAX_PORT = 65535;

function readPort(env: Record<string, string>, name: string, fallback: number): number {
  const raw = env[name];
  if (raw === undefined || raw.trim() === '') return fallback;
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > MAX_PORT) {
    throw new Error(`${name} must be an integer between 1 and ${MAX_PORT}, got "${raw}"`);
  }
  return port;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, REPO_ROOT, 'RAMUS_');
  const webPort = readPort(env, 'RAMUS_WEB_PORT', DEFAULT_WEB_PORT);
  const apiPort = readPort(env, 'RAMUS_API_PORT', DEFAULT_API_PORT);

  return {
    plugins: [react()],
    server: {
      host: HOST,
      port: webPort,
      strictPort: true,
      proxy: { '/api': { target: `http://${HOST}:${apiPort}`, changeOrigin: false } },
    },
    test: { environment: 'node', include: ['tests/**/*.test.{ts,tsx}'] },
  };
});
