import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../../src/api/schema';
import { createApiClient, type ApiError } from '../../src/lib/api';
import { makePasswordSetupEffects } from '../../src/features/auth/passwordSetupEffects';
import { initialPasswordSetupState, passwordSetupReducer as reduce, type PasswordSetupState } from '../../src/features/auth/passwordSetupModel';

const secret = 'Synthetic-setup-passphrase';
const network: ApiError = { kind: 'network', cause: new TypeError('offline') };
const http = (status: number, code: string): ApiError => ({ kind: 'business', status, code, message: 'Failure', details: null });
function missingPassword(): PasswordSetupState {
  const loading = reduce(initialPasswordSetupState, { type: 'load' }).state;
  return reduce(loading, { type: 'loaded', request: loading.statusRequest, configured: false }).state;
}
function filled(): PasswordSetupState {
  const opened = reduce(missingPassword(), { type: 'open' }).state;
  const password = reduce(opened, { type: 'fieldChanged', field: 'password', value: secret }).state;
  return reduce(password, { type: 'fieldChanged', field: 'confirmation', value: secret }).state;
}

describe('initial password setup reducer', () => {
  it('checks status once and refuses to open a configured account', () => {
    const loading = reduce(initialPasswordSetupState, { type: 'load' });
    expect(loading.effects).toEqual([{ type: 'load', request: 1 }]);
    expect(reduce(loading.state, { type: 'load' }).effects).toEqual([]);
    const ready = reduce(loading.state, { type: 'loaded', request: 1, configured: true }).state;
    expect(reduce(ready, { type: 'open' }).state).toBe(ready);
    expect(reduce(initialPasswordSetupState, { type: 'open' }).state).toBe(initialPasswordSetupState);
  });
  it('reports load failures and ignores earlier status responses after retry', () => {
    const loading = reduce(initialPasswordSetupState, { type: 'load' }).state;
    const failed = reduce(loading, { type: 'loadFailed', request: 1, error: network }).state;
    expect(failed.status).toBe('failed');
    const retry = reduce(failed, { type: 'load' });
    expect(retry.effects).toEqual([{ type: 'load', request: 2 }]);
    expect(reduce(retry.state, { type: 'loaded', request: 1, configured: true }).state).toBe(retry.state);
  });
  it('validates the password length and confirmation before sending', () => {
    const state = reduce(filled(), { type: 'fieldChanged', field: 'password', value: 'short' }).state;
    const invalid = reduce(state, { type: 'save', key: 'invalid' });
    expect(invalid.effects).toEqual([]);
    expect(invalid.state.passwordError).toBeTruthy();
    expect(invalid.state.confirmationError).toBeTruthy();
  });
  it('uses the same key and password for an uncertain retry and blocks double submission', () => {
    const first = reduce(filled(), { type: 'save', key: 'original' });
    expect(reduce(first.state, { type: 'save', key: 'duplicate' }).effects).toEqual([]);
    const failed = reduce(first.state, { type: 'saveFailed', request: first.state.saveRequest, error: network }).state;
    const retry = reduce(failed, { type: 'save', key: 'unused' });
    expect(retry.effects[0]).toMatchObject({ type: 'save', key: 'original', password: secret });
    const edited = reduce(failed, { type: 'fieldChanged', field: 'password', value: 'A different setup passphrase' }).state;
    expect(edited.retryKey).toBeNull();
  });
  it('clears credentials and aborts only the outstanding save when closed', () => {
    const pending = reduce(filled(), { type: 'save', key: 'first' }).state;
    const closed = reduce(pending, { type: 'close' });
    expect(closed.effects).toEqual([{ type: 'cancelSave', request: pending.saveRequest }]);
    expect(closed.state).toMatchObject({ open: false, password: '', confirmation: '', pending: null, retryKey: null });
    expect(reduce(closed.state, { type: 'saved', request: pending.saveRequest }).state).toBe(closed.state);
    expect(reduce(closed.state, { type: 'saveFailed', request: pending.saveRequest, error: network }).state).toBe(closed.state);
    const reopened = reduce(closed.state, { type: 'open' }).state;
    expect(reopened).toMatchObject({ open: true, password: '', confirmation: '' });
  });
  it('clears credentials on success and prevents a stale status response from reopening setup', () => {
    const pending = reduce(filled(), { type: 'save', key: 'first' }).state;
    const saved = reduce(pending, { type: 'saved', request: pending.saveRequest }).state;
    expect(saved).toMatchObject({ configured: true, open: false, password: '', confirmation: '', pending: null });
    expect(reduce(saved, { type: 'loaded', request: pending.statusRequest, configured: false }).state).toBe(saved);
  });
  it('clears credentials and reloads status after another session sets the password', () => {
    const pending = reduce(filled(), { type: 'save', key: 'first' }).state;
    const conflict = reduce(pending, { type: 'saveFailed', request: pending.saveRequest, error: http(409, 'PASSWORD_ALREADY_SET') });
    expect(conflict.state).toMatchObject({ status: 'loading', configured: null, open: false, password: '', confirmation: '', retryKey: null });
    expect(conflict.effects).toEqual([{ type: 'load', request: conflict.state.statusRequest }]);
  });
  it('expires authentication and clears credentials only for the current unauthorized operation', () => {
    const pending = reduce(filled(), { type: 'save', key: 'first' }).state;
    const unauthorized = reduce(pending, { type: 'saveFailed', request: pending.saveRequest, error: http(401, 'UNAUTHORIZED') });
    expect(unauthorized.effects).toEqual([{ type: 'expireSession' }]);
    expect(unauthorized.state).toMatchObject({ open: false, password: '', confirmation: '', configured: null });
    expect(reduce(pending, { type: 'saveFailed', request: pending.saveRequest - 1, error: http(401, 'UNAUTHORIZED') }).effects).toEqual([]);
    const loading = reduce(initialPasswordSetupState, { type: 'load' }).state;
    expect(reduce(loading, { type: 'loadFailed', request: loading.statusRequest, error: http(401, 'UNAUTHORIZED') }).effects).toEqual([{ type: 'expireSession' }]);
  });
});

