import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../../../src/api/schema';
import { createAiConnectionApi } from '../../../src/features/ai-connection/api';
import { createApiClient } from '../../../src/lib/api';

const signal = () => new AbortController().signal;

function setup(body: unknown, status = 200) {
  const requests: Request[] = [];
  const fetchMock = vi.fn(async (request: Request) => {
    requests.push(request);
    return new Response(body === undefined ? undefined : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  const client = createApiClient<paths>({
    baseUrl: 'http://ramus.test',
    fetch: fetchMock as unknown as typeof fetch,
  });
  return { api: createAiConnectionApi(client), requests };
}

describe('AI connection API boundary', () => {
  it.each(['none', 'connected', 'invalid'] as const)('accepts the %s contract status', async (status) => {
    const { api } = setup({ status });
    expect(await api.read(signal())).toEqual({ ok: true, status: 200, data: { status } });
  });

  it.each([{}, null, [], { status: 'ready' }, { status: false }, { status: null }, undefined])(
    'rejects a malformed successful response: %j', async (body) => {
      const { api } = setup(body);
      expect(await api.read(signal())).toMatchObject({ ok: false, error: { kind: 'system' } });
    },
  );

  it('discards unexpected fields rather than sharing private server data', async () => {
    const { api } = setup({ status: 'connected', api_key: 'test-only-private-key', ciphertext: 'private' });
    expect(await api.read(signal())).toEqual({ ok: true, status: 200, data: { status: 'connected' } });
  });

  it('requires connected after PUT and none after DELETE', async () => {
    const { api: connect } = setup({ status: 'none' });
    expect(await connect.connect('test-only-key', 'request-connect', signal()))
      .toMatchObject({ ok: false, error: { kind: 'system' } });
    const { api: disconnect } = setup({ status: 'connected' });
    expect(await disconnect.disconnect('request-disconnect', signal()))
      .toMatchObject({ ok: false, error: { kind: 'system' } });
  });

  it('sends the key only in the PUT body with explicit action idempotency and session credentials', async () => {
    const { api, requests } = setup({ status: 'connected' });
    await api.connect('test-only-key', 'connect-action', signal());
    const request = requests[0]!;
    expect(request.method).toBe('PUT');
    expect(request.url).toBe('http://ramus.test/api/me/ai-connection');
    expect(request.credentials).toBe('same-origin');
    expect(request.headers.get('Idempotency-Key')).toBe('connect-action');
    expect(request.headers.get('Content-Type')).toBe('application/json');
    expect(await request.json()).toEqual({ api_key: 'test-only-key' });
    expect([...request.headers.values()].join(' ')).not.toContain('test-only-key');
  });

  it('sends a bodyless DELETE with its action idempotency key', async () => {
    const { api, requests } = setup({ status: 'none' });
    await api.disconnect('disconnect-action', signal());
    expect(requests[0]!.method).toBe('DELETE');
    expect(requests[0]!.headers.get('Idempotency-Key')).toBe('disconnect-action');
    expect(await requests[0]!.text()).toBe('');
  });

  it('keeps invalid-key business failures distinct from network failures', async () => {
    const { api } = setup({ error: { code: 'AI_KEY_INVALID', message: 'Check your key.', details: null } }, 422);
    expect(await api.connect('test-only-key', 'connect-action', signal()))
      .toMatchObject({ ok: false, error: { kind: 'business', code: 'AI_KEY_INVALID' } });
    const client = createApiClient<paths>({
      baseUrl: 'http://ramus.test',
      fetch: vi.fn().mockRejectedValue(new TypeError('offline')),
    });
    expect(await createAiConnectionApi(client).read(signal()))
      .toMatchObject({ ok: false, error: { kind: 'network' } });
  });
});
