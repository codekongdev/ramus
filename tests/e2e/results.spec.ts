import { test, expect, requestLoginCode, finishLogin } from './fixtures';
import type { Page } from '@playwright/test';
import type { components } from '../../apps/web/src/api/schema';
import { task as initialTask, conversation, parent, message, me, createdAt } from '../../apps/web/tests/fixtures/tasks';

type S = components['schemas'];
type Result = S['Result'];
type Revision = S['ResultRevision'];

async function mockResults(page: Page, connected = true) {
  let task = { ...initialTask, status: 'ready' as const };
  let result: Result | null = null;
  const revisions = new Map<string, Revision>();
  const summaries: string[] = [];
  const saves: { base_version: number; conclusion: string }[] = [];
  let conflictNextSave = false;
  await page.addInitScript(() => {
    const sources: EventTarget[] = [];
    class FakeEventSource extends EventTarget {
      onopen: ((event: Event) => void) | null = null;
      constructor() { super(); sources.push(this); setTimeout(() => this.onopen?.(new Event('open')), 0); }
      close() { const i = sources.indexOf(this); if (i >= 0) sources.splice(i, 1); }
    }
    Object.assign(window, { EventSource: FakeEventSource, emitResult: (data: unknown) => sources.forEach(source =>
      source.dispatchEvent(new MessageEvent('result.updated', { data: JSON.stringify(data) }))) });
  });
  const emit = async () => {
    if (!result) throw new Error('No result');
    await page.evaluate(data => (window as unknown as { emitResult: (data: unknown) => void }).emitResult(data), {
      result_id: result.id, task_id: task.id, draft_status: result.draft?.status ?? null,
      latest_version: result.latest_version, occurred_at: createdAt,
    });
  };
  const addRevision = (conclusion: string): Revision => {
    if (!result) throw new Error('No result');
    const version = (result.latest_version ?? 0) + 1;
    const revision: Revision = {
      id: `revision-${version}`, result_id: result.id, version, title: result.title, conclusion,
      source: { conversation_id: 'child1', message_from_seq: 1, message_to_seq: 2,
        resource_revision_ids: [], input_result_revision_ids: [], run_id: result.draft?.run_id ?? 'summary-1' },
      saved_by: 'u1', created_at: createdAt,
    };
    revisions.set(revision.id, revision);
    result = { ...result, latest_version: version, latest_revision_id: revision.id, draft: null,
      revisions: [...result.revisions, { id: revision.id, version, saved_by: 'u1', created_at: createdAt }] };
    return revision;
  };
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (value: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });
    if (request.method() === 'GET') {
      if (path === '/api/me') return json({ ...me, ai_connection: { status: connected ? 'connected' : 'none' } });
      if (path === '/api/me/ai-connection') return json({ status: connected ? 'connected' : 'none' });
      if (path === '/api/projects') return json({ items: [{ id: 'p1', name: '공동 샘플', is_shared_sample: true }] });
      if (path === '/api/projects/p1/participants') return json({ items: [me.account] });
      if (path === '/api/projects/p1/conversations') return json({ items: [parent, conversation] });
      if (path === '/api/conversations/c1/tasks') return json({ items: [task] });
      if (path === '/api/tasks/t1') return json(task);
      if (path === '/api/conversations/c1') return json(parent);
      if (path === '/api/conversations/child1') return json(conversation);
      if (path.endsWith('/messages')) return json({ items: path.includes('child1') ? [message] : [], next_after_seq: null });
      if (path.endsWith('/inputs')) return json({ items: [] });
      if (path === '/api/results/result1' && result) return json(result);
      if (path.startsWith('/api/result-revisions/')) {
        const revision = revisions.get(path.split('/').at(-1)!);
        if (revision) return json(revision);
      }
    } else {
      const key = request.headers()['idempotency-key'];
      expect(key).toBeTruthy();
      if (path === '/api/me/ai-connection') { connected = true; return json({ status: 'connected' }); }
      if (path === '/api/tasks/t1/summaries') {
        summaries.push(key);
        task = { ...task, result_id: 'result1' };
        result = { id: 'result1', project_id: 'p1', title: task.title,
          source_conversation_id: 'child1', source_task_id: task.id,
          latest_version: result?.latest_version ?? null, latest_revision_id: result?.latest_revision_id ?? null,
          revisions: result?.revisions ?? [], draft: { status: 'generating', conclusion: null,
            base_version: result?.latest_version ?? 0, run_id: `summary-${summaries.length}`, error: null, updated_at: createdAt } };
        return json(result);
      }
      if (path === '/api/results/result1/revisions') {
        const body = request.postDataJSON() as S['SaveResultRevisionRequest'];
        saves.push(body);
        if (conflictNextSave) {
          conflictNextSave = false;
          addRevision('다른 참여자가 저장한 결론');
          return json({ error: { code: 'VERSION_CONFLICT', message: '기준 버전이 변경되었습니다.', details: null } }, 409);
        }
        const sourceRun = result?.draft?.run_id ?? revisions.get(result?.latest_revision_id ?? '')?.source.run_id;
        if (body.base_version !== (result?.latest_version ?? 0) || body.source_run_id !== sourceRun) {
          return json({ error: { code: 'VERSION_CONFLICT', message: '편집 기준이 변경되었습니다.', details: null } }, 409);
        }
        return json(addRevision(body.conclusion));
      }
    }
    return json({ error: { code: 'NOT_FOUND', message: '대상을 찾을 수 없습니다.', details: null } }, 404);
  });
  return {
    summaries, saves,
    addRevision,
    seed(conclusion: string) {
      task = { ...task, result_id: 'result1' };
      result = { id: 'result1', project_id: 'p1', title: task.title,
        source_conversation_id: 'child1', source_task_id: task.id,
        latest_version: null, latest_revision_id: null, revisions: [], draft: null };
      return addRevision(conclusion);
    },
    async publish(conclusion: string) { const revision = addRevision(conclusion); await emit(); return revision; },
    conflict() { conflictNextSave = true; },
    async complete(conclusion = '가입 혜택과 반품 예외를 함께 안내합니다.') {
      await expect.poll(() => result?.draft?.status).toBe('generating');
      if (!result?.draft) throw new Error('No draft');
      result = { ...result, draft: { ...result.draft, status: 'ready', conclusion } };
      await emit();
    },
    async fail() {
      await expect.poll(() => result?.draft?.status).toBe('generating');
      if (!result?.draft) throw new Error('No draft');
      result = { ...result, draft: { ...result.draft, status: 'failed', conclusion: null,
        error: { code: 'LLM_UNAVAILABLE', message: 'AI 요청을 처리하지 못했습니다. 다시 시도해 주세요.' } } };
      await emit();
    },
    async replaceDraft() {
      if (!result?.draft) throw new Error('No draft');
      result = { ...result, draft: { ...result.draft, run_id: 'summary-replaced',
        status: 'ready', conclusion: '다른 참여자가 다시 정리한 새 초안' } };
      await emit();
    },
    emit,
  };
}

