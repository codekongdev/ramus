import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../../../src/api/schema';
import { createApiClient } from '../../../src/lib/api';
import { makeTaskModalEffectHandler } from '../../../src/features/task-modal/effects';
import type { TaskModalIntent } from '../../../src/features/task-modal/model';
import { conversation, me, message, task } from './fixtures';
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const defaultResponse = (request: Request) => request.url.endsWith('/api/me') ? json(me) : request.url.endsWith('/api/tasks/task-1') ? json(task) : request.url.endsWith('/api/conversations/child-1') ? json(conversation) : json({ items: [], next_after_seq: null });
function handler(fetch: typeof globalThis.fetch, ensure?: () => Promise<boolean>) { return makeTaskModalEffectHandler(createApiClient<paths>({ baseUrl: 'http://localhost', fetch }), ensure); }

describe('task modal effects', () => {
  it('loads all child message pages and deduplicates overlapping pages', async () => {
    const fetch = vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      if (url.pathname.endsWith('/messages')) return json(url.searchParams.has('after_seq') ? { items: [message(2), message(3)], next_after_seq: null } : { items: [message(2), message(1)], next_after_seq: 2 });
      return defaultResponse(request);
    });
    const intents: TaskModalIntent[] = [];
    await handler(fetch as typeof globalThis.fetch)({ type: 'load', taskId: task.id, request: 1 }, value => intents.push(value), new AbortController().signal);
    expect(intents[0]).toMatchObject({ type: 'loaded', messages: [{ seq: 1 }, { seq: 2 }, { seq: 3 }] });
    expect(fetch.mock.calls.some(([request]) => request.url.includes('parent-1/messages'))).toBe(false);
  });
  it('rejects a repeated pagination cursor and messages from a different conversation', async () => {
    for (const page of [{ items: [message()], next_after_seq: 1 }, { items: [message(1, { conversation_id: 'parent-1' })], next_after_seq: null }]) {
      const fetch = vi.fn(async (request: Request) => request.url.includes('/messages') ? json(page) : defaultResponse(request));
      const dispatch = vi.fn();
      await handler(fetch as typeof globalThis.fetch)({ type: 'load', taskId: task.id, request: 1 }, dispatch, new AbortController().signal);
      expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'loadFailed' }));
    }
  });
  it('preserves the idempotency key and targets the child for message submission', async () => {
    const fetch = vi.fn(async (_request: Request) => json({ message: message(2), run: null }));
    const dispatch = vi.fn();
    await handler(fetch as typeof globalThis.fetch)({ type: 'mutate', task, mutation: { kind: 'send', key: 'same-action', body: '검토 요청' } }, dispatch, new AbortController().signal);
    const request = fetch.mock.calls[0]![0] as unknown as Request;
    expect(request.url).toBe('http://localhost/api/conversations/child-1/messages');
    expect(request.headers.get('Idempotency-Key')).toBe('same-action');
    expect(await request.json()).toEqual({ body: '검토 요청' });
    expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'mutationSucceeded' }));
  });
  it('does not store an AI message without a connection and reports cancellation of connection UI', async () => {
    const fetch = vi.fn(async () => json({ ...me, ai_connection: { status: 'none' } }));
    const dispatch = vi.fn();
    await handler(fetch as typeof globalThis.fetch)({ type: 'mutate', task, mutation: { kind: 'send', key: 'k', body: '@AI 보완' } }, dispatch, new AbortController().signal);
    expect(fetch.mock.calls).toHaveLength(1);
    expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'mutationFailed', message: expect.stringContaining('AI 연결') }));
    const ensure = vi.fn(async () => false);
    fetch.mockClear();
    await handler(fetch as typeof globalThis.fetch, ensure)({ type: 'mutate', task, mutation: { kind: 'retry', key: 'k' } }, dispatch, new AbortController().signal);
    expect(ensure).toHaveBeenCalledTimes(1);
    expect(fetch).not.toHaveBeenCalled();
  });
  it('surfaces server business errors and discards results after unmount', async () => {
    const fetch = vi.fn(async () => json({ error: { code: 'ACTIVE_RUN_EXISTS', message: '다른 요청이 진행 중입니다.', details: null } }, 409));
    const dispatch = vi.fn();
    await handler(fetch as typeof globalThis.fetch)({ type: 'mutate', task, mutation: { kind: 'send', key: 'k', body: '논의' } }, dispatch, new AbortController().signal);
    expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'mutationFailed', message: '다른 요청이 진행 중입니다.' }));
    const controller = new AbortController();
    controller.abort();
    dispatch.mockClear();
    await handler(fetch as typeof globalThis.fetch)({ type: 'load', taskId: task.id, request: 1 }, dispatch, controller.signal);
    expect(dispatch).not.toHaveBeenCalled();
  });
});
