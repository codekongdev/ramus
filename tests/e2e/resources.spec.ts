import { randomUUID } from 'node:crypto';
import type { Page } from '@playwright/test';
import type { components } from '../../apps/web/src/api/schema';
import { test, expect, registerAccount } from './fixtures';

type ResourceDetail = components['schemas']['ResourceDetail'];
type AppliedResourceList = components['schemas']['AppliedResourceList'];

test.use({ viewport: { width: 1440, height: 1000 } });

const modal = (page: Page) => page.getByRole('dialog', { name: '스킬·자료', exact: true });
const selected = (page: Page) => modal(page).getByRole('list', { name: '선택한 스킬·자료', exact: true });
const row = (page: Page, resourceId: string) => modal(page).locator(`[data-resource-id="${resourceId}"]`);

async function createConversation(page: Page, email: string) {
  await registerAccount(page, email);
  const profile = await page.request.get('/api/me');
  expect(profile.ok()).toBe(true);
  const projectId = (await profile.json()).default_project_id as string;
  const title = `공통 기준 검토 ${randomUUID().slice(0, 8)}`;
  await page.getByRole('button', { name: '새 대화', exact: true }).click();
  await page.getByLabel('대화 제목', { exact: true }).fill(title);
  await page.getByRole('button', { name: '만들기', exact: true }).click();
  await expect(page.locator('[data-slot="conversation"]').getByRole('heading', { name: title, exact: true })).toBeVisible();
  return { projectId, conversationId: new URL(page.url()).pathname.split('/').at(-1)! };
}

async function openResources(page: Page) {
  await page.getByRole('button', { name: '스킬·자료', exact: true }).click();
  await expect(modal(page)).toBeVisible();
  await expect(modal(page).getByText('불러오는 중…', { exact: true })).toHaveCount(0);
}

async function createSkill(page: Page, projectId: string, name: string): Promise<ResourceDetail> {
  const response = await page.request.post(`/api/projects/${projectId}/resources`, {
    headers: { 'Idempotency-Key': randomUUID() },
    data: { kind: 'skill', name, description: '버전별 조사 기준', instructions: '출처를 확인한다.', content: null, file_name: null },
  });
  expect(response.ok()).toBe(true);
  return response.json();
}

async function appliedResources(page: Page, conversationId: string): Promise<AppliedResourceList> {
  const response = await page.request.get(`/api/conversations/${conversationId}/resources`);
  expect(response.ok()).toBe(true);
  return response.json();
}

