import { existsSync } from 'node:fs';
import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

// Read the repository-root .env so each worktree's RAMUS_WEB_PORT is honored.
// process.loadEnvFile never overwrites variables that are already set.
const ENV_FILE = path.join(__dirname, '.env');
if (existsSync(ENV_FILE)) process.loadEnvFile(ENV_FILE);

const WEB_HOST = '127.0.0.1';
const DEFAULT_WEB_PORT = 5173;
const MAX_PORT = 65535;

function resolveBaseUrl(env: NodeJS.ProcessEnv): string {
  const url = env.RAMUS_WEB_URL?.trim();
  if (url) return url;
  const raw = env.RAMUS_WEB_PORT?.trim();
  if (!raw) return `http://${WEB_HOST}:${DEFAULT_WEB_PORT}`;
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > MAX_PORT) {
    throw new Error(`RAMUS_WEB_PORT must be an integer between 1 and ${MAX_PORT}, got "${raw}"`);
  }
  return `http://${WEB_HOST}:${port}`;
}

export default defineConfig({
  testDir: './tests/e2e',
  outputDir: './artifacts/test-results',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 150_000,
  expect: { timeout: 15_000 },
  forbidOnly: Boolean(process.env.CI),
  reporter: [['list'], ['html', { outputFolder: 'artifacts/playwright-report', open: 'never' }]],
  use: {
    baseURL: resolveBaseUrl(process.env),
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