async function openTask(page: Page) {
  await page.goto('/projects/p1/conversations/c1');
  await page.locator('[data-slot="task-queue"]').getByRole('button', { name: /경쟁사 분석/ }).click();
  return page.getByRole('dialog', { name: '경쟁사 분석', exact: true });
}

test('summarize, edit and save v1/v2; failed regeneration preserves the approved conclusion', async ({ page }) => {
  const fixture = await mockResults(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  const dialog = await openTask(page);
  await dialog.getByRole('button', { name: '결과 정리', exact: true }).click();
  await expect(dialog.getByRole('tab', { name: '결과', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(dialog.getByRole('button', { name: '정리 중', exact: true })).toBeDisabled();
  await expect.poll(() => fixture.summaries.length).toBe(1);
  await dialog.getByRole('button', { name: '닫기', exact: true }).click();
  await page.locator('[data-slot="task-queue"]').getByRole('button', { name: /경쟁사 분석/ }).click();
  await dialog.getByRole('tab', { name: '결과', exact: true }).click();
  await expect(dialog.getByRole('button', { name: '정리 중', exact: true })).toBeDisabled();
  await fixture.complete();
  await dialog.getByLabel('결론', { exact: true }).fill('검토자가 수정한 멤버십 결론');
  await dialog.getByRole('button', { name: '새 버전 저장', exact: true }).click();
  await expect(dialog).toContainText('검토자가 수정한 멤버십 결론');
  await expect(dialog.getByRole('button', { name: '결론 수정', exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: '결론 수정', exact: true }).click();
  await dialog.getByLabel('결론', { exact: true }).fill('두 번째 승인 결론');
  await dialog.getByRole('button', { name: '새 버전 저장', exact: true }).click();
  await expect(dialog).toContainText('두 번째 승인 결론');
  expect(fixture.saves.map(save => save.base_version)).toEqual([0, 1]);
  await dialog.getByRole('button', { name: '다시 정리', exact: true }).click();
  await fixture.fail();
  await expect(dialog).toContainText('AI 요청을 처리하지 못했습니다.');
  await expect(dialog).toContainText('두 번째 승인 결론');
  await page.screenshot({ path: 'artifacts/b4-results-1440.png', fullPage: true });
});

test('a conflicting save and realtime refresh preserve the local edit until explicit rebase', async ({ page }) => {
  const fixture = await mockResults(page);
  const dialog = await openTask(page);
  await dialog.getByRole('button', { name: '결과 정리', exact: true }).click();
  await fixture.complete();
  const editor = dialog.getByLabel('결론', { exact: true });
  await editor.fill('충돌해도 보존할 나의 초안');
  fixture.conflict();
  await dialog.getByRole('button', { name: '새 버전 저장', exact: true }).click();
  await expect(dialog).toContainText('다른 참여자가 결과를 변경했습니다.');
  await expect(editor).toHaveValue('충돌해도 보존할 나의 초안');
  await fixture.emit();
  await expect(editor).toHaveValue('충돌해도 보존할 나의 초안');
  await dialog.getByRole('button', { name: '최신 버전 확인', exact: true }).click();
  await expect(dialog).toContainText('다른 참여자가 저장한 결론');
  await dialog.getByRole('button', { name: '최신 버전 기준으로 계속 수정', exact: true }).click();
  await expect(editor).toHaveValue('충돌해도 보존할 나의 초안');
  await dialog.getByRole('button', { name: '새 버전 저장', exact: true }).click();
  await expect(dialog.getByRole('button', { name: '결론 수정', exact: true })).toBeVisible();
  expect(fixture.saves.map(save => save.base_version)).toEqual([0, 1]);
});

test('a replaced draft keeps the local text and requires reviewing the new source before saving', async ({ page }) => {
  const fixture = await mockResults(page);
  const dialog = await openTask(page);
  await dialog.getByRole('button', { name: '결과 정리', exact: true }).click();
  await fixture.complete();
  const editor = dialog.getByLabel('결론', { exact: true });
  await editor.fill('재정리와 충돌해도 유지할 검토 내용');
  await fixture.replaceDraft();
  await expect(editor).toHaveValue('재정리와 충돌해도 유지할 검토 내용');
  await dialog.getByRole('button', { name: '새 버전 저장', exact: true }).click();
  await expect(dialog).toContainText('다른 참여자가 결과를 변경했습니다.');
  await expect(dialog).toContainText('다른 참여자가 다시 정리한 새 초안');
  await dialog.getByRole('button', { name: '최신 버전 기준으로 계속 수정', exact: true }).click();
  await expect(editor).toHaveValue('재정리와 충돌해도 유지할 검토 내용');
  await dialog.getByRole('button', { name: '새 버전 저장', exact: true }).click();
  await expect(dialog.getByRole('button', { name: '결론 수정', exact: true })).toBeVisible();
  expect(fixture.saves.map(save => (save as S['SaveResultRevisionRequest']).source_run_id)).toEqual(['summary-1', 'summary-replaced']);
});

test('a cancelled AI connection does not start a summary; connection resumes exactly once', async ({ page }) => {
  const fixture = await mockResults(page, false);
  const dialog = await openTask(page);
  await dialog.getByRole('button', { name: '결과 정리', exact: true }).click();
  const connection = page.getByRole('dialog', { name: 'AI를 사용하려면 연결해 주세요', exact: true });
  await expect(connection).toBeVisible();
  await connection.getByRole('button', { name: '취소', exact: true }).click();
  await expect(dialog).toBeVisible();
  expect(fixture.summaries).toHaveLength(0);
  await dialog.getByRole('button', { name: '결과 정리', exact: true }).click();
  await connection.getByLabel('OpenAI API 키', { exact: true }).fill('valid-test-summary');
  await connection.getByRole('button', { name: '연결하고 요청 실행', exact: true }).click();
  await expect(dialog.getByRole('button', { name: '정리 중', exact: true })).toBeVisible();
  await expect.poll(() => fixture.summaries.length).toBe(1);
});

test('real server stores summary revisions and reopens the approved result', async ({ page, testServer }) => {
  const email = `b4-${Date.now()}@example.test`;
  await requestLoginCode(page, email);
  await finishLogin(page, await testServer.codeFor(email));
  const identity = await (await page.request.get('/api/me')).json();
  const key = () => ({ 'Idempotency-Key': crypto.randomUUID() });
  const connection = await page.request.put('/api/me/ai-connection', { data: { api_key: 'valid-test-b4-server' }, headers: key() });
  expect(connection.ok()).toBe(true);
  const created = await page.request.post(`/api/projects/${identity.default_project_id}/conversations`, {
    data: { title: 'B4 결과 정리 검증' }, headers: key(),
  });
  expect(created.ok()).toBe(true);
  const parentId = (await created.json()).id;
  const requested = await page.request.post(`/api/conversations/${parentId}/messages`, {
    data: { body: '@AI 경쟁사 멤버십 정책을 조사해 주세요.' }, headers: key(),
  });
  expect(requested.ok()).toBe(true);
  await page.goto(`/projects/${identity.default_project_id}/conversations/${parentId}`);
  const queue = page.locator('[data-slot="task-queue"]');
  await expect(queue).toContainText('준비됨');
  await queue.getByRole('button', { name: /경쟁사 분석/ }).click();
  const dialog = page.getByRole('dialog', { name: '경쟁사 분석', exact: true });
  await dialog.getByRole('button', { name: '결과 정리', exact: true }).click();
  await expect(dialog.getByLabel('결론', { exact: true })).toHaveValue('테스트 결론입니다.');
  await dialog.getByLabel('결론', { exact: true }).fill('실제 저장 경로에서 승인한 결론');
  await dialog.getByRole('button', { name: '새 버전 저장', exact: true }).click();
  await expect(dialog.getByRole('button', { name: '결론 수정', exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: '닫기', exact: true }).click();
  await queue.getByRole('button', { name: /경쟁사 분석/ }).click();
  await dialog.getByRole('tab', { name: '결과', exact: true }).click();
  await expect(dialog).toContainText('실제 저장 경로에서 승인한 결론');
  const before = await (await page.request.get(`/api/projects/${identity.default_project_id}/conversations`)).json();
  const writes: string[] = [];
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/') && request.method() !== 'GET') writes.push(request.url()); });
  await dialog.getByRole('button', { name: '결론 보기', exact: true }).click();
  const reader = page.locator('dialog[open]');
  await expect(reader).toContainText('실제 저장 경로에서 승인한 결론');
  await expect(reader.getByText('출처 정보', { exact: true })).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeVisible();
  expect(writes).toEqual([]);
  expect(await (await page.request.get(`/api/projects/${identity.default_project_id}/conversations`)).json()).toEqual(before);
});

test('conclusion reading preserves the parent draft, route and scroll and never writes', async ({ page }) => {
  const fixture = await mockResults(page);
  fixture.seed('고정된 결론\n본문만 읽습니다.');
  await page.goto('/projects/p1/conversations/c1');
  const parentDraft = page.getByRole('textbox', { name: '메시지', exact: true });
  await parentDraft.fill('보내지 않은 부모 초안');
  const parentMessages = page.locator('.conversation__messages');
  await parentMessages.evaluate(node => { node.insertAdjacentHTML('beforeend', '<div style="height:3000px"></div>'); node.scrollTop = 350; });
  const scroll = await parentMessages.evaluate(node => node.scrollTop);
  const writes: string[] = [];
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/') && request.method() !== 'GET') writes.push(request.url()); });
  await page.locator('[data-slot="task-queue"]').getByRole('button', { name: /경쟁사 분석/ }).click();
  const taskDialog = page.locator('dialog[open]');
  await taskDialog.getByRole('tab', { name: '결과', exact: true }).click();
  await expect(taskDialog.getByRole('region', { name: '결론 본문', exact: true })).toContainText('고정된 결론');
  await taskDialog.getByRole('button', { name: '결론 보기', exact: true }).click();
  const reader = page.locator('dialog[open]');
  await expect(reader).toContainText('고정된 결론');
  await expect(reader.getByRole('button', { name: '새 대화 만들기', exact: true })).toBeDisabled();
  await expect(reader.getByRole('button', { name: '다른 대화에 보내기', exact: true })).toBeEnabled();
  await expect(reader.getByRole('textbox')).toHaveCount(0);
  await expect(reader.getByText('출처 정보', { exact: true })).toHaveCount(0);
  await page.screenshot({ path: 'artifacts/b5-conclusion-desktop.png', fullPage: true });
  const readerElement = await reader.elementHandle();
  await reader.getByRole('button', { name: '다른 대화에 보내기', exact: true }).click();
  await expect(reader.getByLabel('대화 검색', { exact: true })).toBeVisible();
  await expect(page.locator('dialog[open]')).toHaveCount(1);
  await reader.getByRole('button', { name: '결론으로 돌아가기', exact: true }).click();
  expect(await reader.evaluate((node, original) => node === original, readerElement)).toBe(true);
  await expect(reader.getByRole('button', { name: '다른 대화에 보내기', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('dialog[open]').getByRole('tab', { name: '결과', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('dialog[open]').getByRole('button', { name: '결론 보기', exact: true })).toBeFocused();
  await page.locator('dialog[open]').getByRole('button', { name: '닫기', exact: true }).click();
  await expect(parentDraft).toHaveValue('보내지 않은 부모 초안');
  expect(await parentMessages.evaluate(node => node.scrollTop)).toBe(scroll);
  expect(new URL(page.url()).pathname).toBe('/projects/p1/conversations/c1');
  expect(writes).toEqual([]);
  expect(fixture.summaries).toEqual([]);
  expect(fixture.saves).toEqual([]);
});

test('history and a received-conclusion reader stay on the chosen version across newer approvals', async ({ page }) => {
  const fixture = await mockResults(page);
  fixture.seed('첫 번째 버전의 결론');
  fixture.addRevision('두 번째 버전의 결론');
  const dialog = await openTask(page);
  await dialog.getByRole('tab', { name: '결과', exact: true }).click();
  await expect(dialog).toContainText('두 번째 버전의 결론');
  await dialog.getByRole('button', { name: 'v1', exact: true }).click();
  await expect(dialog).toContainText('첫 번째 버전의 결론');
  await fixture.publish('세 번째 버전의 결론');
  await expect(dialog.getByRole('button', { name: 'v3', exact: true })).toBeVisible();
  await expect(dialog.getByRole('region', { name: '결론 본문', exact: true })).toContainText('첫 번째 버전의 결론');
  await dialog.getByRole('button', { name: '결론 보기', exact: true }).click();
  await expect(page.locator('dialog[open]')).toContainText('첫 번째 버전의 결론');
  await fixture.publish('네 번째 버전의 결론');
  await expect(page.locator('dialog[open]')).toContainText('첫 번째 버전의 결론');
  await page.locator('dialog[open]').getByRole('button', { name: '닫기', exact: true }).click();
  expect(fixture.summaries).toEqual([]);
  expect(fixture.saves).toEqual([]);
});

test('long conclusion stays readable on mobile with equal side-by-side actions', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const fixture = await mockResults(page);
  fixture.seed('긴결론'.repeat(800));
  const dialog = await openTask(page);
  await dialog.getByRole('tab', { name: '결과', exact: true }).click();
  await dialog.getByRole('button', { name: '결론 보기', exact: true }).click();
  const reader = page.locator('dialog[open]');
  await expect(reader.getByRole('heading', { name: '결론', exact: true })).toBeVisible();
  const actions = reader.locator('.conclusion-view__actions');
  await actions.scrollIntoViewIfNeeded();
  const buttons = await actions.locator('button').all();
  const boxes = await Promise.all(buttons.map(button => button.boundingBox()));
  expect(boxes[0]!.y).toBe(boxes[1]!.y);
  expect(boxes[0]!.width).toBeCloseTo(boxes[1]!.width, 0);
  expect(await reader.evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true);
  const bounds = await reader.boundingBox();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(375);
  await page.screenshot({ path: 'artifacts/b5-conclusion-mobile.png' });
  await reader.getByRole('button', { name: '닫기', exact: true }).click();
});