test('registers imported SKILL.md as v1, searches name and description, and persists the exact applied revision', async ({ page, testServer }) => {
  const { projectId, conversationId } = await createConversation(page, `b1-import-${randomUUID()}@example.test`);
  await openResources(page);
  await modal(page).locator('.resources-toolbar').getByRole('button', { name: '스킬 등록', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(1);

  let creates = 0;
  page.on('request', request => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === `/api/projects/${projectId}/resources`) creates++;
  });
  await modal(page).getByRole('button', { name: '등록', exact: true }).click();
  await expect(modal(page).getByText('이름을 입력하세요.', { exact: true })).toBeVisible();
  await expect(modal(page).getByText('지침을 입력하세요.', { exact: true })).toBeVisible();
  await expect(modal(page).getByRole('button', { name: '등록', exact: true })).toBeDisabled();
  expect(creates).toBe(0);

  await modal(page).getByLabel('이름', { exact: true }).fill('유지할 초안');
  await modal(page).getByLabel('설명', { exact: true }).fill('파일 오류가 나도 유지할 설명');
  await modal(page).getByLabel('지침', { exact: true }).fill('기존 지침을 유지한다.');
  const file = modal(page).getByTestId('skill-file-input');
  await file.setInputFiles({ name: 'guide.pdf', mimeType: 'application/pdf', buffer: Buffer.from('unsupported file') });
  await expect(modal(page).getByText('.md 또는 .txt 파일만 불러올 수 있습니다.', { exact: true })).toBeVisible();
  await expect(modal(page).getByLabel('이름', { exact: true })).toHaveValue('유지할 초안');
  await expect(modal(page).getByLabel('설명', { exact: true })).toHaveValue('파일 오류가 나도 유지할 설명');
  await expect(modal(page).getByLabel('지침', { exact: true })).toHaveValue('기존 지침을 유지한다.');
  expect(creates).toBe(0);

  const name = `벤치마킹 ${randomUUID().slice(0, 8)}`;
  const description = `경쟁사 자료 조사 ${randomUUID().slice(0, 8)}`;
  const instructions = '비교할 때 출처와 조사 날짜를 함께 기록한다.';
  await file.setInputFiles({
    name: 'SKILL.md', mimeType: 'text/markdown',
    buffer: Buffer.from(`---\nname: ${name}\ndescription: ${description}\n---\n\n${instructions}\n`, 'utf8'),
  });
  await expect(modal(page).getByLabel('이름', { exact: true })).toHaveValue(name);
  await expect(modal(page).getByLabel('설명', { exact: true })).toHaveValue(description);
  await expect(modal(page).getByLabel('지침', { exact: true })).toHaveValue(instructions);
  await expect(modal(page).getByText('.md 또는 .txt 파일만 불러올 수 있습니다.', { exact: true })).toHaveCount(0);
  await page.screenshot({ path: 'artifacts/b1-register-1440.png', fullPage: true });

  const createdResponse = page.waitForResponse(response => response.request().method() === 'POST'
    && new URL(response.url()).pathname === `/api/projects/${projectId}/resources`);
  await modal(page).getByRole('button', { name: '등록', exact: true }).click();
  const response = await createdResponse;
  expect(response.ok()).toBe(true);
  const detail: ResourceDetail = await response.json();
  expect(detail.revision.number).toBe(1);
  expect(detail.revision.instructions).toBe(instructions);
  expect(detail.revisions).toHaveLength(1);
  expect(creates).toBe(1);
  await expect(selected(page)).toContainText(`${name} · v1`);
  const search = modal(page).getByLabel('스킬·자료 검색', { exact: true });
  await search.fill(name);
  await expect(row(page, detail.id)).toBeVisible();
  await search.fill(description);
  await expect(row(page, detail.id)).toBeVisible();
  await expect(row(page, detail.id).getByRole('checkbox')).toBeChecked();
  await expect(selected(page)).toContainText(`${name} · v1`);
  await modal(page).getByRole('button', { name: '적용', exact: true }).click();
  await expect(modal(page)).toHaveCount(0);
  expect((await appliedResources(page, conversationId)).items.map(item => item.revision_id)).toEqual([detail.revision.id]);

  await page.reload();
  await expect(page.locator('.app-shell')).toBeVisible();
  await openResources(page);
  await expect(row(page, detail.id)).toContainText('v1 · 현재 적용');
  await expect(row(page, detail.id).getByRole('checkbox')).toBeChecked();
  await expect(selected(page)).toContainText(`${name} · v1`);
  await expect(modal(page).getByRole('button', { name: '적용', exact: true })).toBeDisabled();
});

