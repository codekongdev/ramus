import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../src/api/schema';
import { createApiClient, SYSTEM_ERROR_MESSAGE } from '../src/lib/api';
import { parseInputDetail, type InputDetail } from '../src/features/sharing/contract';
import { initialRevisionState, revisionReducer } from '../src/features/sharing/receivedModel';
import { makeRevisionEffectHandler } from '../src/features/sharing/receivedEffects';
import { revision } from './results-fixtures';

const detail: InputDetail = {
  id: 'input1', conversation_id: 'c1', result_id: revision.result_id, result_revision_id: revision.id,
  title: revision.title, conclusion: revision.conclusion, source: revision.source, version: 1,
  latest_version: 1, origin: 'new_conversation', created_by: 'u1', created_at: revision.created_at,
};
describe('received conclusion snapshot', () => {
  it('opening is read-only and ignores stale reads', () => {
    const loading = revisionReducer(initialRevisionState(detail), { type: 'refresh' });
    expect(loading.effects).toEqual([{ type: 'load', input: detail, request: 1 }]);
    expect(revisionReducer(loading.state, { type: 'loaded', request: 0, revision }).state).toBe(loading.state);
    const loaded = revisionReducer(loading.state, { type: 'loaded', request: 1, revision });
    expect(loaded.effects).toEqual([]);
    expect(loaded.state.revision?.id).toBe(detail.result_revision_id);
  });
  it('validates all snapshot fields and the exact input identity', () => {
    expect(parseInputDetail(detail, 'c1', detail.id)).toEqual(detail);
    for (const value of [{}, { ...detail, id: 'other' }, { ...detail, conversation_id: 'other' }, { ...detail, conclusion: null }, { ...detail, source: {} }]) {
      expect(() => parseInputDetail(value, 'c1', detail.id)).toThrow();
    }
  });
  it('rejects a replaced input instead of silently opening another revision', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response(JSON.stringify({ ...detail, result_revision_id: 'newer', version: 2, latest_version: 2 }), { status: 200 }));
    const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch });
    const dispatch = vi.fn();
    await makeRevisionEffectHandler(client)({ type: 'load', input: detail, request: 1 }, dispatch, new AbortController().signal);
    expect(dispatch).toHaveBeenCalledWith({ type: 'failed', request: 1, message: SYSTEM_ERROR_MESSAGE });
    expect(fetch).toHaveBeenCalledOnce();
    expect((fetch.mock.calls[0][0] as Request).url).toBe('http://localhost/api/conversations/c1/inputs/input1');
  });
  it('handles revoked access without opening the source or navigating', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: '접근할 수 없습니다.', details: null } }), { status: 404 }));
    const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch });
    const dispatch = vi.fn();
    await makeRevisionEffectHandler(client)({ type: 'load', input: detail, request: 1 }, dispatch, new AbortController().signal);
    expect(dispatch).toHaveBeenCalledWith({ type: 'failed', request: 1, message: '접근할 수 없습니다.' });
    expect(fetch).toHaveBeenCalledOnce();
  });
});
