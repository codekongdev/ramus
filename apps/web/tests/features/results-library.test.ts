import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../../src/api/schema';
import { createApiClient, SYSTEM_ERROR_MESSAGE } from '../../src/lib/api';
import { parseProjectResults, type ProjectResultSummary } from '../../src/features/results-library/contract';
import { makeResultsLibraryEffects } from '../../src/features/results-library/effects';
import { initialResultsLibraryState, resultsLibraryReducer, type ResultsLibraryIntent } from '../../src/features/results-library/model';

const item: ProjectResultSummary = {
  result_id: 'result-1', title: '멤버십 구성안', latest_version: 2, latest_revision_id: 'revision-2',
  source_conversation_title: '서비스 방향', updated_at: '2026-11-09T02:00:00Z',
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});
const client = (fetch: typeof globalThis.fetch) => createApiClient<paths>({ baseUrl: 'http://localhost', fetch });
const load = { type: 'load' as const, projectId: 'project-1', request: 1 };

describe('project results boundary', () => {
  it('accepts saved heads and an empty library', () => {
    expect(parseProjectResults({ items: [item] }).items).toEqual([item]);
    expect(parseProjectResults({ items: [] }).items).toEqual([]);
  });
  it.each([
    { ...item, latest_version: 0 }, { ...item, latest_version: 1.5 },
    { ...item, latest_revision_id: null }, { ...item, updated_at: 'invalid date' },
    { ...item, source_conversation_title: null }, { ...item, result_id: '' },
  ])('rejects a draft or malformed summary: %j', value => {
    expect(() => parseProjectResults({ items: [value] })).toThrow();
  });
  it('rejects duplicate result rows', () => {
    expect(() => parseProjectResults({ items: [item, item] })).toThrow();
  });
});

describe('library invalidation and request ordering', () => {
  it('never replaces a refreshed head with an older in-flight response', () => {
    const initial = initialResultsLibraryState('project-1');
    const first = resultsLibraryReducer(initial, { type: 'refresh' });
    const event = { type: 'result.updated' as const, data: {
      result_id: item.result_id, task_id: 'task-1', draft_status: null, latest_version: 2, occurred_at: item.updated_at,
    } };
    const newer = resultsLibraryReducer(first.state, { type: 'serverEvent', event });
    expect(newer.effects).toEqual([{ type: 'load', projectId: 'project-1', request: 2 }]);
    const ready = resultsLibraryReducer(newer.state, { type: 'loaded', request: 2, items: [item] }).state;
    expect(resultsLibraryReducer(ready, { type: 'loaded', request: 1, items: [] }).state).toBe(ready);
    expect(resultsLibraryReducer(ready, { type: 'failed', request: 1, error: 'late' }).state).toBe(ready);
    expect(ready.items).toEqual([item]);
  });
  it('clears previously visible data after a failed permission recheck', () => {
    const state = { ...initialResultsLibraryState('project-1'), request: 1, status: 'ready' as const, items: [item] };
    const refresh = resultsLibraryReducer(state, { type: 'refresh' }).state;
    expect(refresh.items).toEqual([]);
    const failed = resultsLibraryReducer(refresh, { type: 'failed', request: 2, error: '권한이 없습니다.' }).state;
    expect(failed.status).toBe('failed');
    expect(failed.items).toEqual([]);
  });
});

describe('read-only library effects', () => {
  it('queries only the selected project using the generated client', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => json({ items: [item] }));
    const dispatch = vi.fn();
    await makeResultsLibraryEffects(client(fetch))(load, dispatch, new AbortController().signal);
    const request = fetch.mock.calls[0][0] as Request;
    expect(request.url).toBe('http://localhost/api/projects/project-1/results');
    expect(request.method).toBe('GET');
    expect(dispatch).toHaveBeenCalledExactlyOnceWith({ type: 'loaded', request: 1, items: [item] });
  });
  it('shows business errors and suppresses malformed or private system details', async () => {
    for (const [response, error] of [
      [json({ error: { code: 'FORBIDDEN', message: '접근할 수 없습니다.', details: null } }, 403), '접근할 수 없습니다.'],
      [json({ error: { code: 'INTERNAL_ERROR', message: 'private database detail', details: null } }, 500), SYSTEM_ERROR_MESSAGE],
      [json({ items: [{ ...item, updated_at: 'broken' }] }), SYSTEM_ERROR_MESSAGE],
    ] as const) {
      const dispatch = vi.fn();
      await makeResultsLibraryEffects(client(async () => response))(load, dispatch, new AbortController().signal);
      expect(dispatch).toHaveBeenCalledExactlyOnceWith({ type: 'failed', request: 1, error });
    }
  });
  it('aborts obsolete reads and drops their late responses, including after unmount', async () => {
    const responses: ((response: Response) => void)[] = [];
    const requests: Request[] = [];
    const fetch = vi.fn<typeof globalThis.fetch>(request => {
      requests.push(request as Request);
      return new Promise(resolve => responses.push(resolve));
    });
    const effects = makeResultsLibraryEffects(client(fetch));
    const intents: ResultsLibraryIntent[] = [];
    const dispatch = (intent: ResultsLibraryIntent) => intents.push(intent);
    const lifetime = new AbortController();
    const first = effects(load, dispatch, lifetime.signal);
    await vi.waitFor(() => expect(requests).toHaveLength(1));
    const second = effects({ ...load, request: 2 }, dispatch, lifetime.signal);
    await vi.waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[0].signal.aborted).toBe(true);
    responses[1](json({ items: [item] }));
    await second;
    responses[0](json({ items: [] }));
    await first;
    expect(intents).toEqual([{ type: 'loaded', request: 2, items: [item] }]);
    const third = effects({ ...load, request: 3 }, dispatch, lifetime.signal);
    await vi.waitFor(() => expect(requests).toHaveLength(3));
    lifetime.abort();
    expect(requests[2].signal.aborted).toBe(true);
    responses[2](json({ items: [] }));
    await third;
    expect(intents).toHaveLength(1);
  });
});
