import { test, expect, requestLoginCode, finishLogin } from './fixtures';
import type { Page } from '@playwright/test';
import type { components } from '../../apps/web/src/api/schema';

type S = components['schemas'];
const headers = () => ({ 'Idempotency-Key': crypto.randomUUID() });

async function createProject(page: Page, name: string): Promise<S['Project']> {
  const response = await page.request.post('/api/projects', { data: { name }, headers: headers() });
  expect(response.ok()).toBe(true);
  return response.json();
}

test('real saved heads appear live, drafts stay out, and switching projects isolates the read-only library', async ({ page, testServer }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Chromium's offline emulation can leave an existing SSE stream alive. Fail that
  // transport explicitly while keeping REST, event decoding and reconnects real.
  await page.addInitScript(() => {
    const NativeEventSource = window.EventSource;
    const sources = new Set<EventSource>();
    window.EventSource = class extends NativeEventSource {
      constructor(url: string | URL, options?: EventSourceInit) {
        super(url, options);
        sources.add(this);
      }
      close() { sources.delete(this); super.close(); }
    };
    Object.assign(window, { disconnectTestEvents: () => {
      for (const source of [...sources]) source.dispatchEvent(new Event('error'));
    } });
  });
  let interruptEvents = false;
  await page.route('**/api/projects/*/events', route => interruptEvents ? route.abort('internetdisconnected') : route.continue());
  const email = `b8-library-${crypto.randomUUID()}@example.test`;
  await requestLoginCode(page, email);
  await finishLogin(page, await testServer.codeFor(email));
  const project = await createProject(page, 'B8 결과물 검증');
  const connection = await page.request.put('/api/me/ai-connection', { data: { api_key: 'valid-test-b8-library' }, headers: headers() });
  expect(connection.ok()).toBe(true);
  const created = await page.request.post(`/api/projects/${project.id}/conversations`, { data: { title: 'B8 멤버십 검토' }, headers: headers() });
  expect(created.ok()).toBe(true);
  const conversation: S['Conversation'] = await created.json();
  expect((await page.request.post(`/api/conversations/${conversation.id}/messages`, {
    data: { body: '@AI 경쟁사 멤버십 정책을 조사해 주세요.' }, headers: headers(),
  })).ok()).toBe(true);
  let tasks: S['Task'][] = [];
  await expect.poll(async () => {
    tasks = (await (await page.request.get(`/api/conversations/${conversation.id}/tasks`)).json()).items;
    return tasks[0]?.status;
  }).toBe('ready');
  const summarized = await page.request.post(`/api/tasks/${tasks[0].id}/summaries`, { data: {}, headers: headers() });
  expect(summarized.ok()).toBe(true);
  let result: S['Result'] = await summarized.json();
  await expect.poll(async () => {
    result = await (await page.request.get(`/api/results/${result.id}`)).json();
    return result.draft?.status;
  }).toBe('ready');

  await page.goto(`/projects/${project.id}/conversations/${conversation.id}`);
  const composer = page.getByLabel('메시지', { exact: true });
  await composer.fill('결과물을 확인하면서 유지할 대화 초안');
  const opener = page.getByRole('button', { name: '결과물', exact: true });
  await opener.click();
  const dialog = page.getByRole('dialog', { name: '결과물', exact: true });
  await expect(dialog).toContainText('아직 저장된 결과물이 없습니다.');
  expect(await dialog.getByRole('checkbox').count()).toBe(0);
  expect(await dialog.getByRole('button', { name: /새 대화|보내기|저장/ }).count()).toBe(0);

  for (const version of [1, 2]) {
    if (version === 2) {
      interruptEvents = true;
      await page.evaluate(() => (window as unknown as { disconnectTestEvents: () => void }).disconnectTestEvents());
    }
    const saved = await page.request.post(`/api/results/${result.id}/revisions`, {
      data: { base_version: version - 1, conclusion: `승인한 멤버십 구성안 ${version}`, source_run_id: result.draft!.run_id }, headers: headers(),
    });
    expect(saved.ok()).toBe(true);
    const row = dialog.locator(`[data-result-id="${result.id}"]`);
    if (version === 2) {
      await expect(row).toContainText('v1');
      interruptEvents = false;
    }
    await expect(row).toContainText(`v${version}`);
    await expect(row).toContainText(tasks[0].title);
    await expect(dialog.getByRole('listitem')).toHaveCount(1);
  }
  await page.screenshot({ path: 'artifacts/b8-results-library-1440.png', fullPage: true });
  const writes: string[] = [];
  page.on('request', request => { if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.url()); });
  await dialog.getByRole('button', { name: '새로고침', exact: true }).click();
  await expect(dialog.locator(`[data-result-id="${result.id}"]`)).toContainText('v2');
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(opener).toBeFocused();
  await expect(composer).toHaveValue('결과물을 확인하면서 유지할 대화 초안');
  await expect(page).toHaveURL(new RegExp(`/conversations/${conversation.id}$`));
  await opener.click();
  await expect(dialog.locator(`[data-result-id="${result.id}"]`)).toContainText('v2');
  await dialog.getByRole('button', { name: '닫기', exact: true }).click();
  expect(writes).toEqual([]);
  await page.reload();
  await opener.click();
  await expect(dialog.locator(`[data-result-id="${result.id}"]`)).toContainText('v2');
  await page.keyboard.press('Escape');

  const other = await createProject(page, 'B8 빈 프로젝트');
  await page.getByRole('button', { name: /B8 결과물 검증/ }).click();
  await page.getByRole('button', { name: `프로젝트 열기: ${other.name}`, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${other.id}$`));
  await opener.click();
  await expect(dialog).toContainText('아직 저장된 결과물이 없습니다.');
  await expect(dialog.getByRole('listitem')).toHaveCount(0);
});

test('retries server and schema errors, wraps long titles on a narrow screen, and restores keyboard focus', async ({ page, testServer }) => {
  const email = `b8-errors-${crypto.randomUUID()}@example.test`;
  await requestLoginCode(page, email);
  await finishLogin(page, await testServer.codeFor(email));
  const me: S['Me'] = await (await page.request.get('/api/me')).json();
  const longTitle = '검토한 멤버십 정책과 가입 혜택 및 반품 예외를 함께 정리한 결론 '.repeat(6).trim();
  const item: S['ProjectResultSummary'] = {
    result_id: 'result-long', title: longTitle, latest_version: 12, latest_revision_id: 'revision-12',
    source_conversation_title: '멤버십 정책 조사와 사용자 경험 검토 '.repeat(5).trim(), updated_at: '2026-11-09T02:00:00Z',
  };
  let attempt = 0;
  await page.route(`**/api/projects/${me.default_project_id}/results`, route => {
    attempt += 1;
    const body = attempt === 1 ? { error: { code: 'INTERNAL_ERROR', message: 'private database error', details: null } }
      : { items: [attempt === 2 ? { ...item, updated_at: 'invalid' } : item] };
    return route.fulfill({ status: attempt === 1 ? 500 : 200, json: body });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  const opener = page.getByRole('button', { name: '결과물', exact: true });
  await opener.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: '결과물', exact: true });
  await expect(dialog.getByRole('alert')).toBeVisible();
  await expect(dialog).not.toContainText('private database error');
  await dialog.getByRole('button', { name: '다시 시도', exact: true }).click();
  await expect.poll(() => attempt).toBe(2);
  await expect(dialog.getByRole('alert')).toBeVisible();
  await dialog.getByRole('button', { name: '다시 시도', exact: true }).click();
  await expect(dialog.getByRole('listitem')).toHaveCount(1);
  await expect(dialog).toContainText('v12');
  await expect(dialog).toContainText(longTitle);
  expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: 'artifacts/b8-results-library-390.png', fullPage: true });
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(opener).toBeFocused();
});
