import { spawn, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:net';
import { randomBytes, randomUUID } from 'node:crypto';
import { test as base, expect, type Page } from '@playwright/test';

type TestServer = {
  url: string;
  legacyAccount: { email: string; sessionToken: string };
};

async function freePort(): Promise<number> {
  const server = createServer();
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('No local test port available');
  await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  return address.port;
}

async function stop(child: ChildProcess): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null) return;
  const exited = once(child, 'exit');
  child.kill('SIGTERM');
  const timeout = setTimeout(() => child.kill('SIGKILL'), 10_000);
  try { await exited; } finally { clearTimeout(timeout); }
}

async function waitUntilReady(url: string, child: ChildProcess): Promise<void> {
  await expect.poll(async () => {
    if (child.exitCode !== null || child.signalCode !== null) throw new Error('Local E2E server exited');
    try { return (await fetch(url)).ok; } catch { return false; }
  }, { timeout: 30_000, message: 'Local E2E server must become ready' }).toBe(true);
}

export const test = base.extend<{}, { testServer: TestServer }>({
  testServer: [async ({}, use) => {
    const apiPort = await freePort();
    const webPort = await freePort();
    const legacyAccount = { email: `legacy-${randomUUID()}@example.test`, sessionToken: randomBytes(32).toString('hex') };
    const env = { ...process.env, RAMUS_API_PORT: String(apiPort), RAMUS_WEB_PORT: String(webPort), RAMUS_COOKIE_SECURE: 'false', RAMUS_EMAIL_CODE_AUTH_ENABLED: 'false', RAMUS_E2E_LEGACY_EMAIL: legacyAccount.email, RAMUS_E2E_LEGACY_SESSION: legacyAccount.sessionToken };
    const api = spawn('uv', ['run', '--project', 'apps/api', 'python', 'tests/e2e/server.py'], { env, stdio: ['ignore', 'pipe', 'pipe'] });
    api.stdout?.resume();
    api.stderr?.resume();
    let web: ChildProcess | undefined;
    try {
      await waitUntilReady(`http://127.0.0.1:${apiPort}/api/health`, api);
      web = spawn('pnpm', ['--filter', '@ramus/web', 'dev'], { env, stdio: 'ignore' });
      const url = `http://127.0.0.1:${webPort}`;
      await waitUntilReady(url, web);
      await use({ url, legacyAccount });
    } finally {
      if (web) await stop(web);
      await stop(api);
    }
  }, { scope: 'worker', timeout: 60_000 }],
  baseURL: async ({ testServer }, use) => { await use(testServer.url); },
});

export { expect };

export const TEST_PASSWORD = 'Ramus-e2e-pass-2026';

export async function registerAccount(page: Page, email: string, password = TEST_PASSWORD, displayName = email.split('@')[0]): Promise<void> {
  await page.goto('/login');
  await page.getByRole('button', { name: '회원가입', exact: true }).click();
  await page.getByLabel('닉네임', { exact: true }).fill(displayName);
  await page.getByLabel('이메일', { exact: true }).fill(email);
  await page.getByLabel('비밀번호', { exact: true }).fill(password);
  await page.getByLabel('비밀번호 확인', { exact: true }).fill(password);
  await page.getByRole('button', { name: '가입하고 시작하기', exact: true }).click();
  await expect(page.locator('.app-shell')).toBeVisible();
}

export async function signInAccount(page: Page, email: string, password = TEST_PASSWORD): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('이메일', { exact: true }).fill(email);
  await page.getByLabel('비밀번호', { exact: true }).fill(password);
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page.locator('.app-shell')).toBeVisible();
}
