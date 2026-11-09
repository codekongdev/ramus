import { describe, expect, it, vi } from 'vitest';
import {
  IDEMPOTENCY_HEADER,
  createApiClient,
  isConflict,
  isUnauthorized,
  readErrorBody,
  toHttpError,
  toResult,
} from '../../src/lib/api';

// Test-only stand-in for the generated `paths` (P0-A3 will provide the real one).
interface TestPaths {
  '/api/items/{id}': {
    parameters: { path: { id: string } };
    get: {
      parameters: { path: { id: string } };
      responses: {
        200: { content: { 'application/json': { id: string; title: string } } };
        404: { content: { 'application/json': { detail: string } } };
      };
    };
  };
  '/api/items': {
    post: {
      requestBody: { content: { 'application/json': { title: string } } };
      responses: {
        201: { content: { 'application/json': { id: string } } };
        409: { content: { 'application/json': { error: { code: string; message: string } } } };
      };
    };
  };
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

function setup(response: () => Response | Promise<Response>) {
  const requests: Request[] = [];
  const fetchMock = vi.fn(async (input: Request) => {
    requests.push(input);
    return response();
  });
  let counter = 0;
  const api = createApiClient<TestPaths>({
    baseUrl: 'http://ramus.test',
    fetch: fetchMock as unknown as typeof fetch,
    newIdempotencyKey: () => `key-${++counter}`,
  });
  return { api, requests };
}

describe('createApiClient', () => {
  it('adds a fresh Idempotency-Key to mutating requests', async () => {
    const { api, requests } = setup(() => json(201, { id: 'i1' }));
    await api.POST('/api/items', { body: { title: 'a' } });
    await api.POST('/api/items', { body: { title: 'b' } });
    expect(requests.map((r) => r.headers.get(IDEMPOTENCY_HEADER))).toEqual(['key-1', 'key-2']);
  });

  it('keeps a caller-supplied key so retries reuse it', async () => {
    const { api, requests } = setup(() => json(201, { id: 'i1' }));
    await api.POST('/api/items', { body: { title: 'a' }, headers: { [IDEMPOTENCY_HEADER]: 'retry-1' } });
    await api.POST('/api/items', { body: { title: 'a' }, headers: { [IDEMPOTENCY_HEADER]: 'retry-1' } });
    expect(requests.map((r) => r.headers.get(IDEMPOTENCY_HEADER))).toEqual(['retry-1', 'retry-1']);
  });

  it('does not add a key to reads', async () => {
    const { api, requests } = setup(() => json(200, { id: 'i1', title: 't' }));
    await api.GET('/api/items/{id}', { params: { path: { id: 'i1' } } });
    expect(requests[0]!.headers.has(IDEMPOTENCY_HEADER)).toBe(false);
    expect(requests[0]!.url).toBe('http://ramus.test/api/items/i1');
    expect(requests[0]!.credentials).toBe('same-origin');
  });
});

describe('toResult', () => {
  it('returns data on success', async () => {
    const { api } = setup(() => json(200, { id: 'i1', title: 't' }));
    const result = await toResult(api.GET('/api/items/{id}', { params: { path: { id: 'i1' } } }));
    expect(result).toEqual({ ok: true, status: 200, data: { id: 'i1', title: 't' } });
  });

  it('maps 4xx to a business error with code and message', async () => {
    const { api } = setup(() => json(409, { error: { code: 'stale_revision', message: '다른 버전이 먼저 저장됐습니다' } }));
    const result = await toResult(api.POST('/api/items', { body: { title: 'a' } }));
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error).toMatchObject({
      kind: 'business',
      status: 409,
      code: 'stale_revision',
      message: '다른 버전이 먼저 저장됐습니다',
    });
    expect(isConflict(result.error)).toBe(true);
  });

  it('maps 5xx to a system error', async () => {
    const { api } = setup(() => json(503, { detail: 'down' }));
    const result = await toResult(api.GET('/api/items/{id}', { params: { path: { id: 'x' } } }));
    expect(result).toMatchObject({ ok: false, error: { kind: 'system', status: 503, message: 'down' } });
  });

  it('maps a thrown fetch to a network error', async () => {
    const { api } = setup(() => {
      throw new TypeError('Failed to fetch');
    });
    const result = await toResult(api.GET('/api/items/{id}', { params: { path: { id: 'x' } } }));
    expect(result).toMatchObject({ ok: false, error: { kind: 'network' } });
  });

  it('maps an aborted request to aborted', async () => {
    const { api } = setup(() => {
      throw new DOMException('aborted', 'AbortError');
    });
    const result = await toResult(api.GET('/api/items/{id}', { params: { path: { id: 'x' } } }));
    expect(result).toEqual({ ok: false, error: { kind: 'aborted' } });
  });
});

describe('error helpers', () => {
  it('reads the supported error body shapes', () => {
    expect(readErrorBody({ error: { code: 'c', message: 'm' } })).toEqual({ code: 'c', message: 'm' });
    expect(readErrorBody({ code: 'c', message: 'm' })).toEqual({ code: 'c', message: 'm' });
    expect(readErrorBody({ detail: 'd' })).toEqual({ code: null, message: 'd' });
    expect(readErrorBody({ detail: [{ msg: 'x' }] })).toEqual({ code: null, message: null });
    expect(readErrorBody('oops')).toEqual({ code: null, message: null });
    expect(readErrorBody(undefined)).toEqual({ code: null, message: null });
  });

  it('classifies status helpers', () => {
    expect(isUnauthorized(toHttpError(401, null))).toBe(true);
    expect(isConflict(toHttpError(401, null))).toBe(false);
    expect(isConflict(toHttpError(500, null))).toBe(false);
  });
});
