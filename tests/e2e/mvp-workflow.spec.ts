import { randomUUID } from 'node:crypto';
import type { Page } from '@playwright/test';
import type { components } from '../../apps/web/src/api/schema';
import { test, expect, registerAccount } from './fixtures';

type S = components['schemas'];
const headers = () => ({ 'Idempotency-Key': randomUUID() });

async function post<T>(page: Page, path: string, data: unknown): Promise<T> {
  const response = await page.request.post(path, { data, headers: headers() });
  expect(response.ok(), path).toBe(true);
  return response.json();
}

async function get<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), path).toBe(true);
  return response.json();
}

function savedRevision(page: Page) {
  return page.waitForResponse(response => response.request().method() === 'POST'
    && /^\/api\/results\/[^/]+\/revisions$/.test(new URL(response.url()).pathname));
}

test('applied resources flow through branching, pinned sharing, another AI request, followup creation and the relationship map', async ({ page, context, testServer }) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  const suffix = randomUUID().slice(0, 8);
  const email = `mvp-${suffix}@example.test`;
  await registerAccount(page, email);
  const project = await post<S['Project']>(page, '/api/projects', { name: `MVP 연결 검증 ${suffix}` });
  const source = await post<S['Conversation']>(page, `/api/projects/${project.id}/conversations`, { title: '멤버십 공동 검토' });
  const resource = await post<S['ResourceDetail']>(page, `/api/projects/${project.id}/resources`, {
    kind: 'skill', name: `검토 기준 ${suffix}`, description: '공동 조사에서 고정할 기준', instructions: '혜택과 반품 예외의 근거를 확인한다.',
  });
  expect((await page.request.put('/api/me/ai-connection', {
    data: { api_key: 'valid-test-mvp-workflow' }, headers: headers(),
  })).ok()).toBe(true);
  await page.goto(`/projects/${project.id}/conversations/${source.id}`);

  // Apply through the product UI; a newer resource must not silently change either child.
  await page.getByRole('button', { name: '스킬·자료', exact: true }).click();
  const resources = page.getByRole('dialog', { name: '스킬·자료', exact: true });
  await resources.getByLabel('스킬·자료 검색', { exact: true }).fill(resource.revision.name);
  await resources.locator(`[data-resource-id="${resource.id}"]`).getByRole('checkbox').check();
  await resources.getByRole('button', { name: '적용', exact: true }).click();
  await expect(resources).toHaveCount(0);
  const newerResource = await post<S['CreateResourceRevisionResponse']>(page, `/api/resources/${resource.id}/revisions`, {
    base_revision_id: resource.revision.id, name: resource.revision.name,
    description: '아직 적용하지 않은 새 기준', instructions: '새 기준은 명시적으로 적용한 대화에서만 사용한다.',
  });
  expect(newerResource.revision.number).toBe(2);

  const conversation = page.locator('[data-slot="conversation"]');
  await conversation.getByLabel('메시지', { exact: true }).fill('@AI [e2e-branch] 쿠폰과 장바구니를 나눠 조사해 주세요.');
  await conversation.getByRole('button', { name: '보내기', exact: true }).click();
  const queue = page.locator('[data-slot="task-queue"]');
  await expect(queue.getByRole('button', { name: /쿠폰 정책 조사/ })).toContainText('준비됨');
  await expect(queue.getByRole('button', { name: /장바구니 검토/ })).toContainText('준비됨');
  const tasks = await get<S['TaskList']>(page, `/api/conversations/${source.id}/tasks`);
  const coupon = tasks.items.find(task => task.title === '쿠폰 정책 조사')!;
  const cart = tasks.items.find(task => task.title === '장바구니 검토')!;
  for (const task of [coupon, cart]) {
    const applied = await get<S['AppliedResourceList']>(page, `/api/conversations/${task.child_conversation_id}/resources`);
    expect(applied.items.map(item => item.revision_id)).toEqual([resource.revision.id]);
  }

  await queue.getByRole('button', { name: /쿠폰 정책 조사/ }).click();
  const taskDialog = page.getByRole('dialog', { name: coupon.title, exact: true });
  await taskDialog.getByRole('button', { name: '결과 정리', exact: true }).click();
  await expect(taskDialog.getByLabel('결론', { exact: true })).toHaveValue('테스트 결론입니다.');
  await taskDialog.getByLabel('결론', { exact: true }).fill('쿠폰과 반품 예외를 함께 안내하는 첫 번째 승인 결론');
  const firstSave = savedRevision(page);
  await taskDialog.getByRole('button', { name: '새 버전 저장', exact: true }).click();
  const firstResponse = await firstSave;
  expect(firstResponse.ok()).toBe(true);
  const first = await firstResponse.json() as S['ResultRevision'];
  expect(first.source.resource_revision_ids).toEqual([resource.revision.id]);
  expect(first.source.input_result_revision_ids).toEqual([]);

  // Keep the recipient mounted before sharing so this also checks committed SSE refresh.
  const receiver = await context.newPage();
  await receiver.setViewportSize({ width: 1440, height: 1000 });
  await receiver.goto(`${testServer.url}/projects/${project.id}/conversations/${cart.child_conversation_id}`);
  await expect(receiver.locator('[data-slot="conversation"]').getByRole('heading', { name: cart.title, exact: true })).toBeVisible();
  const linked = receiver.getByRole('region', { name: '연결된 결론', exact: true });
  await expect(linked).toContainText('공유받은 결과가 없습니다.');
  await expect(linked.getByRole('button')).toHaveCount(0);
  await taskDialog.getByRole('button', { name: '다른 대화에 보내기', exact: true }).click();
  await taskDialog.getByLabel('대화 검색', { exact: true }).fill(cart.title);
  await taskDialog.getByRole('checkbox', { name: cart.title, exact: false }).check();
  await taskDialog.getByRole('button', { name: '보내기', exact: true }).click();
  const receivedButton = linked.getByRole('button', { name: `${first.title} v1 결론 보기`, exact: true });
  await expect(receivedButton).toBeVisible();
  const latest = await post<S['ResultRevision']>(page, `/api/results/${first.result_id}/revisions`, {
    base_version: 1, source_run_id: first.source.run_id, conclusion: '공유 이후 승인한 두 번째 결론',
  });
  await expect(linked).toContainText('새 버전');
  const pinned = await get<S['ConversationInputList']>(receiver, `/api/conversations/${cart.child_conversation_id}/inputs`);
  expect(pinned.items.map(item => item.result_revision_id)).toEqual([first.id]);
  await receivedButton.click();
  const receivedDialog = receiver.getByRole('dialog', { name: first.title, exact: true });
  await expect(receivedDialog).toContainText(first.conclusion);
  await expect(receivedDialog).not.toContainText(latest.conclusion);
  await receivedDialog.getByRole('button', { name: '닫기', exact: true }).click();

  // Follow the shared input through a real child run and a new summary snapshot.
  const receivingConversation = receiver.locator('[data-slot="conversation"]');
  await receivingConversation.getByLabel('메시지', { exact: true }).fill('@AI 받은 첫 번째 결론을 장바구니 정책에 반영해 주세요.');
  await receivingConversation.getByRole('button', { name: '보내기', exact: true }).click();
  await expect(receivingConversation.getByText('테스트 작업 응답입니다.', { exact: true })).toHaveCount(2);
  await receiver.getByRole('button', { name: '프로젝트 구조', exact: true }).click();
  await receiver.getByRole('region', { name: '프로젝트 관계 지도', exact: true }).getByRole('button', { name: /장바구니 검토/ }).click();
  const cartDialog = receiver.getByRole('dialog', { name: cart.title, exact: true });
  await cartDialog.getByRole('button', { name: '결과 정리', exact: true }).click();
  await expect(cartDialog.getByLabel('결론', { exact: true })).toHaveValue('테스트 결론입니다.');
  await cartDialog.getByLabel('결론', { exact: true }).fill('받은 쿠폰 결론과 고정 업무 기준을 반영한 장바구니 구성안');
  const combinedSave = savedRevision(receiver);
  await cartDialog.getByRole('button', { name: '새 버전 저장', exact: true }).click();
  const combinedResponse = await combinedSave;
  expect(combinedResponse.ok()).toBe(true);
  const combined = await combinedResponse.json() as S['ResultRevision'];
  expect(combined.source.resource_revision_ids).toEqual([resource.revision.id]);
  expect(combined.source.input_result_revision_ids).toEqual([first.id]);

  await cartDialog.getByRole('button', { name: '새 대화 만들기', exact: true }).click();
  const creation = receiver.getByRole('dialog');
  await creation.getByLabel('프로젝트 검색', { exact: true }).fill(project.name);
  await creation.getByRole('button', { name: `${project.name} 선택`, exact: true }).click();
  const followupTitle = '장바구니 상세 기획';
  await creation.getByLabel('대화 제목', { exact: true }).fill(followupTitle);
  await creation.getByRole('button', { name: '만들기', exact: true }).click();
  await expect(receiver.getByRole('dialog')).toHaveCount(0);
  await expect(receiver.locator('[data-slot="conversation"]').getByRole('heading', { name: followupTitle, exact: true })).toBeVisible();
  const followupId = new URL(receiver.url()).pathname.split('/').at(-1)!;
  const followup = await get<S['ConversationDetail']>(receiver, `/api/conversations/${followupId}`);
  expect(followup).toMatchObject({ project_id: project.id, parent_id: null, task_id: null, active_run: null });
  const followupInputs = await get<S['ConversationInputList']>(receiver, `/api/conversations/${followupId}/inputs`);
  expect(followupInputs.items).toHaveLength(1);
  expect(followupInputs.items[0]).toMatchObject({ result_revision_id: combined.id, version: 1, origin: 'new_conversation' });
  expect((await get<S['MessageList']>(receiver, `/api/conversations/${followupId}/messages`)).items).toEqual([]);
  expect((await get<S['AppliedResourceList']>(receiver, `/api/conversations/${followupId}/resources`)).items).toEqual([]);

  await receiver.reload();
  await expect(receiver.getByRole('region', { name: '연결된 결론', exact: true })).toContainText(cart.title);
  await receiver.getByRole('button', { name: '결과물', exact: true }).click();
  const library = receiver.getByRole('dialog', { name: '결과물', exact: true });
  await expect(library.locator(`[data-result-id="${first.result_id}"]`)).toContainText('v2');
  await expect(library.locator(`[data-result-id="${combined.result_id}"]`)).toContainText('v1');
  await expect(library.getByRole('listitem')).toHaveCount(2);
  await library.getByRole('button', { name: '닫기', exact: true }).click();
  await receiver.getByRole('button', { name: '프로젝트 구조', exact: true }).click();
  const graph = receiver.getByRole('dialog', { name: '프로젝트 구조', exact: true });
  await expect(graph.locator('svg line')).toHaveCount(2);
  await expect(graph.locator('svg path.is-dashed')).toHaveCount(2);
  await graph.getByText('관계 텍스트로 보기', { exact: true }).click();
  await expect(graph).toContainText(`${source.title} → ${coupon.title}: 분기`);
  await expect(graph).toContainText(`${source.title} → ${cart.title}: 분기`);
  await expect(graph).toContainText(`${coupon.title} → ${cart.title}: 결론 사용`);
  await expect(graph).toContainText(`${cart.title} → ${followupTitle}: 결론 사용`);
  await receiver.close();
});
