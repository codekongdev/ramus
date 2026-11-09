import { existsSync } from 'node:fs';
import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

// Read the repository-root .env (DATABASE_URL etc.). process.loadEnvFile never overwrites set variables.
const ENV_FILE = path.join(__dirname, '.env');
if (existsSync(ENV_FILE)) process.loadEnvFile(ENV_FILE);

const HOST = '127.0.0.1';
// E2E servers use their own ports so a running dev server (5173/8000) is never reused or blocked.
const DEFAULT_E2E_WEB_PORT = 5273;
const DEFAULT_E2E_API_PORT = 8100;
const MAX_PORT = 65535;
const SERVER_START_TIMEOUT_MS = 120_000;

function readPort(name: string, fallback: number): number {
  const raw = process.env[name]?.trim();
  if (!raw) return fallback;
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > MAX_PORT) {
    throw new Error(`${name} must be an integer between 1 and ${MAX_PORT}, got "${raw}"`);
  }
  return port;
}

const webPort = readPort('RAMUS_E2E_WEB_PORT', DEFAULT_E2E_WEB_PORT);
const apiPort = readPort('RAMUS_E2E_API_PORT', DEFAULT_E2E_API_PORT);
// RAMUS_WEB_URL points the tests at an already deployed app; then no local servers are started.
const externalUrl = process.env.RAMUS_WEB_URL?.trim();
const serverEnv = { RAMUS_WEB_PORT: String(webPort), RAMUS_API_PORT: String(apiPort) };

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.spec.ts', // support/*.test.mjs are node:test unit tests run by `pnpm verify`
  outputDir: './artifacts/test-results',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 150_000,
  expect: { timeout: 15_000 },
  forbidOnly: Boolean(process.env.CI),
  reporter: [['list'], ['html', { outputFolder: 'artifacts/playwright-report', open: 'never' }]],
  use: {
    baseURL: externalUrl || `http://${HOST}:${webPort}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: externalUrl
    ? undefined
    : [
        {
          // Prepares the ramus_e2e database and captures the API log for login codes.
          command: 'node tests/e2e/support/start-api.mjs',
          url: `http://${HOST}:${apiPort}/api/health`,
          env: serverEnv,
          reuseExistingServer: false,
          timeout: SERVER_START_TIMEOUT_MS,
          stdout: 'ignore',
          stderr: 'pipe',
        },
        {
          command: 'node node_modules/vite/bin/vite.js',
          cwd: 'apps/web',
          url: `http://${HOST}:${webPort}`,
          env: serverEnv,
          reuseExistingServer: false,
          timeout: SERVER_START_TIMEOUT_MS,
        },
      ],
});
