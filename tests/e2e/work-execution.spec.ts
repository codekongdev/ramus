import { randomUUID } from 'node:crypto';
import { test, expect, requestLoginCode, finishLogin } from './fixtures';

test('AI response, automatic tasks, cancellation and retry use the real API worker and SSE', async ({ page, testServer }) => {
  test.setTimeout(45_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  const email = `work-${randomUUID().slice(0, 8)}@example.test`;
  await requestLoginCode(page, email);
  await finishLogin(page, await testServer.codeFor(email));
  await page.getByRole('button', { name: '새 대화', exact: true }).click();
  await page.getByLabel('대화 제목', { exact: true }).fill('실제 실행 흐름 검증');
  await page.getByRole('button', { name: '만들기', exact: true }).click();

  const parent = page.locator('[data-slot="conversation"]');
  await expect(parent.getByRole('heading', { name: '실제 실행 흐름 검증', exact: true })).toBeVisible();
  const composer = parent.getByLabel('메시지', { exact: true });
  await composer.fill('@AI [e2e-answer] 간단하게 답해 주세요.');
  await parent.getByRole('button', { name: '보내기', exact: true }).click();
  const connection = page.getByRole('dialog', { name: 'AI를 사용하려면 연결해 주세요', exact: true });
  await connection.getByLabel('OpenAI API 키', { exact: true }).fill('valid-test-work-execution');
  await connection.getByRole('button', { name: '연결하고 요청 실행', exact: true }).click();
  await expect(parent.getByText('테스트 응답입니다.', { exact: true })).toBeVisible();

  await composer.fill('@AI [e2e-branch] 쿠폰과 장바구니를 나눠서 조사해 주세요.');
  await parent.getByRole('button', { name: '보내기', exact: true }).click();
  await expect(parent.getByText('별도 작업 2개로 나눠 진행합니다.', { exact: true })).toBeVisible();
  const queue = page.locator('[data-slot="task-queue"]');
  const coupon = queue.getByRole('button', { name: /쿠폰 정책 조사/ });
  await expect(coupon).toContainText('준비됨');
  await expect(queue.getByRole('button', { name: /장바구니 검토/ })).toContainText('준비됨');
  await expect(page.getByRole('dialog')).toHaveCount(0);

  const parentUrl = page.url();
  const draft = '작업을 검토하는 동안 유지할 부모 초안';
  await composer.fill(draft);
  await coupon.click();
  const task = page.getByRole('dialog', { name: '쿠폰 정책 조사', exact: true });
  await expect(task.getByText('테스트 작업 응답입니다.', { exact: true })).toHaveCount(1);
  const taskComposer = task.getByLabel('작업 메시지', { exact: true });
  await taskComposer.fill('@AI [e2e-cancel] 예외 조건도 확인해 주세요.');
  await task.getByRole('button', { name: '전송', exact: true }).click();
  await expect(task.getByRole('button', { name: '작업 중단', exact: true })).toBeVisible();
  await task.getByRole('button', { name: '작업 중단', exact: true }).click();
  await expect(task.getByText('작업이 중단되었습니다. 요청자가 다시 시도할 수 있습니다.', { exact: true })).toBeVisible();
  await task.getByRole('button', { name: '작업 다시 시도', exact: true }).click();
  await expect(task.getByText('AI 응답이 준비되었습니다. 대화를 검토하거나 @AI로 보완을 요청하세요.', { exact: true })).toBeVisible();
  await expect(task.getByText('테스트 작업 응답입니다.', { exact: true })).toHaveCount(2);
  await task.getByRole('button', { name: '닫기', exact: true }).click();
  await expect(composer).toHaveValue(draft);
  await expect(page).toHaveURL(parentUrl);
  await expect(coupon).toContainText('준비됨');
  await page.reload();
  await expect(coupon).toContainText('준비됨');
  await coupon.click();
  await expect(task.getByText('테스트 작업 응답입니다.', { exact: true })).toHaveCount(2);
});
