import { spawn, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:net';
import { test as base, expect, type Page } from '@playwright/test';

type TestServer = {
  url: string;
  codeFor(email: string, delivery?: number): Promise<string>;
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
    const env = { ...process.env, RAMUS_API_PORT: String(apiPort), RAMUS_WEB_PORT: String(webPort), RAMUS_COOKIE_SECURE: 'false' };
    const deliveries = new Map<string, string[]>();
    const api = spawn('uv', ['run', '--project', 'apps/api', 'python', 'tests/e2e/server.py'], { env, stdio: ['ignore', 'pipe', 'pipe'] });
    let pending = '';
    // Codes remain inside the fixture and never enter a test log or an HTTP test endpoint.
    api.stdout?.resume();
    api.stderr?.on('data', (data: Buffer) => {
      pending += data.toString();
      const lines = pending.split('\n');
      pending = lines.pop() ?? '';
      for (const line of lines) {
        const match = line.match(/\[DEV MAIL - not sent\] Ramus login code for (.+): (\d{6}) \(/);
        if (match) deliveries.set(match[1], [...(deliveries.get(match[1]) ?? []), match[2]]);
      }
    });
    let web: ChildProcess | undefined;
    try {
      await waitUntilReady(`http://127.0.0.1:${apiPort}/api/health`, api);
      web = spawn('pnpm', ['--filter', '@ramus/web', 'dev'], { env, stdio: 'ignore' });
      const url = `http://127.0.0.1:${webPort}`;
      await waitUntilReady(url, web);
      await use({
        url,
        async codeFor(email, delivery = 1) {
          const normalized = email.trim().toLowerCase();
          await expect.poll(() => deliveries.get(normalized)?.length ?? 0, { message: 'Test mail should arrive' }).toBeGreaterThanOrEqual(delivery);
          return deliveries.get(normalized)![delivery - 1];
        },
      });
    } finally {
      if (web) await stop(web);
      await stop(api);
    }
  }, { scope: 'worker', timeout: 60_000 }],
  baseURL: async ({ testServer }, use) => { await use(testServer.url); },
});

export { expect };

export async function requestLoginCode(page: Page, email: string): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('이메일', { exact: true }).fill(email);
  await page.getByRole('button', { name: '인증 코드 받기', exact: true }).click();
  await expect(page.getByLabel('인증 코드', { exact: true })).toBeVisible();
}

export async function finishLogin(page: Page, code: string): Promise<void> {
  await page.getByLabel('인증 코드', { exact: true }).fill(code);
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page.locator('.app-shell')).toBeVisible();
}
