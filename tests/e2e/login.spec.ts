import { randomUUID } from 'node:crypto';
import { test, expect, requestLoginCode, finishLogin } from './fixtures';

test('three separate sessions share participants and restore the session on refresh', async ({ browser, testServer }) => {
  const contexts = await Promise.all(Array.from({ length: 3 }, () => browser.newContext({ baseURL: testServer.url })));
  try {
    const pages = await Promise.all(contexts.map((context) => context.newPage()));
    const emails = pages.map((_, index) => `browser-${index}-${randomUUID().slice(0, 8)}@example.test`);
    await Promise.all(pages.map(async (page, index) => {
      await requestLoginCode(page, emails[index]);
      await finishLogin(page, await testServer.codeFor(emails[index]));
    }));
    const profiles = await Promise.all(pages.map(async (page) => {
      const response = await page.request.get('/api/me');
      expect(response.ok()).toBe(true);
      return response.json();
    }));
    expect(new Set(profiles.map((profile) => profile.account.id)).size).toBe(3);
    expect(new Set(profiles.map((profile) => profile.default_project_id)).size).toBe(1);
    for (const page of pages) {
      await page.reload();
      await expect(page.locator('.app-shell')).toBeVisible();
      const participants = page.locator('[data-slot="participants"]');
      for (const email of emails) await expect(participants).toContainText(email.split('@')[0]);
      const cookies = await page.context().cookies();
      expect(cookies.find((cookie) => cookie.name === 'ramus_session')).toMatchObject({ httpOnly: true, sameSite: 'Lax' });
    }
    await pages[0].getByRole('button', { name: '로그아웃', exact: true }).click();
    await expect(pages[0].getByLabel('이메일', { exact: true })).toBeVisible();
    expect((await pages[0].request.get('/api/me')).status()).toBe(401);
    await pages[0].goto('/');
    await expect(pages[0]).toHaveURL(/\/login$/);
    await expect(pages[1].locator('.app-shell')).toBeVisible();
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
  }
});

test('wrong code keeps the form, email can be edited, and resend follows the cooldown', async ({ page, testServer }) => {
  const email = `resend-${randomUUID().slice(0, 8)}@example.test`;
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
  await requestLoginCode(page, `typo-${randomUUID().slice(0, 8)}@example.test`);
  await page.getByRole('button', { name: '이메일 수정', exact: true }).click();
  await page.getByLabel('이메일', { exact: true }).fill(email);
  await page.getByRole('button', { name: '인증 코드 받기', exact: true }).click();
  await expect(page.getByLabel('인증 코드', { exact: true })).toBeVisible();
  const firstCode = await testServer.codeFor(email);
  await page.getByLabel('인증 코드', { exact: true }).fill(String((Number(firstCode) + 1) % 1_000_000).padStart(6, '0'));
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('인증 코드가 올바르지 않습니다');
  const resend = page.getByRole('button', { name: /다시 받기$/ });
  await expect(resend).toBeDisabled();
  await expect(resend).toBeEnabled({ timeout: 65_000 });
  await resend.click();
  await finishLogin(page, await testServer.codeFor(email, 2));
  await expect(page.locator('[data-slot="participants"]')).toContainText(email.split('@')[0]);
});
