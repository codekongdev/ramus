import { randomUUID } from 'node:crypto';
import type { Page } from '@playwright/test';
import { test, expect, registerAccount } from './fixtures';

const panel = (page: Page) => page.locator('[data-slot="conversation"]');
const log = (page: Page) => panel(page).getByRole('log', { name: '대화 메시지' });

async function send(page: Page, body: string) {
  await panel(page).getByLabel('메시지', { exact: true }).fill(body);
  await panel(page).getByRole('button', { name: '보내기', exact: true }).click();
  await expect(log(page).locator('article').filter({ hasText: body })).toHaveCount(1);
  await expect(panel(page).getByLabel('메시지', { exact: true })).toHaveValue('');
}

test('two accounts create and discuss together, then recover missed SSE messages without losing a draft', async ({ browser, testServer }) => {
  const contexts = await Promise.all(Array.from({ length: 2 }, () => browser.newContext({
    baseURL: testServer.url, viewport: { width: 1440, height: 1000 },
  })));
  try {
    const pages = await Promise.all(contexts.map(context => context.newPage()));
    const [author, teammate] = pages;
    // Retain real native streams. The test closes only one stream to model a dropped
    // connection; all event payloads and subsequent reconnects come from the real API.
    await Promise.all(pages.map(page => page.addInitScript(() => {
      const NativeEventSource = window.EventSource;
      const sources: EventSource[] = [];
      class TrackedEventSource extends NativeEventSource {
        constructor(url: string | URL, options?: EventSourceInit) {
          super(url, options);
          sources.push(this);
        }
      }
      Object.assign(window, { EventSource: TrackedEventSource, a2EventSources: sources });
    })));
    const emails = pages.map((_, index) => `a2-${index}-${randomUUID().slice(0, 8)}@example.test`);
    await Promise.all(pages.map(async (page, index) => {
      await registerAccount(page, emails[index]);
      await page.waitForFunction(() => (window as unknown as { a2EventSources: EventSource[] })
        .a2EventSources.some(source => source.readyState === EventSource.OPEN));
    }));
    const profiles = await Promise.all(pages.map(async page => {
      const response = await page.request.get('/api/me');
      expect(response.ok()).toBe(true);
      return response.json();
    }));
    expect(profiles[0].account.id).not.toBe(profiles[1].account.id);
    expect(profiles[0].default_project_id).toBe(profiles[1].default_project_id);

    await author.getByRole('button', { name: '새 대화', exact: true }).click();
    await author.getByLabel('대화 제목', { exact: true }).fill('멤버십 도입 논의');
    await author.getByRole('button', { name: '만들기', exact: true }).click();
    await expect(panel(author).getByRole('heading', { name: '멤버십 도입 논의' })).toBeVisible();
    const treeEntry = teammate.locator('[data-slot="conversation-tree"]').getByRole('button', { name: '멤버십 도입 논의', exact: true });
    await expect(treeEntry).toBeVisible();
    await treeEntry.click();
    await expect(panel(teammate).getByRole('heading', { name: '멤버십 도입 논의' })).toBeVisible();
    expect(new URL(teammate.url()).pathname).toBe(new URL(author.url()).pathname);
    await Promise.all(pages.map(page => expect(panel(page).getByRole('textbox', { name: '메시지', exact: true })).toHaveCount(1)));

    const firstBody = '멤버십 혜택을 함께 정리해 봅시다.';
    const secondBody = '반품 기준도 확인하겠습니다.';
    await send(author, firstBody);
    const firstSeenByTeammate = log(teammate).locator('article').filter({ hasText: firstBody });
    await expect(firstSeenByTeammate).toHaveCount(1);
    await expect(firstSeenByTeammate).toContainText(profiles[0].account.display_name);
    await send(teammate, secondBody);
    const replySeenByAuthor = log(author).locator('article').filter({ hasText: secondBody });
    await expect(replySeenByAuthor).toHaveCount(1);
    await expect(replySeenByAuthor).toContainText(profiles[1].account.display_name);

    const conversationId = new URL(author.url()).pathname.split('/').at(-1)!;
    const response = await author.request.get(`/api/conversations/${conversationId}/messages?after_seq=0&limit=200`);
    expect(response.ok()).toBe(true);
    const stored = (await response.json()).items;
    expect(stored.map((message: { body: string }) => message.body)).toEqual([firstBody, secondBody]);
    expect(stored.map((message: { author: { account_id: string } }) => message.author.account_id))
      .toEqual(profiles.map(profile => profile.account.id));
    for (const page of pages) {
      await expect(log(page).locator('[data-message-id]')).toHaveCount(2);
      expect(await log(page).locator('[data-message-id]').evaluateAll(elements => elements.map(element => ({
        id: element.getAttribute('data-message-id'), seq: Number(element.getAttribute('data-message-seq')),
      })))).toEqual(stored.map((message: { id: string; seq: number }) => ({ id: message.id, seq: message.seq })));
    }

    const draft = '아직 보내지 않은 팀원의 초안';
    await panel(teammate).getByLabel('메시지', { exact: true }).fill(draft);
    let streamUnavailable = true;
    await teammate.route('**/api/projects/*/events', route => streamUnavailable ? route.abort('connectionfailed') : route.continue());
    await teammate.evaluate(() => {
      const source = (window as unknown as { a2EventSources: EventSource[] }).a2EventSources.at(-1)!;
      const onerror = source.onerror;
      source.close();
      onerror?.call(source, new Event('error'));
    });
    await expect(panel(teammate)).toContainText('다시 연결하는 중입니다.');
    const missedBody = '연결이 끊긴 동안 추가한 논의입니다.';
    await send(author, missedBody);
    await expect(log(teammate).locator('article').filter({ hasText: missedBody })).toHaveCount(0);
    streamUnavailable = false;
    await expect(log(teammate).locator('article').filter({ hasText: missedBody })).toHaveCount(1);
    await expect(panel(teammate).getByLabel('메시지', { exact: true })).toHaveValue(draft);
    await expect(panel(teammate)).not.toContainText('다시 연결하는 중입니다.');
    await expect(log(teammate).locator('[data-message-id]')).toHaveCount(3);
    await author.screenshot({ path: 'artifacts/a2-conversation-1440.png', fullPage: true });

    // A missing connection opens the A3 gate without publishing or clearing the text.
    const aiDraft = '@AI 멤버십 혜택을 정리해 주세요.';
    const aiPostKeys: string[] = [];
    author.on('request', request => {
      if (request.method() === 'POST' && new URL(request.url()).pathname === `/api/conversations/${conversationId}/messages`) {
        aiPostKeys.push(request.headers()['idempotency-key']);
      }
    });
    await panel(author).getByLabel('메시지', { exact: true }).fill(aiDraft);
    await panel(author).getByRole('button', { name: '보내기', exact: true }).click();
    const connection = author.getByRole('dialog', { name: 'AI를 사용하려면 연결해 주세요', exact: true });
    await expect(connection).toBeVisible();
    await expect(connection).toContainText('연결이 끝나면 원래 요청을 실행합니다.');
    await expect(panel(author).getByLabel('메시지', { exact: true })).toHaveValue(aiDraft);
    await connection.getByRole('button', { name: '취소', exact: true }).click();
    await expect(connection).toHaveCount(0);
    await expect(panel(author).getByLabel('메시지', { exact: true })).toHaveValue(aiDraft);
    await expect(log(author).locator('[data-message-id]')).toHaveCount(3);
    expect(aiPostKeys).toHaveLength(0);

    // The fixture injects a synthetic validator; connecting cannot call OpenAI.
    await panel(author).getByRole('button', { name: '보내기', exact: true }).click();
    await expect(connection).toBeVisible();
    await connection.getByLabel('OpenAI API 키', { exact: true }).fill('valid-test-a2');
    await connection.getByRole('button', { name: '연결하고 요청 실행', exact: true }).click();
    await expect(connection).toHaveCount(0);
    await expect(panel(author).getByLabel('메시지', { exact: true })).toHaveValue('');
    await expect(log(author).locator('article').filter({ hasText: aiDraft })).toHaveCount(1);
    await expect(log(teammate).locator('article').filter({ hasText: aiDraft })).toHaveCount(1);
    expect(aiPostKeys).toHaveLength(1);
    expect(aiPostKeys[0]).toBeTruthy();
    const afterConnection = await author.request.get(`/api/conversations/${conversationId}/messages?after_seq=0&limit=200`);
    expect(afterConnection.ok()).toBe(true);
    expect((await afterConnection.json()).items.filter((message: { body: string }) => message.body === aiDraft)).toHaveLength(1);
  } finally {
    await Promise.all(contexts.map(context => context.close()));
  }
});
