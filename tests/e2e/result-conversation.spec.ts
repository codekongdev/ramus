import type { Page } from '@playwright/test';
import { test, expect, registerAccount } from './fixtures';
import { task, conversation, parent, me, createdAt } from '../../apps/web/tests/fixtures/tasks';
import { result, revision } from '../../apps/web/tests/results-fixtures';

async function mockFollowup(page: Page, sourceAccess = true) {
  const projects = [
    { id: 'p1', name: '공동 샘플', is_shared_sample: true },
    { id: 'p2', name: '사용자 경험 개선', is_shared_sample: false },
  ];
  const old = { ...revision, conclusion: '선택한 이전 버전 결론' };
  const latest = { ...old, id: 'revision2', version: 2, conclusion: '최신 버전 결론' };
  const current = { ...result, draft: null, latest_revision_id: latest.id, latest_version: 2,
    revisions: [old, latest].map(item => ({ id: item.id, version: item.version, saved_by: item.saved_by, created_at: item.created_at })) };
  const created = { ...parent, id: 'new-conversation', project_id: 'p2', title: '고객 경험 개선안' };
  const requests: { key: string; body: { result_revision_id: string; title: string } }[] = [];
  const sourceReads: string[] = [];
  let failure: 'network' | 'permission' | null = null;
  await page.addInitScript(() => {
    class FakeEventSource extends EventTarget {
      onopen: (() => void) | null = null;
      constructor() { super(); queueMicrotask(() => this.onopen?.()); }
      close() {}
    }
    Object.assign(window, { EventSource: FakeEventSource });
  });
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const json = (value: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });
    if (request.method() === 'POST') {
      expect(path).toBe('/api/projects/p2/conversations/from-result');
      requests.push({ key: request.headers()['idempotency-key'], body: request.postDataJSON() });
      const mode = failure; failure = null;
      if (mode === 'network') return route.abort('failed');
      if (mode === 'permission') return json({ error: { code: 'PROJECT_CREATE_FORBIDDEN', message: '권한 변경', details: null } }, 403);
      return json(created);
    }
    if (path === '/api/me') return json({ ...me, ai_connection: { status: 'none' } });
    if (path === '/api/me/password') return json({ configured: true });
    if (path === '/api/projects') return json({ items: projects });
    if (path === '/api/projects/search') return json({ items: projects.filter(item => item.name.includes(url.searchParams.get('q') ?? '')) });
    if (path.endsWith('/participants')) return json({ items: [me.account] });
    if (path === '/api/projects/p1/conversations') return json({ items: [parent, conversation] });
    if (path === '/api/projects/p2/conversations') return json({ items: [created] });
    if (path === '/api/tasks/t1') return json({ ...task, result_id: result.id, status: 'ready' });
    if (path.endsWith('/tasks')) return json({ items: path.includes('/c1/') ? [{ ...task, result_id: result.id, status: 'ready' }] : [] });
    if (path === '/api/conversations/c1') return json(parent);
    if (path === '/api/conversations/child1') return json(conversation);
    if (path === '/api/conversations/new-conversation') return json(created);
    if (path.endsWith('/messages')) return json({ items: [], next_after_seq: null });
    if (path.startsWith('/api/results/') || path.startsWith('/api/result-revisions/')) {
      sourceReads.push(path);
      if (!sourceAccess) return json({ error: { code: 'NOT_FOUND', message: '대상을 찾을 수 없습니다.', details: null } }, 404);
      if (path === '/api/results/result1') return json(current);
      if (path === '/api/result-revisions/revision1') return json(old);
      if (path === '/api/result-revisions/revision2') return json(latest);
    }
    if (path.endsWith('/inputs/input1')) return json({
      id: 'input1', conversation_id: created.id, result_id: result.id, result_revision_id: old.id,
      version: old.version, latest_version: sourceAccess ? 2 : 1, title: old.title, origin: 'new_conversation', created_by: 'u1', created_at: createdAt,
      conclusion: old.conclusion, source: old.source,
    });
    if (path.endsWith('/inputs')) return json({ items: path.includes('/new-conversation/') ? [{
      id: 'input1', conversation_id: created.id, result_id: result.id, result_revision_id: old.id,
      version: old.version, latest_version: 2, title: old.title, origin: 'new_conversation', created_by: 'u1', created_at: createdAt,
    }] : [] });
    return json({ error: { code: 'NOT_FOUND', message: '대상을 찾을 수 없습니다.', details: null } }, 404);
  });
  return { requests, sourceReads, fail(mode: 'network' | 'permission') { failure = mode; } };
}

