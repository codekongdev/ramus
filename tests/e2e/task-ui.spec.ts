import { test, expect, type Page } from '@playwright/test';
import { task as initialTask, conversation, parent, message as initialMessage, me, createdAt } from '../../apps/web/tests/fixtures/tasks';

async function fixture(page: Page, accountId = 'u1', connected = true) {
  let task = { ...initialTask };
  let messages = [{ ...initialMessage }];
  const mutations: string[] = [];
  await page.addInitScript(() => {
    const sources: EventTarget[] = [];
    class FakeEventSource extends EventTarget {
      onopen: ((event: Event) => void) | null = null;
      constructor() { super(); sources.push(this); setTimeout(() => this.onopen?.(new Event('open')), 0); }
      close() { const index = sources.indexOf(this); if (index >= 0) sources.splice(index, 1); }
    }
    Object.assign(window, { EventSource: FakeEventSource,
      emitProjectEvent: (type: string, data: unknown) => sources.forEach(source => source.dispatchEvent(new MessageEvent(type, { data: JSON.stringify(data) }))),
    });
  });
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (request.method() === 'GET') {
      if (path === '/api/me') return json({ ...me, account: { ...me.account, id: accountId }, ai_connection: { status: connected ? 'connected' : 'none' } });
      if (path === '/api/me/ai-connection') return json({ status: connected ? 'connected' : 'none' });
      if (path === '/api/projects') return json({ items: [{ id: 'p1', name: '공동 샘플', is_shared_sample: true }] });
      if (path === '/api/projects/p1/participants') return json({ items: [me.account] });
      if (path === '/api/projects/p1/conversations') return json({ items: [parent, conversation] });
      if (path === '/api/conversations/c1/tasks') return json({ items: [task] });
      if (path === '/api/tasks/t1') return json(task);
      if (path === '/api/conversations/child1') return json(conversation);
      if (path === '/api/conversations/child1/messages') return json({ items: messages, next_after_seq: null });
    } else {
      mutations.push(path);
      expect(request.headers()['idempotency-key']).toBeTruthy();
      if (path === '/api/me/ai-connection') {
        connected = true;
        return json({ status: 'connected' });
      }
      if (path === '/api/conversations/child1/messages') {
        const body = request.postDataJSON().body;
        const added = { ...initialMessage, id: `m${messages.length + 1}`, seq: messages.length + 1,
          author: { kind: 'human' as const, account_id: accountId, display_name: '민서' }, body, run_id: null };
        messages.push(added);
        const run = /@ai/i.test(body) ? { id: 'run2', conversation_id: 'child1', task_id: 't1', purpose: 'work',
          status: 'pending', requested_by: accountId, error: null, created_at: createdAt, started_at: null, finished_at: null } : null;
        return json({ message: added, run });
      }
      if (path === '/api/tasks/t1/cancel') { task = { ...task, status: 'cancelled' }; return json(task); }
      if (path === '/api/tasks/t1/retry') { task = { ...task, status: 'pending' }; return json(task); }
    }
    return json({ error: { code: 'NOT_FOUND', message: '테스트 경로가 없습니다.', details: null } }, 404);
  });
  const update = async (status: typeof task.status) => {
    task = { ...task, status };
    await page.evaluate(({ status }) => {
      (window as unknown as { emitProjectEvent: (type: string, data: unknown) => void }).emitProjectEvent('task.updated', {
        source_conversation_id: 'c1', task: { id: 't1', title: '경쟁사 분석', status, child_conversation_id: 'child1', result_id: null }, occurred_at: '2026-11-09T01:00:01Z',
      });
    }, { status });
  };
  return { mutations, update };
}

