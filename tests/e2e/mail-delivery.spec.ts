import { randomUUID } from 'node:crypto';
import { test, expect, finishLogin } from './fixtures';

test('a mail service failure keeps the email and retries the same request without a resend countdown', async ({ page, testServer }) => {
  const email = `mail-recovery-${randomUUID().slice(0, 8)}@example.test`;
  const keys: string[] = [];
  // API integration tests exercise actual mail failures; this checks the UI's uncertain retry.
  await page.route('**/api/auth/email-code', async route => {
    keys.push(route.request().headers()['idempotency-key']);
    if (keys.length === 1) {
      await route.fulfill({
        status: 503, contentType: 'application/json',
        body: JSON.stringify({ error: {
          code: 'SERVICE_UNAVAILABLE', message: '요청을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.', details: null,
        } }),
      });
    } else {
      await route.continue();
    }
  });
  await page.goto('/login');
  await page.getByLabel('이메일', { exact: true }).fill(email);
  const send = page.getByRole('button', { name: '인증 코드 받기', exact: true });
  await send.click();
  await expect(page.getByRole('alert')).toContainText('요청을 처리하는 중에 문제가 생겼습니다.');
  await expect(page.getByLabel('이메일', { exact: true })).toHaveValue(email);
  await expect(page.getByLabel('인증 코드', { exact: true })).toHaveCount(0);
  await expect(send).toBeEnabled();
  await send.click();
  await expect(page.getByLabel('인증 코드', { exact: true })).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[1]).toBe(keys[0]);
  await finishLogin(page, await testServer.codeFor(email));
});