async function openCreation(page: Page) {
  await page.goto('/projects/p1/conversations/c1');
  await page.locator('[data-slot="task-queue"]').getByRole('button', { name: new RegExp(task.title) }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('tab', { name: '결과', exact: true }).click();
  await expect(dialog).toContainText('최신 버전 결론');
  await dialog.getByRole('button', { name: 'v1', exact: true }).click();
  await expect(dialog).toContainText('선택한 이전 버전 결론');
  await dialog.evaluate(node => node.setAttribute('data-original-dialog', 'true'));
  await dialog.getByRole('button', { name: '새 대화 만들기', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(1);
  await expect(dialog).toHaveAttribute('data-original-dialog', 'true');
  await expect(dialog).toContainText('선택한 이전 버전 결론');
  return dialog;
}

test('chooses a project, preserves an old conclusion in the same dialog, and navigates only after creation', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const fixture = await mockFollowup(page);
  const dialog = await openCreation(page);
  const create = dialog.getByRole('button', { name: '만들기', exact: true });
  await expect(create).toBeDisabled();
  await dialog.getByLabel('프로젝트 검색', { exact: true }).fill('없는 프로젝트');
  await expect(dialog).toContainText('일치하는 프로젝트가 없습니다.');
  await dialog.getByLabel('프로젝트 검색', { exact: true }).fill('사용자 경험');
  await dialog.getByRole('button', { name: '사용자 경험 개선 선택', exact: true }).click();
  await expect(create).toBeDisabled();
  await dialog.getByLabel('대화 제목', { exact: true }).fill('고객 경험 개선안');
  await expect(create).toBeEnabled();
  await page.screenshot({ path: 'artifacts/b7-create-1440.png', fullPage: true });
  await create.click();
  await expect(page).toHaveURL('/projects/p2/conversations/new-conversation');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '고객 경험 개선안', exact: true })).toBeVisible();
  const inputs = page.getByRole('region', { name: '연결된 결론', exact: true });
  await expect(inputs).toContainText(revision.title);
  await expect(inputs).toContainText('v1');
  expect(fixture.requests).toHaveLength(1);
  expect(fixture.requests[0].body).toEqual({ result_revision_id: revision.id, title: '고객 경험 개선안' });
  await page.screenshot({ path: 'artifacts/b7-created-1440.png', fullPage: true });
});

test('back preserves the conclusion and failed requests retain the form and reuse the action key', async ({ page }) => {
  const fixture = await mockFollowup(page);
  const dialog = await openCreation(page);
  await dialog.getByRole('button', { name: '결론 보기로 돌아가기', exact: true }).click();
  await expect(dialog).toContainText('선택한 이전 버전 결론');
  expect(fixture.requests).toHaveLength(0);
  await dialog.getByRole('button', { name: '새 대화 만들기', exact: true }).click();
  await dialog.getByRole('button', { name: '사용자 경험 개선 선택', exact: true }).click();
  await dialog.getByLabel('대화 제목', { exact: true }).fill('고객 경험 개선안');
  fixture.fail('network');
  await dialog.getByRole('button', { name: '만들기', exact: true }).click();
  await expect(dialog.getByRole('alert')).toBeVisible();
  await expect(page).toHaveURL('/projects/p1/conversations/c1');
  await expect(dialog.getByLabel('대화 제목', { exact: true })).toHaveValue('고객 경험 개선안');
  await dialog.getByRole('button', { name: '만들기', exact: true }).click();
  await expect(page).toHaveURL('/projects/p2/conversations/new-conversation');
  expect(fixture.requests).toHaveLength(2);
  expect(fixture.requests[0]).toEqual(fixture.requests[1]);
});

