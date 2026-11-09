import { randomUUID } from 'node:crypto';
import { test, expect, requestLoginCode, finishLogin } from './fixtures';

test('real account API keeps connections private through replacement, refresh, disconnect and account switch', async ({ browser, testServer }) => {
  const contexts = await Promise.all([0, 1].map(() => browser.newContext({ baseURL: testServer.url })));
  try {
    const [first, second] = await Promise.all(contexts.map((context) => context.newPage()));
    for (const page of [first, second]) {
      const email = `ai-${randomUUID().slice(0, 8)}@example.test`;
      await requestLoginCode(page, email);
      await finishLogin(page, await testServer.codeFor(email));
    }
    expect((await first.request.get('/api/me')).ok()).toBe(true);
    expect(await (await second.request.get('/api/me/ai-connection')).json()).toEqual({ status: 'none' });
    const open = () => first.getByRole('button', { name: /^AI 연결/ }).click();
    const dialog = first.getByRole('dialog', { name: 'AI 연결', exact: true });
    await open();
    await dialog.getByLabel('OpenAI API 키', { exact: true }).fill('invalid-test-value');
    await dialog.getByRole('button', { name: '연결하기', exact: true }).click();
    await expect(dialog.getByRole('alert')).toBeVisible();
    await dialog.getByLabel('OpenAI API 키', { exact: true }).fill('valid-test-original');
    await dialog.getByRole('button', { name: '연결하기', exact: true }).click();
    await expect(dialog.getByText('AI가 연결되었습니다.', { exact: true })).toBeVisible();
    expect(await (await first.request.get('/api/me/ai-connection')).json()).toEqual({ status: 'connected' });
    expect(await (await second.request.get('/api/me/ai-connection')).json()).toEqual({ status: 'none' });
    expect((await (await second.request.get('/api/me')).json()).ai_connection).toEqual({ status: 'none' });
    await dialog.getByRole('button', { name: '완료', exact: true }).click();
    await first.reload();
    await open();
    const replacement = dialog.getByLabel('새 OpenAI API 키', { exact: true });
    await expect(replacement).toHaveValue('');
    await replacement.fill('invalid-test-replacement');
    await dialog.getByRole('button', { name: '키 교체', exact: true }).click();
    await expect(dialog.getByRole('alert')).toBeVisible();
    expect(await (await first.request.get('/api/me/ai-connection')).json()).toEqual({ status: 'connected' });
    await replacement.fill('valid-test-replacement');
    await dialog.getByRole('button', { name: '키 교체', exact: true }).click();
    await expect(replacement).toHaveValue('');
    await dialog.getByRole('button', { name: '연결 해제', exact: true }).click();
    await dialog.getByRole('button', { name: '연결 해제', exact: true }).click();
    await expect(dialog.getByText('AI 연결을 해제했습니다.', { exact: true })).toBeVisible();
    expect(await (await first.request.get('/api/me/ai-connection')).json()).toEqual({ status: 'none' });
    await dialog.getByLabel('OpenAI API 키', { exact: true }).fill('valid-test-before-logout');
    await dialog.getByRole('button', { name: '연결하기', exact: true }).click();
    await expect(dialog.getByText('AI가 연결되었습니다.', { exact: true })).toBeVisible();
    await dialog.getByRole('button', { name: '완료', exact: true }).click();
    await first.getByRole('button', { name: '로그아웃', exact: true }).click();
    await expect(first.getByLabel('이메일', { exact: true })).toBeVisible();
    const nextEmail = `ai-next-${randomUUID().slice(0, 8)}@example.test`;
    await requestLoginCode(first, nextEmail);
    await finishLogin(first, await testServer.codeFor(nextEmail));
    await open();
    await expect(dialog.getByLabel('OpenAI API 키', { exact: true })).toHaveValue('');
    expect(await (await first.request.get('/api/me/ai-connection')).json()).toEqual({ status: 'none' });
    expect(await first.evaluate(() => [JSON.stringify(localStorage), JSON.stringify(sessionStorage)])).toEqual(['{}', '{}']);
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
  }
});
