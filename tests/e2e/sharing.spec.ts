import { randomUUID } from 'node:crypto';
import type { Page } from '@playwright/test';
import type { components } from '../../apps/web/src/api/schema';
import { test, expect, requestLoginCode, finishLogin } from './fixtures';

type S = components['schemas'];
const headers = () => ({ 'Idempotency-Key': randomUUID() });
const received = (page: Page) => page.locator('[data-slot="shared-results"]');

test.use({ viewport: { width: 1440, height: 1000 } });

async function inputs(page: Page, conversationId: string): Promise<S['ConversationInput'][]> {
  const response = await page.request.get(`/api/conversations/${conversationId}/inputs`);
  expect(response.ok()).toBe(true);
  return (await response.json()).items;
}

test('sends a pinned conclusion to multiple conversations, forwards it, and explicitly replaces its version', async ({ page, context, testServer }) => {
  const email = `b6-${randomUUID()}@example.test`;
  await requestLoginCode(page, email);
  await finishLogin(page, await testServer.codeFor(email));
  const identity = await (await page.request.get('/api/me')).json() as S['Me'];
  const projectId = identity.default_project_id;
  const create = async (title: string): Promise<S['Conversation']> => {
    const response = await page.request.post(`/api/projects/${projectId}/conversations`, {
      data: { title }, headers: headers(),
    });
    expect(response.ok()).toBe(true);
    return response.json();
  };
  const prefix = `B6 ${randomUUID().slice(0, 8)}`;
  const source = await create(`${prefix} 조사`);
  const targetA = await create(`${prefix} 통합`);
  const targetB = await create(`${prefix} 정책`);
  const targetC = await create(`${prefix} 상세`);
  const connection = await page.request.put('/api/me/ai-connection', {
    data: { api_key: 'valid-test-b6' }, headers: headers(),
  });
  expect(connection.ok()).toBe(true);
  const requested = await page.request.post(`/api/conversations/${source.id}/messages`, {
    data: { body: '@AI 경쟁사 멤버십 정책을 조사해 주세요.' }, headers: headers(),
  });
  expect(requested.ok()).toBe(true);
  await page.goto(`/projects/${projectId}/conversations/${source.id}`);
  const queue = page.locator('[data-slot="task-queue"]');
  await expect(queue).toContainText('준비됨');
  await queue.getByRole('button', { name: /경쟁사 분석/ }).click();
  const dialog = page.getByRole('dialog', { name: '경쟁사 분석', exact: true });
  await dialog.getByRole('button', { name: '결과 정리', exact: true }).click();
  await expect(dialog.getByLabel('결론', { exact: true })).toHaveValue('테스트 결론입니다.');
  await dialog.getByLabel('결론', { exact: true }).fill('B6에서 승인한 첫 번째 결론');
  const saved = page.waitForResponse(response => response.request().method() === 'POST' && /\/results\/[^/]+\/revisions$/.test(new URL(response.url()).pathname));
  await dialog.getByRole('button', { name: '새 버전 저장', exact: true }).click();
  const revision1 = await (await saved).json() as S['ResultRevision'];
  await expect(dialog.getByRole('button', { name: '다른 대화에 보내기', exact: true })).toBeVisible();

  // Keep a receiver mounted before delivery: this verifies the committed SSE refresh.
  const receiver = await context.newPage();
  await receiver.goto(`${testServer.url}/projects/${projectId}/conversations/${targetA.id}`);
  await expect(receiver.locator('[data-slot="conversation"]').getByRole('heading', { name: targetA.title, exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: '다른 대화에 보내기', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(1);
  await expect(dialog.getByRole('button', { name: '보내기', exact: true })).toBeDisabled();
  await dialog.getByLabel('대화 검색', { exact: true }).fill(prefix);
  const firstTarget = dialog.getByRole('checkbox', { name: targetA.title, exact: false });
  await firstTarget.check();
  await dialog.getByRole('checkbox', { name: targetB.title, exact: false }).check();
  await dialog.getByRole('button', { name: `${targetA.title} 선택 해제`, exact: true }).click();
  await expect(firstTarget).not.toBeChecked();
  await firstTarget.check();
  await dialog.getByRole('button', { name: '보내기', exact: true }).click();
  await expect(dialog.getByRole('button', { name: '다른 대화에 보내기', exact: true })).toBeVisible();
  await expect(dialog).toContainText('B6에서 승인한 첫 번째 결론');
  await expect(page).toHaveURL(new RegExp(`/conversations/${source.id}$`));
  await expect(received(receiver)).toContainText('경쟁사 분석');
  for (const target of [targetA, targetB]) {
    const pinned = (await inputs(page, target.id)).find(input => input.result_id === revision1.result_id);
    expect(pinned?.result_revision_id).toBe(revision1.id);
    const detail = await (await page.request.get(`/api/conversations/${target.id}`)).json() as S['ConversationDetail'];
    expect(detail.active_run).toBeNull();
    const messages = await (await page.request.get(`/api/conversations/${target.id}/messages`)).json() as S['MessageList'];
    expect(messages.items).toHaveLength(0);
  }

  // Opening/closing a received conclusion is read-only; it can be forwarded in the same dialog.
  let receiverMutations = 0;
  receiver.on('request', request => { if (request.method() !== 'GET') receiverMutations++; });
  await received(receiver).getByRole('button', { name: /경쟁사 분석/ }).click();
  const receivedDialog = receiver.getByRole('dialog', { name: revision1.title, exact: true });
  await expect(receivedDialog).toContainText(revision1.conclusion);
  await expect(receivedDialog.getByText('출처 정보', { exact: true })).toHaveCount(0);
  await expect(receivedDialog.getByRole('button', { name: '새 대화 만들기', exact: true })).toBeDisabled();
  const receivedActions = receivedDialog.locator('.conclusion-view__actions button');
  await expect(receivedActions).toHaveCount(2);
  expect(await receivedActions.nth(0).getAttribute('class')).toBe(await receivedActions.nth(1).getAttribute('class'));
  await receivedDialog.getByRole('button', { name: '닫기', exact: true }).click();
  expect(receiverMutations).toBe(0);
  await received(receiver).getByRole('button', { name: /경쟁사 분석/ }).click();
  await receivedDialog.getByRole('button', { name: '다른 대화에 보내기', exact: true }).click();
  await receivedDialog.getByLabel('대화 검색', { exact: true }).fill(prefix);
  await expect(receivedDialog.getByRole('checkbox', { name: targetA.title, exact: false })).toHaveCount(0);
  await receivedDialog.getByRole('checkbox', { name: targetC.title, exact: false }).check();
  await receivedDialog.getByRole('button', { name: '보내기', exact: true }).click();
  await expect(receivedDialog.getByRole('button', { name: '다른 대화에 보내기', exact: true })).toBeVisible();
  expect((await inputs(page, targetC.id)).find(input => input.result_id === revision1.result_id)?.result_revision_id).toBe(revision1.id);
  await receivedDialog.getByRole('button', { name: '닫기', exact: true }).click();

  // A new approval does not update any destination until the sender explicitly sends it again.
  await dialog.getByRole('button', { name: '결론 수정', exact: true }).click();
  await dialog.getByLabel('결론', { exact: true }).fill('B6에서 명시적으로 다시 보낼 두 번째 결론');
  const savedAgain = page.waitForResponse(response => response.request().method() === 'POST' && /\/results\/[^/]+\/revisions$/.test(new URL(response.url()).pathname));
  await dialog.getByRole('button', { name: '새 버전 저장', exact: true }).click();
  const revision2 = await (await savedAgain).json() as S['ResultRevision'];
  await expect(received(receiver)).toContainText('새 버전');
  expect((await inputs(page, targetA.id)).find(input => input.result_id === revision1.result_id)?.result_revision_id).toBe(revision1.id);
  await received(receiver).getByRole('button', { name: /경쟁사 분석/ }).click();
  await expect(receivedDialog).toContainText(revision1.conclusion);
  await expect(receivedDialog).not.toContainText(revision2.conclusion);
  await receivedDialog.getByRole('button', { name: '닫기', exact: true }).click();
  await dialog.getByRole('button', { name: '다른 대화에 보내기', exact: true }).click();
  await dialog.getByLabel('대화 검색', { exact: true }).fill(prefix);
  await dialog.getByRole('checkbox', { name: targetA.title, exact: false }).check();
  await dialog.getByRole('button', { name: '보내기', exact: true }).click();
  await expect(dialog.getByRole('button', { name: '다른 대화에 보내기', exact: true })).toBeVisible();
  await expect.poll(async () => (await inputs(page, targetA.id)).find(input => input.result_id === revision1.result_id)?.result_revision_id).toBe(revision2.id);
  await expect(received(receiver)).not.toContainText('새 버전');

  const older = await page.request.post(`/api/result-revisions/${revision1.id}/shares`, {
    data: { conversation_ids: [targetA.id] }, headers: headers(),
  });
  expect(older.ok()).toBe(true);
  expect((await older.json()).items).toEqual([{ conversation_id: targetA.id, outcome: 'kept_newer' }]);
  expect((await inputs(page, targetB.id)).find(input => input.result_id === revision1.result_id)?.result_revision_id).toBe(revision1.id);
  await receiver.reload();
  await received(receiver).getByRole('button', { name: /경쟁사 분석/ }).click();
  await expect(receivedDialog).toContainText(revision2.conclusion);
  await expect(receiver.getByRole('dialog')).toHaveCount(1);
  await receiver.screenshot({ path: 'artifacts/b6-received-1440.png', fullPage: true });
  await receiver.close();
});
