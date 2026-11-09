import { describe, expect, it, vi } from 'vitest';
import type { components, paths } from '../../../src/api/schema';
import { makeConversationEffectHandler } from '../../../src/features/conversation/effects';
import type { Effect, Intent } from '../../../src/features/conversation/model';
import { createApiClient, SYSTEM_ERROR_MESSAGE } from '../../../src/lib/api';

const date = '2026-11-09T01:00:00Z';
const conversation: components['schemas']['ConversationDetail'] = { id: 'conversation-1', project_id: 'project-1', parent_id: null, task_id: null, title: '멤버십 기획', path: ['멤버십 기획'], created_by: 'author-1', created_at: date, active_run: null };
const message = (seq = 1, overrides: Partial<components['schemas']['Message']> = {}): components['schemas']['Message'] => ({
  id: `message-${seq}`, conversation_id: conversation.id, seq, author: { kind: 'human', account_id: 'author-1', display_name: '서버 작성자' }, body: '  원문\n', requested_by: null, run_id: null, is_example: false, created_at: date, ...overrides,
});
const me = { account: { id: 'author-1', email: 'example@example.test', display_name: '현재 계정' }, ai_connection: { status: 'connected' }, default_project_id: 'project-1' };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const load: Effect = { type: 'load', projectId: 'project-1', conversationId: conversation.id, request: 1 };
const send = (body = '  원문\n'): Effect => ({ type: 'send', conversationId: conversation.id, mutation: { key: 'original-key', body, runVersion: 0 } });
function handler(fetch: typeof globalThis.fetch, ensure?: () => Promise<boolean>) { return makeConversationEffectHandler(createApiClient<paths>({ baseUrl: 'http://localhost', fetch }), ensure); }

async function execute(fetch: typeof globalThis.fetch, effect = load, ensure?: () => Promise<boolean>) {
  const intents: Intent[] = [];
  await handler(fetch, ensure)(effect, value => intents.push(value), new AbortController().signal);
  return intents;
}

describe('conversation effects', () => {
  it('loads all pages by returned cursor, keeps non-contiguous server order and deduplicates overlap', async () => {
    const fetch = vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      if (!url.pathname.endsWith('/messages')) return json(conversation);
      expect(url.searchParams.get('limit')).toBe('200');
      return json(url.searchParams.get('after_seq') === '0'
        ? { items: [message(5), message(2)], next_after_seq: 5 }
        : { items: [message(5), message(9)], next_after_seq: null });
    });
    const intents = await execute(fetch as typeof globalThis.fetch);
    expect(intents[0]).toMatchObject({ type: 'loaded', request: 1, messages: [{ seq: 2 }, { seq: 5 }, { seq: 9 }] });
    expect(fetch.mock.calls).toHaveLength(3);
    expect(fetch.mock.calls.some(([request]) => request.url.includes('/api/me'))).toBe(false);
  });

  it('rejects non-advancing or fabricated cursors, a foreign message and malformed responses', async () => {
    for (const page of [
      { items: [message(1)], next_after_seq: 1 },
      { items: [message(1)], next_after_seq: 3 },
      { items: [message(1, { conversation_id: 'foreign' })], next_after_seq: null },
      { items: [message(1, { created_at: 'invalid' })], next_after_seq: null },
      { items: [{ id: 'incomplete' }], next_after_seq: null },
    ]) {
      const fetch = vi.fn(async (request: Request) => request.url.includes('/messages') ? json(page) : json(conversation));
      expect(await execute(fetch as typeof globalThis.fetch)).toEqual([{ type: 'loadFailed', conversationId: conversation.id, request: 1, message: SYSTEM_ERROR_MESSAGE }]);
    }
  });

  it('rejects conversations belonging to a different project or different active run target', async () => {
    for (const value of [{ ...conversation, project_id: 'other-project' }, { ...conversation, id: 'other' }]) {
      const fetch = vi.fn(async (request: Request) => request.url.includes('/messages') ? json({ items: [], next_after_seq: null }) : json(value));
      expect((await execute(fetch as typeof globalThis.fetch))[0]).toMatchObject({ type: 'loadFailed' });
    }
  });

  it('posts the exact body and action key and trusts the server author without an extra account fetch', async () => {
    const fetch = vi.fn(async (_request: Request) => json({ message: message(8), run: null }));
    const intents = await execute(fetch as typeof globalThis.fetch, send());
    const request = fetch.mock.calls[0]![0];
    expect(request.url).toBe('http://localhost/api/conversations/conversation-1/messages');
    expect(request.headers.get('Idempotency-Key')).toBe('original-key');
    expect(await request.json()).toEqual({ body: '  원문\n' });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(intents[0]).toMatchObject({ type: 'mutationSucceeded', message: { seq: 8, author: { display_name: '서버 작성자' } } });
  });

  it('gates AI sends and resumes the same request only after the connection seam succeeds', async () => {
    const fetch = vi.fn(async (request: Request) => request.url.endsWith('/api/me') ? json({ ...me, ai_connection: { status: 'none' } }) : json({ message: message(), run: null }));
    const failed = await execute(fetch as typeof globalThis.fetch, send('@AI 비교'));
    expect(failed[0]).toMatchObject({ type: 'mutationFailed', message: expect.stringContaining('AI 연결') });
    expect(fetch).toHaveBeenCalledTimes(1);
    fetch.mockClear();
    const cancelled = vi.fn(async () => false);
    await execute(fetch as typeof globalThis.fetch, send('@AI 비교'), cancelled);
    expect(cancelled).toHaveBeenCalledTimes(1);
    expect(fetch).not.toHaveBeenCalled();
    const connected = vi.fn(async () => true);
    const success = await execute(fetch as typeof globalThis.fetch, send('@AI 비교'), connected);
    expect(success[0]).toMatchObject({ type: 'mutationSucceeded', key: 'original-key' });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('keeps business errors, rejects cross-target acknowledgements and silences aborted effects', async () => {
    const fetch = vi.fn(async () => json({ error: { code: 'ACTIVE_RUN_EXISTS', message: 'AI 요청이 진행 중입니다.', details: null } }, 409));
    expect((await execute(fetch as typeof globalThis.fetch, send()))[0]).toMatchObject({ type: 'mutationFailed', message: 'AI 요청이 진행 중입니다.' });
    const foreign = vi.fn(async () => json({ message: message(1, { conversation_id: 'other' }), run: null }));
    expect((await execute(foreign as typeof globalThis.fetch, send()))[0]).toMatchObject({ type: 'mutationFailed', message: SYSTEM_ERROR_MESSAGE });
    const controller = new AbortController();
    const dispatch = vi.fn();
    const late = vi.fn(async () => { controller.abort(); return json({ message: message(), run: null }); });
    await handler(late as typeof globalThis.fetch)(send(), dispatch, controller.signal);
    expect(dispatch).not.toHaveBeenCalled();
    late.mockClear();
    await handler(late as typeof globalThis.fetch)(load, dispatch, controller.signal);
    expect(late).not.toHaveBeenCalled();
  });
});