test('a permission change keeps the conclusion and title but requires choosing a project again', async ({ page }) => {
  const fixture = await mockFollowup(page);
  const dialog = await openCreation(page);
  await dialog.getByRole('button', { name: '사용자 경험 개선 선택', exact: true }).click();
  await dialog.getByLabel('대화 제목', { exact: true }).fill('고객 경험 개선안');
  fixture.fail('permission');
  await dialog.getByRole('button', { name: '만들기', exact: true }).click();
  await expect(dialog).toContainText('다른 프로젝트를 선택해 주세요.');
  await expect(dialog.getByRole('button', { name: '만들기', exact: true })).toBeDisabled();
  await expect(dialog.getByLabel('대화 제목', { exact: true })).toHaveValue('고객 경험 개선안');
  await expect(dialog).toContainText('선택한 이전 버전 결론');
  await expect(page).toHaveURL('/projects/p1/conversations/c1');
});

test('a recipient opens only the pinned snapshot and starts another conversation without source access', async ({ page }) => {
  const fixture = await mockFollowup(page, false);
  await page.goto('/projects/p2/conversations/new-conversation');
  await page.getByRole('button', { name: `${revision.title} v1 결론 보기`, exact: true }).click();
  const dialog = page.getByRole('dialog', { name: revision.title, exact: true });
  await expect(dialog).toContainText('선택한 이전 버전 결론');
  await dialog.evaluate(node => node.setAttribute('data-original-dialog', 'true'));
  await dialog.getByRole('button', { name: '새 대화 만들기', exact: true }).click();
  const creation = page.getByRole('dialog');
  await expect(creation).toHaveAttribute('data-original-dialog', 'true');
  await expect(creation).toContainText('선택한 이전 버전 결론');
  await creation.getByRole('button', { name: '사용자 경험 개선 선택', exact: true }).click();
  await creation.getByLabel('대화 제목', { exact: true }).fill('고객 경험 개선안');
  await creation.getByRole('button', { name: '만들기', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(fixture.sourceReads).toEqual([]);
  expect(fixture.requests[0].body.result_revision_id).toBe(revision.id);
});

test('the creation form stays within small and landscape viewports with reduced motion', async ({ page }) => {
  await mockFollowup(page);
  const dialog = await openCreation(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const viewport of [{ width: 375, height: 812 }, { width: 812, height: 375 }]) {
    await page.setViewportSize(viewport);
    const bounds = await dialog.boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width);
    await dialog.getByLabel('프로젝트 검색', { exact: true }).fill('사용자 경험');
    await dialog.getByRole('button', { name: '사용자 경험 개선 선택', exact: true }).click();
    await dialog.getByLabel('대화 제목', { exact: true }).fill('고객 경험 개선안');
    await expect(dialog.getByRole('button', { name: '만들기', exact: true })).toBeEnabled();
    await page.screenshot({ path: `artifacts/b7-create-${viewport.width}.png`, fullPage: true });
  }
});

test('real server creates a root conversation with exactly the viewed conclusion and no automatic AI run', async ({ page, testServer }) => {
  const email = `b7-${Date.now()}@example.test`;
  await registerAccount(page, email);
  const me = await (await page.request.get('/api/me')).json();
  const headers = () => ({ 'Idempotency-Key': crypto.randomUUID() });
  async function post(path: string, data: unknown) {
    const response = await page.request.post(path, { data, headers: headers() });
    expect(response.ok(), path).toBe(true);
    return response.json();
  }
  const project = await post('/api/projects', { name: 'B7 후속 프로젝트' });
  await page.request.put('/api/me/ai-connection', { data: { api_key: 'valid-test-b7' }, headers: headers() });
  const parent = await post(`/api/projects/${me.default_project_id}/conversations`, { title: 'B7 출처 대화' });
  await post(`/api/conversations/${parent.id}/messages`, { body: '@AI 경쟁사 멤버십 정책을 조사해 주세요.' });
  let taskId = '';
  await expect.poll(async () => {
    const tasks = await (await page.request.get(`/api/conversations/${parent.id}/tasks`)).json();
    taskId = tasks.items[0]?.id ?? '';
    return tasks.items[0]?.status;
  }).toBe('ready');
  const summary = await post(`/api/tasks/${taskId}/summaries`, {});
  let sourceRunId = '';
  await expect.poll(async () => {
    const result = await (await page.request.get(`/api/results/${summary.id}`)).json();
    sourceRunId = result.draft?.run_id ?? '';
    return result.draft?.status;
  }).toBe('ready');
  const old = await post(`/api/results/${summary.id}/revisions`, { base_version: 0, source_run_id: sourceRunId, conclusion: 'B7 선택한 v1 결론' });
  await post(`/api/results/${summary.id}/revisions`, { base_version: 1, source_run_id: sourceRunId, conclusion: 'B7 최신 v2 결론' });
  await page.request.delete('/api/me/ai-connection', { headers: headers() });
  await page.goto(`/projects/${me.default_project_id}/conversations/${parent.id}`);
  await page.locator('[data-slot="task-queue"]').getByRole('button', { name: /경쟁사 분석/ }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('tab', { name: '결과', exact: true }).click();
  await dialog.getByRole('button', { name: 'v1', exact: true }).click();
  await expect(dialog).toContainText(old.conclusion);
  await dialog.getByRole('button', { name: '새 대화 만들기', exact: true }).click();
  await dialog.getByLabel('프로젝트 검색', { exact: true }).fill('B7 후속');
  await dialog.getByRole('button', { name: 'B7 후속 프로젝트 선택', exact: true }).click();
  await dialog.getByLabel('대화 제목', { exact: true }).fill('B7 후속 기획');
  await dialog.getByRole('button', { name: '만들기', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${project.id}/conversations/`));
  await expect(page.getByRole('heading', { name: 'B7 후속 기획', exact: true })).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const id = new URL(page.url()).pathname.split('/').at(-1);
  const detail = await (await page.request.get(`/api/conversations/${id}`)).json();
  expect(detail).toMatchObject({ project_id: project.id, parent_id: null, task_id: null, active_run: null });
  const inputs = await (await page.request.get(`/api/conversations/${id}/inputs`)).json();
  expect(inputs.items).toHaveLength(1);
  expect(inputs.items[0]).toMatchObject({ result_revision_id: old.id, version: 1, origin: 'new_conversation' });
  await expect(page.getByRole('region', { name: '연결된 결론', exact: true })).toContainText('v1');
  await page.getByRole('button', { name: `${old.title} v1 결론 보기`, exact: true }).click();
  await expect(page.getByRole('dialog', { name: old.title, exact: true })).toContainText(old.conclusion);
  await page.getByRole('dialog').getByRole('button', { name: '닫기', exact: true }).click();
  expect((await (await page.request.get(`/api/conversations/${id}/messages`)).json()).items).toEqual([]);
  expect((await (await page.request.get(`/api/conversations/${id}/resources`)).json()).items).toEqual([]);

  // The pinned cross-project conclusion keeps its normal send action in the receiving project.
  const destination = await post(`/api/projects/${project.id}/conversations`, { title: 'B7 후속 수신 대화' });
  await page.getByRole('button', { name: `${old.title} v1 결론 보기`, exact: true }).click();
  const received = page.getByRole('dialog');
  await received.getByRole('button', { name: '다른 대화에 보내기', exact: true }).click();
  await received.getByLabel('대화 검색', { exact: true }).fill('B7 후속 수신');
  await received.getByRole('checkbox', { name: 'B7 후속 수신 대화', exact: false }).check();
  await received.getByRole('button', { name: '보내기', exact: true }).click();
  await expect(received.getByRole('button', { name: '다른 대화에 보내기', exact: true })).toBeFocused();
  const forwarded = await (await page.request.get(`/api/conversations/${destination.id}/inputs`)).json();
  expect(forwarded.items).toHaveLength(1);
  expect(forwarded.items[0]).toMatchObject({ result_revision_id: old.id, version: 1, origin: 'share' });
  const destinationDetail = await (await page.request.get(`/api/conversations/${destination.id}`)).json();
  expect(destinationDetail.active_run).toBeNull();
});
