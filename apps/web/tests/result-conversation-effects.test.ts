import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../src/api/schema';
import { createApiClient } from '../src/lib/api';
import { makeEffects } from '../src/features/sharing/effects';
import { parent } from './fixtures/tasks';
import { parseConversation } from '../src/lib/api/task-contract';

const operation = { key: 'one-action', projectId: 'p2', revisionId: 'old-revision', title: '후속 기획' };
const conversation = parseConversation({ ...parent, project_id: 'p2', title: operation.title });
const signal = () => new AbortController().signal;
function setup(value: unknown, status = 200) {
  const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response(JSON.stringify(value), { status }));
  const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch });
  const created = vi.fn();
  return { fetch, client, created, handle: makeEffects(client, created), dispatch: vi.fn() };
}
describe('result conversation effects', () => {
  it('searches permission-filtered projects on the server and validates their schema', async () => {
    const test = setup({ items: [{ id: 'p2', name: '후속', is_shared_sample: false }] });
    await test.handle({ type: 'search', request: 2, query: '후속' }, test.dispatch, signal());
    const url = new URL((test.fetch.mock.calls[0][0] as Request).url);
    expect(url.pathname).toBe('/api/projects/search');
    expect(url.searchParams.get('q')).toBe('후속');
    expect(test.dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'loaded', request: 2 }));
    const invalid = setup({ items: [{ id: 'p2' }] });
    await invalid.handle({ type: 'search', request: 1, query: '' }, invalid.dispatch, signal());
    expect(invalid.dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'searchFailed' }));
  });
  it('sends only the pinned revision and title with a stable key and navigates through a separate effect', async () => {
    const test = setup(conversation);
    await test.handle({ type: 'create', operation }, test.dispatch, signal());
    const request = test.fetch.mock.calls[0][0] as Request;
    expect(request.url).toBe('http://localhost/api/projects/p2/conversations/from-result');
    expect(await request.json()).toEqual({ result_revision_id: 'old-revision', title: operation.title });
    expect(request.headers.get('Idempotency-Key')).toBe('one-action');
    expect(test.created).not.toHaveBeenCalled();
    expect(test.dispatch).toHaveBeenCalledWith({ type: 'created', key: 'one-action', conversation });
    await test.handle({ type: 'navigate', conversation }, test.dispatch, signal());
    expect(test.created).toHaveBeenCalledWith(conversation);
  });
  it.each([{}, { ...conversation, project_id: 'wrong' }, { ...conversation, parent_id: 'inherited' }, { ...conversation, task_id: 'task' }, { ...conversation, title: 'wrong' }])('rejects an invalid or unrelated target response %j', async value => {
    const test = setup(value);
    await test.handle({ type: 'create', operation }, test.dispatch, signal());
    expect(test.dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'createFailed' }));
    expect(test.created).not.toHaveBeenCalled();
  });
  it('reports permission changes without navigating, and suppresses work after unmount', async () => {
    const test = setup({ error: { code: 'PROJECT_CREATE_FORBIDDEN', message: '권한 변경', details: null } }, 403);
    await test.handle({ type: 'create', operation }, test.dispatch, signal());
    expect(test.dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'createFailed', error: expect.objectContaining({ code: 'PROJECT_CREATE_FORBIDDEN' }) }));
    const abort = new AbortController();
    abort.abort();
    await test.handle({ type: 'navigate', conversation }, test.dispatch, abort.signal);
    expect(test.created).not.toHaveBeenCalled();
  });
});
