import { randomUUID } from 'node:crypto';
import { test, expect, registerAccount, signInAccount, TEST_PASSWORD } from './fixtures';

test('three separate sessions share participants and restore the session on refresh', async ({ browser, testServer }) => {
  const contexts = await Promise.all(Array.from({ length: 3 }, () => browser.newContext({ baseURL: testServer.url })));
  try {
    const pages = await Promise.all(contexts.map((context) => context.newPage()));
    const emails = pages.map((_, index) => `browser-${index}-${randomUUID().slice(0, 8)}@example.test`);
    await Promise.all(pages.map(async (page, index) => {
      await registerAccount(page, emails[index]);
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

test('signs in with a password after logout, preserving the email on invalid credentials', async ({ page }) => {
  const email = `password-${randomUUID().slice(0, 8)}@example.test`;
  let mailRequests = 0;
  page.on('request', request => { if (/\/api\/auth\/(email-code|verify)$/.test(new URL(request.url()).pathname)) mailRequests += 1; });
  await registerAccount(page, email, TEST_PASSWORD, '비밀번호 사용자');
  await page.getByRole('button', { name: '로그아웃', exact: true }).click();
  await expect(page.getByLabel('비밀번호', { exact: true })).toHaveValue('');
  await page.getByLabel('이메일', { exact: true }).fill(email);
  await page.getByLabel('비밀번호', { exact: true }).fill('Wrong-password-2026');
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByLabel('이메일', { exact: true })).toHaveValue(email);
  await signInAccount(page, email);
  await expect(page.locator('[data-slot="participants"]')).toContainText('비밀번호 사용자');
  expect(mailRequests).toBe(0);
  expect(await page.evaluate(() => [JSON.stringify(localStorage), JSON.stringify(sessionStorage)])).toEqual(['{}', '{}']);
});

test('password forms fit a narrow screen and support password managers and visibility controls', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/login');
  await expect(page.getByLabel('비밀번호', { exact: true })).toHaveAttribute('autocomplete', 'current-password');
  await page.getByRole('button', { name: '회원가입', exact: true }).click();
  const password = page.getByLabel('비밀번호', { exact: true });
  await expect(password).toHaveAttribute('autocomplete', 'new-password');
  await expect(page.getByLabel('비밀번호 확인', { exact: true })).toHaveAttribute('autocomplete', 'new-password');
  await password.fill(TEST_PASSWORD);
  await page.getByRole('button', { name: '비밀번호 보기', exact: true }).click();
  await expect(password).toHaveAttribute('type', 'text');
  await page.getByRole('button', { name: '비밀번호 숨기기', exact: true }).click();
  await expect(password).toHaveAttribute('type', 'password');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
  await page.screenshot({ path: 'artifacts/password-signup-mobile.png', fullPage: true });
  await page.getByRole('button', { name: '로그인으로 돌아가기', exact: true }).click();
  await expect(page.getByLabel('비밀번호', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('인증 코드', { exact: true })).toHaveCount(0);
});
