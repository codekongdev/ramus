import { randomUUID } from 'node:crypto';
import { test, expect, TEST_PASSWORD } from './fixtures';

test('a failed registration preserves the form and reuses its idempotency key without email delivery', async ({ page }) => {
  const email = `signup-retry-${randomUUID().slice(0, 8)}@example.test`;
  const keys: string[] = [];
  await page.route('**/api/auth/register', async route => {
    keys.push(route.request().headers()['idempotency-key']);
    if (keys.length === 1) {
      await route.fulfill({ status: 503, json: { error: {
        code: 'SERVICE_UNAVAILABLE', message: '잠시 후 다시 시도해 주세요.', details: null,
      } } });
    } else {
      await route.continue();
    }
  });
  await page.goto('/login');
  await page.getByRole('button', { name: '회원가입', exact: true }).click();
  await page.getByLabel('닉네임', { exact: true }).fill('가입 재시도');
  await page.getByLabel('이메일', { exact: true }).fill(email);
  await page.getByLabel('비밀번호', { exact: true }).fill(TEST_PASSWORD);
  await page.getByLabel('비밀번호 확인', { exact: true }).fill(TEST_PASSWORD);
  const submit = page.getByRole('button', { name: '가입하고 시작하기', exact: true });
  await submit.click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByLabel('이메일', { exact: true })).toHaveValue(email);
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect(page.locator('.app-shell')).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[1]).toBe(keys[0]);
});
