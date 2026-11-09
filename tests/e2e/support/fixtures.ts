// Multi-account fixtures: each account gets its own BrowserContext (own cookies) and is logged in
// through the real email-code API. Codes come from the development mailer's log (start-api.mjs).
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { test as base, expect, type APIRequestContext, type BrowserContext, type Page } from '@playwright/test';
import { apiLogPath, findLoginCode } from './env.mjs';

const API_LOG = apiLogPath(path.resolve(__dirname, '..', '..', '..'));

export type Me = {
  account: { id: string; email: string; display_name: string };
  default_project_id: string;
  ai_connection: { status: 'none' | 'connected' | 'invalid' };
};

export type Account = {
  readonly label: string;
  readonly email: string;
  readonly context: BrowserContext;
  readonly page: Page;
  readonly me: Me;
};

const CODE_WAIT_MS = 10_000;
const CODE_POLL_MS = 100;

export function idempotencyHeaders(prefix: string): Record<string, string> {
  return { 'Idempotency-Key': `e2e-${prefix}-${randomUUID()}` };
}

function readLog(): string {
  try {
    return readFileSync(API_LOG, 'utf8');
  } catch {
    return '';
  }
}

/** Waits for a code logged after `offset`, so a code from an earlier request is never reused. */
async function waitForCode(email: string, offset: number): Promise<string> {
  const deadline = Date.now() + CODE_WAIT_MS;
  for (;;) {
    const code = findLoginCode(readLog().slice(offset), email);
    if (code) return code;
    if (Date.now() > deadline) {
      throw new Error(
        `No login code for ${email} in ${API_LOG}. The API must be started by the E2E harness ` +
          '(pnpm e2e) so its log is captured; an already running dev server is not read.',
      );
    }
    await new Promise((resolve) => setTimeout(resolve, CODE_POLL_MS));
  }
}

/** Logs in `email` with the cookies of `request` (a context's request shares that context's cookies). */
export async function loginWithEmail(request: APIRequestContext, email: string): Promise<Me> {
  const offset = readLog().length;
  const requested = await request.post('/api/auth/email-code', {
    data: { email },
    headers: idempotencyHeaders('code'),
  });
  expect(requested.status(), await requested.text()).toBe(202);
  const verified = await request.post('/api/auth/verify', {
    data: { email, code: await waitForCode(email, offset) },
    headers: idempotencyHeaders('verify'),
  });
  expect(verified.status(), await verified.text()).toBe(200);
  return (await verified.json()) as Me;
}

type Fixtures = {
  /** `loginAs('mason')` opens a fresh logged-in context. Every context is closed after the test. */
  loginAs: (label: string) => Promise<Account>;
};

export const test = base.extend<Fixtures>({
  loginAs: async ({ browser }, use) => {
    const opened: BrowserContext[] = [];
    await use(async (label) => {
      const context = await browser.newContext();
      opened.push(context);
      const email = `${label}-${randomUUID().slice(0, 8)}@example.test`;
      const me = await loginWithEmail(context.request, email);
      const page = await context.newPage();
      return { label, email, context, page, me };
    });
    await Promise.all(opened.map((context) => context.close()));
  },
});

export { expect };