test('queue and tree open one task modal without navigating; updates and close do not interrupt work', async ({ page }) => {
  const { mutations, update } = await fixture(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/projects/p1/conversations/c1');
  const queue = page.locator('[data-slot="task-queue"]');
  await expect(queue.getByRole('button', { name: /경쟁사 분석/ })).toContainText('대기 중');
  await update('running');
  await expect(queue).toContainText('진행 중');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await update('ready');
  await expect(queue).toContainText('준비됨');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await queue.getByRole('button', { name: /경쟁사 분석/ }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText(initialMessage.body);
  await expect(dialog).toContainText(initialTask.goal);
  await page.screenshot({ path: 'artifacts/a6-a7-task-modal-1440.png', fullPage: true });
  await dialog.getByLabel('작업 메시지', { exact: true }).fill('반품 조건도 함께 확인해 주세요.');
  await dialog.getByRole('button', { name: '전송', exact: true }).click();
  await expect(dialog).toContainText('반품 조건도 함께 확인해 주세요.');
  await dialog.getByLabel('작업 메시지', { exact: true }).fill('@AI 예외 사례도 보완해 주세요.');
  await dialog.getByRole('button', { name: '전송', exact: true }).click();
  await expect(dialog).toContainText('@AI 예외 사례도 보완해 주세요.');
  await dialog.getByRole('button', { name: '닫기', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(mutations.filter(path => path.endsWith('/cancel'))).toHaveLength(0);
  await expect(page).toHaveURL(/\/projects\/p1\/conversations\/c1$/);
  await page.locator('[data-slot="conversation-tree"]').getByRole('button', { name: /경쟁사 분석/ }).click();
  await expect(dialog).toContainText(initialMessage.body);
  await expect(page.locator('dialog')).toHaveCount(1);
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(page).toHaveURL(/\/projects\/p1\/conversations\/c1$/);
});

test('a keyless task request retains its draft on cancel and resumes exactly once after connection', async ({ page }) => {
  const { mutations, update } = await fixture(page, 'u1', false);
  await page.goto('/projects/p1/conversations/c1');
  await expect(page.locator('[data-slot="task-queue"]')).toContainText('경쟁사 분석');
  await update('ready');
  await page.locator('[data-slot="task-queue"]').getByRole('button', { name: /경쟁사 분석/ }).click();
  const taskDialog = page.getByRole('dialog', { name: '경쟁사 분석', exact: true });
  const draft = taskDialog.getByLabel('작업 메시지', { exact: true });
  await draft.fill('@AI 원래 작업의 예외 사례를 보완해 주세요.');
  await taskDialog.getByRole('button', { name: '전송', exact: true }).click();
  const connectionDialog = page.getByRole('dialog', { name: 'AI를 사용하려면 연결해 주세요', exact: true });
  await expect(connectionDialog).toBeVisible();
  await expect(page.locator('dialog[open]')).toHaveCount(1);
  await connectionDialog.getByRole('button', { name: '취소', exact: true }).click();
  await expect(taskDialog).toBeVisible();
  await expect(draft).toHaveValue('@AI 원래 작업의 예외 사례를 보완해 주세요.');
  expect(mutations).toEqual([]);
  await taskDialog.getByRole('button', { name: '전송', exact: true }).click();
  await expect(connectionDialog).toBeVisible();
  await connectionDialog.getByLabel('OpenAI API 키', { exact: true }).fill('valid-test-task-request');
  await connectionDialog.getByRole('button', { name: '연결하고 요청 실행', exact: true }).click();
  await expect(taskDialog).toBeVisible();
  await expect(taskDialog).toContainText('@AI 원래 작업의 예외 사례를 보완해 주세요.');
  await expect(draft).toHaveValue('');
  expect(mutations).toEqual(['/api/me/ai-connection', '/api/conversations/child1/messages']);
  await expect(page).toHaveURL(/\/projects\/p1\/conversations\/c1$/);
  await expect(page.locator('dialog[open]')).toHaveCount(1);
});

test('requester can stop and retry; another member can read and discuss without controlling the run', async ({ browser }) => {
  const owner = await browser.newPage();
  const viewer = await browser.newPage();
  try {
    const ownerFixture = await fixture(owner);
    const viewerFixture = await fixture(viewer, 'u2');
    await Promise.all([owner.goto('/projects/p1/conversations/c1'), viewer.goto('/projects/p1/conversations/c1')]);
    await Promise.all([owner, viewer].map(page => expect(page.locator('[data-slot="task-queue"]')).toContainText('경쟁사 분석')));
    await Promise.all([ownerFixture.update('running'), viewerFixture.update('running')]);
    await owner.locator('[data-slot="task-queue"]').getByRole('button').click();
    await expect(owner.getByRole('dialog').getByRole('button', { name: '작업 중단' })).toBeVisible();
    await expect(viewer.getByRole('dialog')).toHaveCount(0);
    await viewer.locator('[data-slot="task-queue"]').getByRole('button').click();
    await expect(viewer.getByRole('dialog').getByRole('button', { name: '작업 중단' })).toHaveCount(0);
    await viewer.getByRole('dialog').getByLabel('작업 메시지', { exact: true }).fill('진행 중에도 논의를 남깁니다.');
    await viewer.getByRole('dialog').getByRole('button', { name: '전송', exact: true }).click();
    await expect(viewer.getByRole('dialog')).toContainText('진행 중에도 논의를 남깁니다.');
    await owner.getByRole('dialog').getByRole('button', { name: '작업 중단' }).click();
    await expect(owner.getByRole('dialog')).toContainText('중단됨');
    await owner.getByRole('dialog').getByRole('button', { name: '작업 다시 시도' }).click();
    await expect(owner.getByRole('dialog')).toContainText('대기 중');
    expect(ownerFixture.mutations.filter(path => path.endsWith('/cancel'))).toHaveLength(1);
    expect(ownerFixture.mutations.filter(path => path.endsWith('/retry'))).toHaveLength(1);
    expect(viewerFixture.mutations.filter(path => /\/(cancel|retry)$/.test(path))).toHaveLength(0);
  } finally { await owner.close(); await viewer.close(); }
});
