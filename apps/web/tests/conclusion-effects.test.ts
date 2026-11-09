import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../src/api/schema';
import { createApiClient, NETWORK_ERROR_MESSAGE, SYSTEM_ERROR_MESSAGE } from '../src/lib/api';
import { makeConclusionEffectHandler } from '../src/features/results/conclusionEffects';
import { revision } from './results-fixtures';

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});
const handler = (fetch: typeof globalThis.fetch) => makeConclusionEffectHandler(
  createApiClient<paths>({ baseUrl: 'http://localhost', fetch }),
);
const effect = { type: 'load' as const, revisionId: revision.id, request: 1 };

describe('conclusion reader effects', () => {
  it('performs one GET for the exact revision without starting any mutation or AI request', async () => {
    const fetch = vi.fn(async (_request: Request) => json(revision));
    const dispatch = vi.fn();
    await handler(fetch as typeof globalThis.fetch)(effect, dispatch, new AbortController().signal);
    expect(fetch).toHaveBeenCalledOnce();
    const request = fetch.mock.calls[0][0];
    expect(request.url).toBe(`http://localhost/api/result-revisions/${revision.id}`);
    expect(request.method).toBe('GET');
    expect(request.headers.has('Idempotency-Key')).toBe(false);
    expect(dispatch).toHaveBeenCalledWith({ type: 'loaded', revisionId: revision.id, request: 1, revision });
  });

  it('rejects mismatched ids and malformed payloads instead of showing another conclusion', async () => {
    for (const payload of [
      { ...revision, id: 'another-revision' },
      { ...revision, conclusion: null },
      { ...revision, source: { ...revision.source, resource_revision_ids: 'invalid' } },
    ]) {
      const dispatch = vi.fn();
      await handler(vi.fn(async () => json(payload)))(effect, dispatch, new AbortController().signal);
      expect(dispatch).toHaveBeenCalledOnce();
      expect(dispatch).toHaveBeenCalledWith({
        type: 'failed', revisionId: revision.id, request: 1, message: SYSTEM_ERROR_MESSAGE,
      });
    }
  });

  it('shows business errors but hides system details and uses the common network message', async () => {
    const dispatch = vi.fn();
    await handler(vi.fn(async () => json({ error: {
      code: 'NOT_FOUND', message: '결론을 찾을 수 없습니다.', details: null,
    } }, 404)))(effect, dispatch, new AbortController().signal);
    expect(dispatch).toHaveBeenLastCalledWith({
      type: 'failed', revisionId: revision.id, request: 1, message: '결론을 찾을 수 없습니다.',
    });
    await handler(vi.fn(async () => json({ error: {
      code: 'INTERNAL_ERROR', message: 'private server detail', details: null,
    } }, 500)))(effect, dispatch, new AbortController().signal);
    expect(dispatch).toHaveBeenLastCalledWith({
      type: 'failed', revisionId: revision.id, request: 1, message: SYSTEM_ERROR_MESSAGE,
    });
    await handler(vi.fn(async () => { throw new Error('private connection detail'); }))(
      effect, dispatch, new AbortController().signal,
    );
    expect(dispatch).toHaveBeenLastCalledWith({
      type: 'failed', revisionId: revision.id, request: 1, message: NETWORK_ERROR_MESSAGE,
    });
  });

  it('drops a late success or error after the reader closes', async () => {
    for (const fail of [false, true]) {
      const abort = new AbortController();
      const dispatch = vi.fn();
      const fetch = vi.fn(async () => {
        abort.abort();
        if (fail) throw new Error('late failure');
        return json(revision);
      });
      await handler(fetch)(effect, dispatch, abort.signal);
      expect(dispatch).not.toHaveBeenCalled();
    }
  });
});
