import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../src/api/schema';
import { createApiClient, NETWORK_ERROR_MESSAGE, SYSTEM_ERROR_MESSAGE } from '../src/lib/api';
import { makeSendEffectHandler } from '../src/features/sharing/sendEffects';
import { makeReceivedEffectHandler, makeRevisionEffectHandler } from '../src/features/sharing/receivedEffects';
import type { ConversationInput } from '../src/features/sharing/contract';
import { revision } from './results-fixtures';
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const client = (fetch: typeof globalThis.fetch) => createApiClient<paths>({ baseUrl: 'http://localhost', fetch });
const input: ConversationInput = { id: 'input', conversation_id: 'c1', result_id: revision.result_id, result_revision_id: revision.id, version: revision.version, latest_version: 2, title: revision.title, origin: 'share', created_by: 'u1', created_at: revision.created_at };
const snapshot = { ...input, conclusion: revision.conclusion, source: revision.source };
const expectedRevision = { id: revision.id, result_id: revision.result_id, version: revision.version, title: revision.title, conclusion: revision.conclusion, source: revision.source };
const signal = () => new AbortController().signal;
describe('sharing API effects', () => {
  it('searches only the current project with the source excluded and validates response', async () => {
    const fetch = vi.fn(async (_request: Request) => json({ items: [] }));
    const dispatch = vi.fn();
    await makeSendEffectHandler(client(fetch as typeof globalThis.fetch))({ type: 'search', target: { projectId: 'p1', currentConversationId: 'c1', revision }, query: ' 계획 ', request: 1 }, dispatch, signal());
    const url = new URL(fetch.mock.calls[0]![0].url);
    expect(url.pathname).toBe('/api/projects/p1/conversations/search');
    expect(url.searchParams.get('exclude_id')).toBe(revision.source.conversation_id);
    expect(url.searchParams.get('q')).toBe('계획');
    expect(dispatch).toHaveBeenCalledWith({ type: 'matches', request: 1, matches: [] });
  });
  it('sends exact revision and frozen target IDs with stable idempotency, without AI connection or execution', async () => {
    const fetch = vi.fn(async (_request: Request) => json({ items: [{ conversation_id: 'c1', outcome: 'linked' }] }));
    const dispatch = vi.fn();
    await makeSendEffectHandler(client(fetch as typeof globalThis.fetch))({ type: 'send', mutation: { key: 'same-key', revisionId: revision.id, conversationIds: ['c1'] } }, dispatch, signal());
    expect(fetch).toHaveBeenCalledOnce();
    const request = fetch.mock.calls[0]![0];
    expect(request.url).toBe(`http://localhost/api/result-revisions/${revision.id}/shares`);
    expect(request.headers.get('Idempotency-Key')).toBe('same-key');
    expect(await request.json()).toEqual({ conversation_ids: ['c1'] });
    expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'sent', key: 'same-key' }));
  });
  it('rejects incomplete or unrelated outcomes and malformed input payloads, and hides transport details', async () => {
    const dispatch = vi.fn();
    const effect = { type: 'send' as const, mutation: { key: 'key', revisionId: revision.id, conversationIds: ['c1'] } };
    for (const payload of [{ items: [] }, { items: [{ conversation_id: 'other', outcome: 'linked' }] }, { items: [{ conversation_id: 'c1', outcome: 'unexpected' }] }]) {
      await makeSendEffectHandler(client(vi.fn(async () => json(payload))))(effect, dispatch, signal());
      expect(dispatch).toHaveBeenLastCalledWith({ type: 'sendFailed', key: 'key', message: SYSTEM_ERROR_MESSAGE });
    }
    await makeSendEffectHandler(client(vi.fn(async () => { throw new Error('private network detail'); })))(effect, dispatch, signal());
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'sendFailed', key: 'key', message: NETWORK_ERROR_MESSAGE });
    await makeReceivedEffectHandler(client(vi.fn(async () => json({ items: [{ ...input, conversation_id: 'other' }] }))))({ type: 'load', conversationId: 'c1', request: 1 }, dispatch, signal());
    expect(dispatch).toHaveBeenLastCalledWith(expect.objectContaining({ type: 'failed', message: SYSTEM_ERROR_MESSAGE }));
  });
  it('opens exactly the pinned revision with GET only, and rejects a newer returned revision', async () => {
    const fetch = vi.fn(async (_request: Request) => json(snapshot));
    const dispatch = vi.fn();
    await makeRevisionEffectHandler(client(fetch as typeof globalThis.fetch))({ type: 'load', input, request: 1 }, dispatch, signal());
    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch.mock.calls[0]![0].method).toBe('GET');
    expect(fetch.mock.calls[0]![0].url).toBe(`http://localhost/api/conversations/${input.conversation_id}/inputs/${input.id}`);
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'loaded', request: 1, revision: expectedRevision });
    await makeRevisionEffectHandler(client(vi.fn(async () => json({ ...snapshot, version: 2 }))))({ type: 'load', input, request: 2 }, dispatch, signal());
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'failed', request: 2, message: SYSTEM_ERROR_MESSAGE });
  });
});