test('keeps an applied v1 when v2 exists and changes the conversation only after explicit apply', async ({ page, testServer }) => {
  const { projectId, conversationId } = await createConversation(page, `b1-versions-${randomUUID()}@example.test`);
  const name = `버전 고정 ${randomUUID().slice(0, 8)}`;
  const detail = await createSkill(page, projectId, name);
  const pin = await page.request.put(`/api/conversations/${conversationId}/resources`, {
    headers: { 'Idempotency-Key': randomUUID() }, data: { revision_ids: [detail.revision.id] },
  });
  expect(pin.ok()).toBe(true);
  const revisionResponse = await page.request.post(`/api/resources/${detail.id}/revisions`, {
    headers: { 'Idempotency-Key': randomUUID() },
    data: { base_revision_id: detail.revision.id, name, description: '새 조사 기준', instructions: '출처와 날짜를 확인한다.', content: null, file_name: null },
  });
  expect(revisionResponse.ok()).toBe(true);
  const latest = (await revisionResponse.json()).revision as components['schemas']['ResourceRevision'];
  expect(latest.number).toBe(2);

  // The search can finish before the applied-version read. Until the pinned v1
  // arrives, selecting a latest revision must not erase the conversation's inputs.
  let releaseApplied!: () => void;
  const appliedGate = new Promise<void>(resolve => { releaseApplied = resolve; });
  await page.route(`**/api/conversations/${conversationId}/resources`, async route => {
    if (route.request().method() === 'GET') await appliedGate;
    await route.continue();
  });
  await page.getByRole('button', { name: '스킬·자료', exact: true }).click();
  await expect(modal(page)).toBeVisible();
  await modal(page).getByLabel('스킬·자료 검색', { exact: true }).fill(name);
  try {
    await expect(row(page, detail.id).getByRole('checkbox')).toBeDisabled();
    await expect(modal(page).getByRole('button', { name: '적용', exact: true })).toBeDisabled();
  } finally {
    releaseApplied();
  }
  await expect(row(page, detail.id)).toContainText('최신 v2 · 현재 적용 v1');
  await expect(selected(page)).toContainText(`${name} · v1`);
  await expect(modal(page).getByRole('button', { name: '적용', exact: true })).toBeDisabled();
  const bounds = await modal(page).boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(1440);
  await page.screenshot({ path: 'artifacts/b1-versions-1440.png', fullPage: true });
  await modal(page).getByRole('button', { name: '닫기', exact: true }).click();
  expect((await appliedResources(page, conversationId)).items.map(item => item.revision_id)).toEqual([detail.revision.id]);

  await openResources(page);
  await row(page, detail.id).getByRole('button', { name: '최신 v2로 바꾸기', exact: true }).click();
  await expect(selected(page)).toContainText(`${name} · v2`);
  expect((await appliedResources(page, conversationId)).items.map(item => item.revision_id)).toEqual([detail.revision.id]);
  await modal(page).getByRole('button', { name: '적용', exact: true }).click();
  await expect(modal(page)).toHaveCount(0);
  expect((await appliedResources(page, conversationId)).items.map(item => item.revision_id)).toEqual([latest.id]);
});

test('retains query and selection after apply failure and retries the same request key', async ({ page, testServer }) => {
  const { projectId, conversationId } = await createConversation(page, `b1-retry-${randomUUID()}@example.test`);
  const name = `재시도 기준 ${randomUUID().slice(0, 8)}`;
  const detail = await createSkill(page, projectId, name);
  await openResources(page);
  await modal(page).getByLabel('스킬·자료 검색', { exact: true }).fill(name);
  await row(page, detail.id).getByRole('checkbox').check();
  await expect(selected(page)).toContainText(`${name} · v1`);

  const attempts: { key: string; body: unknown }[] = [];
  await page.route(`**/api/conversations/${conversationId}/resources`, async route => {
    const request = route.request();
    if (request.method() !== 'PUT') return route.continue();
    attempts.push({ key: request.headers()['idempotency-key'], body: request.postDataJSON() });
    if (attempts.length === 1) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: {
        code: 'TEST_APPLY_UNAVAILABLE', message: '잠시 적용할 수 없습니다. 다시 시도해 주세요.', details: null,
      } }) });
    } else await route.continue();
  });
  await modal(page).getByRole('button', { name: '적용', exact: true }).click();
  await expect(modal(page).getByRole('alert')).toHaveText('요청을 처리하는 중에 문제가 생겼습니다. 잠시 후 다시 시도해 주세요.');
  await expect(modal(page).getByLabel('스킬·자료 검색', { exact: true })).toHaveValue(name);
  await expect(row(page, detail.id).getByRole('checkbox')).toBeChecked();
  await expect(selected(page)).toContainText(`${name} · v1`);
  expect((await appliedResources(page, conversationId)).items).toEqual([]);
  await modal(page).getByRole('button', { name: '적용', exact: true }).click();
  await expect(modal(page)).toHaveCount(0);
  expect(attempts).toHaveLength(2);
  expect(attempts[0].key).toBeTruthy();
  expect(attempts[1]).toEqual(attempts[0]);
  expect(attempts[1].body).toEqual({ revision_ids: [detail.revision.id] });
  expect((await appliedResources(page, conversationId)).items.map(item => item.revision_id)).toEqual([detail.revision.id]);
});
