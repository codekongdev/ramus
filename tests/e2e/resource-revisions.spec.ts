import { randomUUID } from 'node:crypto';
import type { Page } from '@playwright/test';
import type { components } from '../../apps/web/src/api/schema';
import { test, expect, requestLoginCode, finishLogin } from './fixtures';

type Detail = components['schemas']['ResourceDetail'];
const modal = (page: Page) => page.getByRole('dialog', { name: '스킬·자료', exact: true });
const detailView = (page: Page) => modal(page).locator('[data-step="detail"]');

async function signIn(page: Page, codeFor: (email: string) => Promise<string>) {
  const email = `b2-${randomUUID()}@example.test`;
  await requestLoginCode(page, email);
  await finishLogin(page, await codeFor(email));
  const profile = await page.request.get('/api/me');
  expect(profile.ok()).toBe(true);
  return profile.json();
}

async function createFixture(page: Page, projectId: string, kind: 'skill' | 'file' = 'skill') {
  const name = `공통 조사 기준 ${randomUUID().slice(0, 8)}`;
  const created = await page.request.post(`/api/projects/${projectId}/resources`, {
    headers: { 'Idempotency-Key': randomUUID() },
    data: { kind, name, description: '출처 확인 방법', instructions: kind === 'skill' ? 'v1: 공식 출처를 확인한다.' : null, content: kind === 'file' ? '기존 원본 파일의 내용' : null, file_name: kind === 'file' ? 'original.md' : null },
  });
  expect(created.ok()).toBe(true);
  const resource: Detail = await created.json();
  const title = `버전 관리 논의 ${randomUUID().slice(0, 8)}`;
  await page.getByRole('button', { name: '새 대화', exact: true }).click();
  await page.getByLabel('대화 제목', { exact: true }).fill(title);
  await page.getByRole('button', { name: '만들기', exact: true }).click();
  await expect(page.locator('[data-slot="conversation"]').getByRole('heading', { name: title })).toBeVisible();
  const conversationId = new URL(page.url()).pathname.split('/').at(-1)!;
  const pin = await page.request.put(`/api/conversations/${conversationId}/resources`, {
    headers: { 'Idempotency-Key': randomUUID() }, data: { revision_ids: [resource.revision.id] },
  });
  expect(pin.ok()).toBe(true);
  return { resource, conversationId };
}

async function openDetail(page: Page, name: string) {
  await page.getByRole('button', { name: '스킬·자료', exact: true }).click();
  await modal(page).getByLabel('스킬·자료 검색', { exact: true }).fill(name);
  await modal(page).getByRole('button', { name: `${name} 상세·버전 이력`, exact: true }).click();
  await expect(detailView(page)).toBeVisible();
  await expect(modal(page).getByRole('button', { name: '수정', exact: true })).toBeVisible();
}

async function applied(page: Page, conversationId: string): Promise<string[]> {
  const response = await page.request.get(`/api/conversations/${conversationId}/resources`);
  expect(response.ok()).toBe(true);
  const body: components['schemas']['AppliedResourceList'] = await response.json();
  return body.items.map(item => item.revision_id);
}

async function saveAnotherVersion(page: Page, resource: Detail) {
  const response = await page.request.post(`/api/resources/${resource.id}/revisions`, {
    headers: { 'Idempotency-Key': randomUUID() },
    data: { base_revision_id: resource.revision.id, name: resource.revision.name, description: '동료가 수정한 기준', instructions: 'v2: 출처와 발행 날짜를 기록한다.', content: null, file_name: null },
  });
  expect(response.ok()).toBe(true);
  return (await response.json()).revision as components['schemas']['ResourceRevision'];
}