describe('initial password API effects', () => {
  it('puts only the password for the current session, with the stable mutation key', async () => {
    const fetch = vi.fn(async (value: RequestInfo | URL) => {
      const request = value as Request;
      expect(request.method).toBe('PUT');
      expect(new URL(request.url).pathname).toBe('/api/me/password');
      expect(request.headers.get('Idempotency-Key')).toBe('stable');
      expect(await request.json()).toEqual({ password: secret });
      return new Response(JSON.stringify({ configured: true }));
    });
    const dispatch = vi.fn();
    const effects = makePasswordSetupEffects(createApiClient<paths>({ baseUrl: 'http://localhost', fetch }), vi.fn());
    await effects({ type: 'save', request: 3, key: 'stable', password: secret }, dispatch, new AbortController().signal);
    expect(dispatch).toHaveBeenCalledWith({ type: 'saved', request: 3 });
    expect(JSON.stringify(dispatch.mock.calls)).not.toContain(secret);
  });
  it.each([{}, { configured: 'false' }, { configured: null }])('rejects malformed status responses', async body => {
    const effects = makePasswordSetupEffects(createApiClient<paths>({ baseUrl: 'http://localhost', fetch: async () => new Response(JSON.stringify(body)) }), vi.fn());
    const dispatch = vi.fn();
    await effects({ type: 'load', request: 2 }, dispatch, new AbortController().signal);
    expect(dispatch.mock.calls[0][0]).toMatchObject({ type: 'loadFailed', request: 2, error: { kind: 'system', status: 502 } });
  });
  it('rejects a successful mutation response that does not confirm configuration', async () => {
    const effects = makePasswordSetupEffects(createApiClient<paths>({ baseUrl: 'http://localhost', fetch: async () => new Response(JSON.stringify({ configured: false })) }), vi.fn());
    const dispatch = vi.fn();
    await effects({ type: 'save', request: 3, key: 'stable', password: secret }, dispatch, new AbortController().signal);
    expect(dispatch.mock.calls[0][0]).toMatchObject({ type: 'saveFailed', error: { kind: 'system', status: 502 } });
  });
  it('propagates close cancellation and drops the response from the cancelled mutation', async () => {
    let signal: AbortSignal | undefined;
    let finish: ((response: Response) => void) | undefined;
    let notifyStarted: (() => void) | undefined;
    const started = new Promise<void>(resolve => { notifyStarted = resolve; });
    const dispatch = vi.fn();
    const effects = makePasswordSetupEffects(createApiClient<paths>({ baseUrl: 'http://localhost', fetch: async value => {
      signal = (value as Request).signal;
      notifyStarted!();
      return new Promise<Response>(resolve => { finish = resolve; });
    } }), vi.fn());
    const pending = effects({ type: 'save', request: 4, key: 'stable', password: secret }, dispatch, new AbortController().signal);
    await started;
    await effects({ type: 'cancelSave', request: 4 }, dispatch, new AbortController().signal);
    expect(signal?.aborted).toBe(true);
    finish!(new Response(JSON.stringify({ configured: true })));
    await pending;
    expect(dispatch).not.toHaveBeenCalled();
  });
  it('delegates reauthentication after the reducer accepts an unauthorized result', async () => {
    const expire = vi.fn();
    const effects = makePasswordSetupEffects(createApiClient<paths>(), expire);
    await effects({ type: 'expireSession' }, vi.fn(), new AbortController().signal);
    expect(expire).toHaveBeenCalledTimes(1);
  });
});
