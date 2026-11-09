import type { components } from '../../apps/web/src/api/schema';
import { test, expect, requestLoginCode, finishLogin } from './fixtures';

type S = components['schemas'];
const headers = () => ({ 'Idempotency-Key': crypto.randomUUID() });
test.use({ viewport: { width: 1440, height: 1000 } });

test('shows real branch and conclusion usage, opens the task, and preserves the conversation draft', async ({ page, testServer }) => {
  const email = `a9-${crypto.randomUUID()}@example.test`;
  await requestLoginCode(page, email);
  await finishLogin(page, await testServer.codeFor(email));
  const project = await (await page.request.post('/api/projects', { data: { name: 'A9 관계 지도' }, headers: headers() })).json() as S['Project'];
  const create = async (title: string): Promise<S['Conversation']> => {
    const response = await page.request.post(`/api/projects/${project.id}/conversations`, { data: { title }, headers: headers() });
    expect(response.ok()).toBe(true); return response.json();
  };
  const source = await create('A9 서비스 방향');
  const target = await create('A9 결론을 사용할 대화');
  expect((await page.request.put('/api/me/ai-connection', { data: { api_key: 'valid-test-a9' }, headers: headers() })).ok()).toBe(true);
  expect((await page.request.post(`/api/conversations/${source.id}/messages`, { data: { body: '@AI 조사해 주세요.' }, headers: headers() })).ok()).toBe(true);
  let task!: S['Task'];
  await expect.poll(async () => { const response = await page.request.get(`/api/conversations/${source.id}/tasks`); task = (await response.json()).items[0]; return task?.status; }).toBe('ready');
  const summary = await page.request.post(`/api/tasks/${task.id}/summaries`, { data: {}, headers: headers() });
  expect(summary.ok()).toBe(true); let result = await summary.json() as S['Result'];
  await expect.poll(async () => { result = await (await page.request.get(`/api/results/${result.id}`)).json(); return result.draft?.status; }).toBe('ready');
  const saved = await page.request.post(`/api/results/${result.id}/revisions`, { data: { base_version: 0, conclusion: 'A9 결론', source_run_id: result.draft!.run_id }, headers: headers() });
  expect(saved.ok()).toBe(true); const revision = await saved.json() as S['ResultRevision'];
  expect((await page.request.post(`/api/result-revisions/${revision.id}/shares`, { data: { conversation_ids: [source.id, target.id] }, headers: headers() })).ok()).toBe(true);
  await page.goto(`/projects/${project.id}/conversations/${source.id}`);
  const draft = page.getByLabel('메시지', { exact: true }); await draft.fill('지도 확인 중인 초안');
  const opener = page.getByRole('button', { name: '프로젝트 구조', exact: true }); await opener.click();
  const graph = page.getByRole('dialog', { name: '프로젝트 구조' });
  const map = graph.getByRole('region', { name: '프로젝트 관계 지도' });
  await expect(map.getByRole('button', { name: /경쟁사 분석/ })).toBeVisible();
  await expect(map.locator('svg line')).toHaveCount(1);
  await expect(map.locator('svg path.is-dashed')).toHaveCount(2);
  const separation = await map.locator('svg').evaluate(svg => {
    const branch = svg.querySelector('line')!;
    const midpoint = { x: (Number(branch.getAttribute('x1')) + Number(branch.getAttribute('x2'))) / 2,
      y: (Number(branch.getAttribute('y1')) + Number(branch.getAttribute('y2'))) / 2 };
    // Only the child-to-parent use edge has the branch's reversed endpoints.
    const reverse = [...svg.querySelectorAll('path.is-dashed')].find(path => {
      const start = path.getPointAtLength(0), end = path.getPointAtLength(path.getTotalLength());
      return Math.abs(start.x - Number(branch.getAttribute('x2'))) < 0.1 && Math.abs(end.x - Number(branch.getAttribute('x1'))) < 0.1;
    })!;
    const point = reverse.getPointAtLength(reverse.getTotalLength() / 2);
    return Math.hypot(point.x - midpoint.x, point.y - midpoint.y);
  });
  expect(separation).toBeGreaterThan(20);
  await graph.getByText('관계 텍스트로 보기').click();
  await expect(graph).toContainText('A9 서비스 방향 → 경쟁사 분석: 분기');
  await expect(graph).toContainText('경쟁사 분석 → A9 결론을 사용할 대화: 결론 사용');
  await expect(graph).toContainText('경쟁사 분석 → A9 서비스 방향: 결론 사용');
  const taskNode = map.getByRole('button', { name: /경쟁사 분석/ }); await taskNode.focus();
  await graph.getByRole('button', { name: '새로고침' }).click();
  await expect(map.getByRole('button', { name: /경쟁사 분석/ })).toBeVisible();
  await map.getByRole('button', { name: /경쟁사 분석/ }).click();
  await expect(graph).toHaveCount(0);
  const taskModal = page.getByRole('dialog', { name: '경쟁사 분석' }); await expect(taskModal).toBeVisible();
  await taskModal.getByRole('button', { name: '닫기' }).click();
  await expect(taskModal).toHaveCount(0); await expect(draft).toHaveValue('지도 확인 중인 초안');
});

test('retries malformed data and keeps long nodes separated', async ({ page, testServer }) => {
  const email = `a9-errors-${crypto.randomUUID()}@example.test`;
  await requestLoginCode(page, email); await finishLogin(page, await testServer.codeFor(email));
  const me = await (await page.request.get('/api/me')).json() as S['Me'];
  const title = '긴 프로젝트 관계 제목 '.repeat(12).trim(); let attempt = 0;
  await page.route(`**/api/projects/${me.default_project_id}/graph`, route => {
    attempt++;
    const nodes = [{ conversation_id: 'first', title, parent_id: null, task_status: null }, { conversation_id: 'second', title: '두 번째 대화', parent_id: null, task_status: null }];
    return route.fulfill({ json: { nodes, edges: attempt === 1 ? [{ kind: 'branch', from: 'first', to: 'missing' }] : [] } });
  });
  const opener = page.getByRole('button', { name: '프로젝트 구조', exact: true }); await opener.focus(); await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: '프로젝트 구조' }); await expect(dialog.getByRole('alert')).toBeVisible();
  await dialog.getByRole('button', { name: '다시 시도' }).click();
  const first = dialog.getByRole('button', { name: title }), second = dialog.getByRole('button', { name: '두 번째 대화' });
  await expect(first).toBeVisible(); const a = await first.boundingBox(), b = await second.boundingBox();
  expect(a && b && (a.y + a.height <= b.y || b.y + b.height <= a.y)).toBe(true);
  await first.focus();
  await dialog.getByRole('button', { name: '새로고침' }).evaluate(button => (button as HTMLButtonElement).click());
  await expect(first).toBeVisible();
  await expect(first).toBeFocused();
  await page.keyboard.press('Escape'); await expect(opener).toBeFocused();
});