test('saving a new version preserves another conversation pin until explicit latest or historical apply', async ({ browser, testServer }) => {
  const contexts = await Promise.all([0, 1].map(() => browser.newContext({ baseURL: testServer.url, viewport: { width: 1440, height: 1000 } })));
  try {
    const [author, editor] = await Promise.all(contexts.map(context => context.newPage()));
    const [one, two] = await Promise.all([signIn(author, testServer.codeFor), signIn(editor, testServer.codeFor)]);
    expect(one.default_project_id).toBe(two.default_project_id);
    const { resource, conversationId } = await createFixture(author, one.default_project_id);
    await openDetail(editor, resource.revision.name);
    await modal(editor).getByRole('button', { name: '수정', exact: true }).click();
    await modal(editor).getByLabel('지침', { exact: true }).fill('v2: 출처와 발행 날짜를 기록한다.');
    const savedResponse = editor.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === `/api/resources/${resource.id}/revisions`);
    await modal(editor).getByRole('button', { name: '새 버전 저장', exact: true }).click();
    const response = await savedResponse;
    expect(response.ok()).toBe(true);
    const saved = (await response.json()).revision as components['schemas']['ResourceRevision'];
    expect(saved.number).toBe(2);
    expect(saved.created_by).toBe(two.account.id);
    await expect(detailView(editor)).toContainText('v2: 출처와 발행 날짜를 기록한다.');
    await expect(detailView(editor)).toContainText(two.account.display_name);
    await expect(editor.getByRole('dialog')).toHaveCount(1);
    expect(await applied(author, conversationId)).toEqual([resource.revision.id]);

    await openDetail(author, resource.revision.name);
    await expect(detailView(author)).toContainText('v2: 출처와 발행 날짜를 기록한다.');
    await author.screenshot({ path: 'artifacts/b2-detail-1440.png', fullPage: true });
    await author.setViewportSize({ width: 390, height: 844 });
    const bounds = await modal(author).boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(390);
    expect(await modal(author).evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    const historyRows = modal(author).getByRole('list', { name: '버전 이력', exact: true }).getByRole('button');
    for (const row of await historyRows.all()) {
      expect(await row.evaluate(element => element.scrollHeight <= element.clientHeight)).toBe(true);
    }
    await author.screenshot({ path: 'artifacts/b2-detail-390.png' });
    await author.setViewportSize({ width: 1440, height: 1000 });
    await modal(author).getByRole('button', { name: 'v1 보기', exact: true }).focus();
    await author.keyboard.press('Enter');
    await expect(detailView(author)).toContainText('v1: 공식 출처를 확인한다.');
    await expect(detailView(author)).toContainText(one.account.display_name);
    expect(await applied(author, conversationId)).toEqual([resource.revision.id]);
    await modal(author).getByRole('button', { name: 'v2 보기', exact: true }).click();
    await modal(author).getByRole('button', { name: '현재 대화에 적용', exact: true }).click();
    await expect(modal(author)).toHaveCount(0);
    expect(await applied(author, conversationId)).toEqual([saved.id]);

    await openDetail(author, resource.revision.name);
    await modal(author).getByRole('button', { name: 'v1 보기', exact: true }).click();
    await modal(author).getByRole('button', { name: '현재 대화에 적용', exact: true }).click();
    await expect(modal(author)).toHaveCount(0);
    expect(await applied(author, conversationId)).toEqual([resource.revision.id]);
    const after = await author.request.get(`/api/resources/${resource.id}`);
    expect((await after.json()).latest_revision_id).toBe(saved.id);
  } finally {
    await Promise.all(contexts.map(context => context.close()));
  }
});

test('a conflicting save preserves its draft while latest content is inspected', async ({ page, testServer }) => {
  const profile = await signIn(page, testServer.codeFor);
  const { resource, conversationId } = await createFixture(page, profile.default_project_id);
  await openDetail(page, resource.revision.name);
  await modal(page).getByRole('button', { name: '수정', exact: true }).click();
  const draft = '진행 중인 초안: 날짜와 URL을 모두 기록한다.';
  await modal(page).getByLabel('지침', { exact: true }).fill(draft);
  const latest = await saveAnotherVersion(page, resource);
  const conflict = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === `/api/resources/${resource.id}/revisions`);
  await modal(page).getByRole('button', { name: '새 버전 저장', exact: true }).click();
  expect((await conflict).status()).toBe(409);
  await expect(modal(page).getByLabel('지침', { exact: true })).toHaveValue(draft);
  await page.screenshot({ path: 'artifacts/b2-conflict-1440.png', fullPage: true });
  await modal(page).getByRole('button', { name: '최신 버전 확인', exact: true }).click();
  await expect(detailView(page)).toContainText(latest.instructions!);
  await modal(page).getByRole('button', { name: '초안으로 돌아가기', exact: true }).click();
  await expect(modal(page).getByLabel('지침', { exact: true })).toHaveValue(draft);
  expect(await applied(page, conversationId)).toEqual([resource.revision.id]);
  const detail = await page.request.get(`/api/resources/${resource.id}`);
  expect((await detail.json()).revisions).toHaveLength(2);
});

