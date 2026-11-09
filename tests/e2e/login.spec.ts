// P0-B4 / ON-AC-01: two different accounts log in at the same time and land in the same shared sample.
import { expect, test } from './support/fixtures';

test('two accounts log in separately and share the same sample project', async ({ loginAs }) => {
  const [mason, hayden] = await Promise.all([loginAs('mason'), loginAs('hayden')]);

  expect(mason.me.account.id).not.toBe(hayden.me.account.id);
  expect(mason.me.default_project_id).toBe(hayden.me.default_project_id);

  // Each context keeps its own session cookie.
  for (const account of [mason, hayden]) {
    const me = await account.context.request.get('/api/me');
    expect(me.status()).toBe(200);
    expect((await me.json()).account.email).toBe(account.email);
  }

  // Both browsers open the app shell.
  await Promise.all(
    [mason, hayden].map(async ({ page }) => {
      await page.goto('/');
      await expect(page.locator('.app-shell')).toBeVisible();
    }),
  );
});

test('a context without a session is rejected by the API', async ({ browser }) => {
  const context = await browser.newContext();
  try {
    const me = await context.request.get('/api/me');
    expect(me.status()).toBe(401);
    expect((await me.json()).error.code).toBe('UNAUTHORIZED');
  } finally {
    await context.close();
  }
});
