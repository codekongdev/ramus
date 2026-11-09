import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../../../src/api/schema';
import { makeProjectsEffects } from '../../../src/features/projects/effects';
import { createApiClient } from '../../../src/lib/api';

const project = { id: 'p1', name: 'Research', is_shared_sample: false };
const operation = { key: 'creation-action', name: project.name };
const signal = () => new AbortController().signal;

function setup(body: unknown, status = 200) {
  const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response(JSON.stringify(body), { status }));
  const navigate = vi.fn();
  const dispatch = vi.fn();
  return { handle: makeProjectsEffects(createApiClient<paths>({ baseUrl: 'http://ramus.test', fetch }), navigate), fetch, navigate, dispatch };
}

describe('project effects', () => {
  it('loads the session-scoped project list', async () => {
    const { handle, fetch, dispatch } = setup({ items: [project] });
    await handle({ type: 'load', generation: 3 }, dispatch, signal());
    expect((fetch.mock.calls[0][0] as Request).url).toBe('http://ramus.test/api/projects');
    expect(dispatch).toHaveBeenCalledWith({ type: 'loaded', generation: 3, items: [project] });
  });

  it('sends the trimmed name and the stable user action key', async () => {
    const { handle, fetch, dispatch, navigate } = setup(project);
    await handle({ type: 'create', operation }, dispatch, signal());
    const request = fetch.mock.calls[0][0] as Request;
    expect(request.method).toBe('POST');
    expect(request.headers.get('Idempotency-Key')).toBe(operation.key);
    expect(await request.json()).toEqual({ name: project.name });
    expect(dispatch).toHaveBeenCalledWith({ type: 'created', key: operation.key, project });
    expect(navigate).not.toHaveBeenCalled();
    await handle({ type: 'navigate', projectId: project.id }, dispatch, signal());
    expect(navigate).toHaveBeenCalledWith(project.id);
  });

  it.each([{}, { ...project, name: 'Different' }, { ...project, is_shared_sample: true }, { ...project, id: null }])('rejects malformed or unrelated creation responses: %j', async body => {
    const { handle, dispatch } = setup(body);
    await handle({ type: 'create', operation }, dispatch, signal());
    expect(dispatch).toHaveBeenCalledWith({ type: 'createFailed', key: operation.key, error: expect.objectContaining({ kind: 'system', status: 502 }) });
  });

  it('returns network failures as retryable result intents', async () => {
    const client = createApiClient<paths>({ baseUrl: 'http://ramus.test', fetch: async () => { throw new TypeError('offline'); } });
    const dispatch = vi.fn();
    await makeProjectsEffects(client, vi.fn())({ type: 'create', operation }, dispatch, signal());
    expect(dispatch).toHaveBeenCalledWith({ type: 'createFailed', key: operation.key, error: expect.objectContaining({ kind: 'network' }) });
  });

  it('does not navigate or call the API after store teardown', async () => {
    const { handle, fetch, navigate, dispatch } = setup(project);
    const controller = new AbortController();
    controller.abort();
    await handle({ type: 'navigate', projectId: project.id }, dispatch, controller.signal);
    await handle({ type: 'create', operation }, dispatch, controller.signal);
    expect(navigate).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
  });
});