test('retrying a lost save response reuses its key and never creates a duplicate revision', async ({ page, testServer }) => {
  const profile = await signIn(page, testServer.codeFor);
  const { resource, conversationId } = await createFixture(page, profile.default_project_id);
  await openDetail(page, resource.revision.name);
  await modal(page).getByRole('button', { name: '수정', exact: true }).click();
  const instructions = '출처와 조사 날짜를 기록하는 새 버전';
  await modal(page).getByLabel('지침', { exact: true }).fill(instructions);
  const keys: string[] = [];
  let committed = false;
  let releaseResponse!: () => void;
  const responseGate = new Promise<void>(resolve => { releaseResponse = resolve; });
  await page.route(`**/api/resources/${resource.id}/revisions`, async route => {
    if (route.request().method() !== 'POST') return route.continue();
    keys.push(route.request().headers()['idempotency-key']);
    if (keys.length !== 1) return route.continue();
    const response = await route.fetch();
    expect(response.ok()).toBe(true);
    committed = true;
    await responseGate;
    await route.abort('connectionreset');
  });
  await modal(page).getByRole('button', { name: '새 버전 저장', exact: true }).click();
  try {
    await expect.poll(() => committed).toBe(true);
    await page.keyboard.press('Escape');
    await expect(modal(page)).toBeVisible();
  } finally {
    releaseResponse();
  }
  await expect(modal(page).getByRole('alert')).toBeVisible();
  await expect(modal(page).getByLabel('지침', { exact: true })).toHaveValue(instructions);
  await modal(page).getByRole('button', { name: '새 버전 저장', exact: true }).click();
  await expect(detailView(page)).toContainText(instructions);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[1]).toBe(keys[0]);
  const response = await page.request.get(`/api/resources/${resource.id}`);
  expect((await response.json()).revisions).toHaveLength(2);
  expect(await applied(page, conversationId)).toEqual([resource.revision.id]);
});

test('a failed file replacement blocks saving and a valid replacement preserves the old version', async ({ page, testServer }) => {
  const profile = await signIn(page, testServer.codeFor);
  const { resource, conversationId } = await createFixture(page, profile.default_project_id, 'file');
  await openDetail(page, resource.revision.name);
  await modal(page).getByRole('button', { name: '수정', exact: true }).click();
  await modal(page).getByLabel('이름', { exact: true }).fill(`${resource.revision.name} 수정`);
  const fileInput = modal(page).getByTestId('revision-file-input');
  await fileInput.setInputFiles({ name: 'replacement.pdf', mimeType: 'application/pdf', buffer: Buffer.from('invalid') });
  await expect(modal(page).getByRole('alert')).toContainText('.md 또는 .txt');
  await expect(modal(page).getByRole('button', { name: '새 버전 저장', exact: true })).toBeDisabled();
  await expect(modal(page).getByLabel('내용', { exact: true })).toHaveValue(resource.revision.content!);
  const newContent = '교체 파일의 내용\n출처와 날짜를 모두 남긴다.';
  await fileInput.setInputFiles({ name: 'replacement.txt', mimeType: 'text/plain', buffer: Buffer.from(newContent, 'utf8') });
  await expect(modal(page).getByLabel('파일 이름', { exact: true })).toHaveValue('replacement.txt');
  await expect(modal(page).getByLabel('내용', { exact: true })).toHaveValue(newContent);
  await modal(page).getByRole('button', { name: '새 버전 저장', exact: true }).click();
  await expect(detailView(page)).toContainText(newContent);
  await expect(detailView(page)).toContainText('replacement.txt');
  expect(await applied(page, conversationId)).toEqual([resource.revision.id]);
  await modal(page).getByRole('button', { name: 'v1 보기', exact: true }).click();
  await expect(detailView(page)).toContainText(resource.revision.content!);
  await expect(detailView(page)).toContainText('original.md');
  const response = await page.request.get(`/api/resources/${resource.id}`);
  const detail: Detail = await response.json();
  expect(detail.revisions).toHaveLength(2);
  expect(detail.revision.file_name).toBe('replacement.txt');
});
