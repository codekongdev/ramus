import { expect, it, vi } from 'vitest';
import type { paths } from '../../../src/api/schema';
import { createApiClient } from '../../../src/lib/api/client';
import { makeEffects } from '../../../src/features/task-navigation/effects';
import { parent, conversation } from '../../fixtures/tasks';

it('creates a top-level conversation with the user action key and validates its response', async () => {
  const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response(JSON.stringify(parent)));
  const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch });
  const dispatch = vi.fn();
  await makeEffects(client)({ type: 'create', projectId: 'p1', title: parent.title, key: 'user-action' }, dispatch, new AbortController().signal);
  const request = fetch.mock.calls[0][0] as Request;
  expect(request.method).toBe('POST');
  expect(request.headers.get('Idempotency-Key')).toBe('user-action');
  expect(await request.json()).toEqual({ title: parent.title });
  expect(dispatch).toHaveBeenCalledWith({ type: 'created', key: 'user-action', conversation: expect.objectContaining({ id: parent.id }) });
});

it('rejects a child task returned from top-level creation and ignores an aborted response', async () => {
  const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch: async () => new Response(JSON.stringify(conversation)) });
  const dispatch = vi.fn();
  const controller = new AbortController();
  await makeEffects(client)({ type: 'create', projectId: 'p1', title: 'new', key: 'new' }, dispatch, controller.signal);
  expect(dispatch).toHaveBeenCalledWith({ type: 'createFailed', key: 'new', error: expect.any(String) });
  dispatch.mockClear();
  controller.abort();
  await makeEffects(client)({ type: 'create', projectId: 'p1', title: 'new', key: 'new' }, dispatch, controller.signal);
  expect(dispatch).not.toHaveBeenCalled();
});
