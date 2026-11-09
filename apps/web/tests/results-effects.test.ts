import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../src/api/schema';
import { createApiClient, SYSTEM_ERROR_MESSAGE } from '../src/lib/api';
import { makeResultEffectHandler } from '../src/features/results/effects';
import type { ResultIntent } from '../src/features/results/model';
import { result, revision } from './results-fixtures';
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const handler = (fetch: typeof globalThis.fetch, ensure?: () => Promise<boolean>) => makeResultEffectHandler(createApiClient<paths>({ baseUrl: 'http://localhost', fetch }), ensure);

describe('result effects', () => {
  it('checks the current actor connection and sends one summary with its mutation key', async () => {
    const fetch = vi.fn(async (_request: Request) => json(result));
    const ensure = vi.fn(async () => true);
    const dispatch = vi.fn();
    await handler(fetch as typeof globalThis.fetch, ensure)({ type: 'mutate', taskId: 't1', resultId: null, mutation: { kind: 'summary', key: 'summary-key' } }, dispatch, new AbortController().signal);
    expect(ensure).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledOnce();
    const request = fetch.mock.calls[0]![0];
    expect(request.url).toBe('http://localhost/api/tasks/t1/summaries');
    expect(request.headers.get('Idempotency-Key')).toBe('summary-key');
    expect(await request.json()).toEqual({});
    expect(dispatch).toHaveBeenCalledWith({ type: 'summarySucceeded', taskId: 't1', key: 'summary-key', result });
  });
  it('does not send a summary after connection is cancelled or the task is unmounted', async () => {
    const fetch = vi.fn();
    const dispatch = vi.fn();
    const effect = { type: 'mutate' as const, taskId: 't1', resultId: null, mutation: { kind: 'summary' as const, key: 'summary-key' } };
    await handler(fetch, async () => false)(effect, dispatch, new AbortController().signal);
    expect(fetch).not.toHaveBeenCalled();
    expect(dispatch).toHaveBeenCalledWith({ type: 'mutationCancelled', taskId: 't1', key: 'summary-key' });
    const abort = new AbortController();
    dispatch.mockClear();
    await handler(fetch, async () => { abort.abort(); return true; })(effect, dispatch, abort.signal);
    expect(fetch).not.toHaveBeenCalled();
    expect(dispatch).not.toHaveBeenCalled();
  });
  it('sends the edited conclusion and exact base version without acquiring AI credentials', async () => {
    const fetch = vi.fn(async (_request: Request) => json(revision));
    const ensure = vi.fn();
    const dispatch = vi.fn();
    await handler(fetch as typeof globalThis.fetch, ensure)({ type: 'mutate', taskId: 't1', resultId: 'result1',
      mutation: { kind: 'save', key: 'save-key', baseVersion: 0, sourceRunId: 'summary1', conclusion: '검토한 결론' } }, dispatch, new AbortController().signal);
    expect(ensure).not.toHaveBeenCalled();
    expect(await fetch.mock.calls[0]![0].json()).toEqual({ base_version: 0, source_run_id: 'summary1', conclusion: '검토한 결론' });
    expect(fetch.mock.calls[0]![0].headers.get('Idempotency-Key')).toBe('save-key');
    expect(dispatch).toHaveBeenCalledWith({ type: 'saved', taskId: 't1', key: 'save-key', revision });
  });
  it('distinguishes version conflict and hides system error details', async () => {
    const effect = { type: 'mutate' as const, taskId: 't1', resultId: 'result1', mutation: { kind: 'save' as const, key: 'key', baseVersion: 0, sourceRunId: 'summary1', conclusion: '결론' } };
    const dispatch = vi.fn();
    await handler(vi.fn(async () => json({ error: { code: 'VERSION_CONFLICT', message: '새 버전이 있습니다.', details: null } }, 409)))(effect, dispatch, new AbortController().signal);
    expect(dispatch).toHaveBeenLastCalledWith(expect.objectContaining({ type: 'mutationFailed', conflict: true, message: '새 버전이 있습니다.' }));
    await handler(vi.fn(async () => json({ error: { code: 'INTERNAL_ERROR', message: 'private detail', details: null } }, 500)))(effect, dispatch, new AbortController().signal);
    expect(dispatch).toHaveBeenLastCalledWith(expect.objectContaining({ type: 'mutationFailed', conflict: false, message: SYSTEM_ERROR_MESSAGE }));
  });
  it('loads and validates the latest approved revision and rejects wrong targets or malformed payloads', async () => {
    const intents: ResultIntent[] = [];
    const current = { ...result, latest_revision_id: revision.id, latest_version: 1 };
    const fetch = vi.fn(async (request: Request) => json(request.url.includes('/result-revisions/') ? revision : current));
    const effect = { type: 'load' as const, taskId: 't1', resultId: 'result1', request: 1 };
    await handler(fetch as typeof globalThis.fetch)(effect, intent => intents.push(intent), new AbortController().signal);
    expect(intents[0]).toMatchObject({ type: 'loaded', result: current, approved: revision });
    for (const payload of [{ ...result, source_task_id: 'other' }, { ...result, draft: { ...result.draft, status: 'invalid' } }]) {
      const dispatch = vi.fn();
      await handler(vi.fn(async () => json(payload)))(effect, dispatch, new AbortController().signal);
      expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'loadFailed', message: SYSTEM_ERROR_MESSAGE }));
    }
  });
});
