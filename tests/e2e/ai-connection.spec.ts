import { expect, test } from './fixtures';

const projectId = '00000000-0000-4000-8000-000000000001';

test.beforeEach(async ({ page }) => {
  // Deterministic browser test: no real credential, mail, provider call or shared data writes.
  await page.route('**/api/me', (route) => route.fulfill({ json: {
    account: { id: '00000000-0000-4000-8000-000000000002', email: 'test@example.test', display_name: '테스트' },
    default_project_id: projectId, ai_connection: { status: 'none' },
  } }));
  await page.route(`**/api/projects/${projectId}`, (route) => route.fulfill({ json: {
    id: projectId, name: '테스트 프로젝트', participants: [],
  } }));
  await page.route('**/api/projects', (route) => route.fulfill({ json: {
    items: [{ id: projectId, name: '테스트 프로젝트', is_shared_sample: true }],
  } }));
  await page.route(`**/api/projects/${projectId}/participants`, (route) => route.fulfill({ json: {
    items: [{ id: '00000000-0000-4000-8000-000000000002', email: 'test@example.test', display_name: '테스트' }],
  } }));
});

test('connects, corrects an invalid key, replaces it and disconnects from the workspace', async ({ page }) => {
  let connected = false;
  const writes: string[] = [];
  await page.route('**/api/me/ai-connection', async (route) => {
    const request = route.request();
    if (request.method() === 'GET') return route.fulfill({ json: { status: connected ? 'connected' : 'none' } });
    expect(request.headers()['idempotency-key']).toBeTruthy();
    writes.push(request.method());
    if (request.method() === 'DELETE') {
      connected = false;
      return route.fulfill({ json: { status: 'none' } });
    }
    if (request.postDataJSON().api_key === 'invalid-test-value') {
      return route.fulfill({ status: 422, json: { error: {
        code: 'AI_KEY_INVALID', message: '사용할 수 없는 키입니다. 다시 입력해 주세요.', details: null,
      } } });
    }
    connected = true;
    return route.fulfill({ json: { status: 'connected' } });
  });

  await page.goto('/');
  const opener = page.getByRole('button', { name: /^AI 연결/ });
  await opener.click();
  const dialog = page.getByRole('dialog', { name: 'AI 연결', exact: true });
  const key = dialog.getByLabel('OpenAI API 키', { exact: true });
  await expect(key).toHaveAttribute('type', 'password');
  await expect(dialog.getByRole('button', { name: '연결하기', exact: true })).toBeDisabled();
  await key.fill('invalid-test-value');
  await dialog.getByRole('button', { name: '키 보기', exact: true }).click();
  await expect(key).toHaveAttribute('type', 'text');
  await dialog.getByRole('button', { name: '키 숨기기', exact: true }).click();
  await dialog.getByRole('button', { name: '연결하기', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('사용할 수 없는 키');
  await expect(key).toHaveValue('invalid-test-value');
  await key.fill('valid-test-value');
  await dialog.getByRole('button', { name: '연결하기', exact: true }).click();
  await expect(dialog.getByText('AI가 연결되었습니다.', { exact: true })).toHaveAttribute('role', 'status');
  await expect(dialog.getByLabel('새 OpenAI API 키', { exact: true })).toHaveValue('');
  await expect(dialog.getByLabel('새 OpenAI API 키', { exact: true })).toHaveAttribute('type', 'password');
  await dialog.getByLabel('새 OpenAI API 키', { exact: true }).fill('replacement-test-value');
  await dialog.getByRole('button', { name: '키 교체', exact: true }).click();
  await expect(dialog.getByLabel('새 OpenAI API 키', { exact: true })).toHaveValue('');
  await dialog.getByRole('button', { name: '연결 해제', exact: true }).click();
  await expect(dialog.getByRole('region', { name: 'AI 연결을 해제할까요?' })).toBeVisible();
  await dialog.getByRole('button', { name: '연결 유지', exact: true }).click();
  expect(writes).toEqual(['PUT', 'PUT', 'PUT']);
  await dialog.getByRole('button', { name: '연결 해제', exact: true }).click();
  await dialog.getByRole('button', { name: '연결 해제', exact: true }).click();
  await expect(dialog.getByText('AI 연결을 해제했습니다.', { exact: true })).toHaveAttribute('role', 'status');
  await dialog.getByRole('button', { name: '완료', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(opener).toContainText('연결 안 됨');
  await expect(opener).toBeFocused();
  expect(writes).toEqual(['PUT', 'PUT', 'PUT', 'DELETE']);
  expect(await page.evaluate(() => [JSON.stringify(localStorage), JSON.stringify(sessionStorage)])).toEqual(['{}', '{}']);
});

test('Escape closes the modal without a key write and fits a narrow viewport', async ({ page }) => {
  const writes: string[] = [];
  await page.route('**/api/me/ai-connection', async (route) => {
    if (route.request().method() !== 'GET') writes.push(route.request().method());
    return route.fulfill({ json: { status: 'none' } });
  });
  await page.goto('/');
  const opener = page.getByRole('button', { name: /^AI 연결/ });
  await opener.click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('OpenAI API 키', { exact: true }).fill('cancelled-test-value');
  await page.setViewportSize({ width: 375, height: 667 });
  const bounds = await dialog.boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(375);
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  expect(writes).toEqual([]);
  await page.setViewportSize({ width: 1280, height: 800 });
  await opener.click();
  await expect(dialog.getByLabel('OpenAI API 키', { exact: true })).toHaveValue('');
});
