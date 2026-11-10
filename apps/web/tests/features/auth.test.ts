import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../../src/api/schema';
import { createApiClient, type ApiError } from '../../src/lib/api';
import { makeAuthEffects } from '../../src/features/auth/api';
import { authReducer, initialAuthState, validateAuthForm, type AuthIntent, type AuthState } from '../../src/features/auth/model';
import { initialParticipantsState, participantsReducer } from '../../src/features/auth/participants';

const password = 'Synthetic-test-passphrase';
const anonymous: AuthState = { ...initialAuthState, status: 'anonymous', email: 'person@example.test', password };
const registration: AuthState = { ...anonymous, mode: 'register', displayName: ' Person ', confirmPassword: password };
const network: ApiError = { kind: 'network', cause: new TypeError('unavailable') };
const me = { account: { id: 'a1', email: 'person@example.test', display_name: 'Person' }, default_project_id: 'p1', ai_connection: { status: 'none' as const } };
const business = (code: string): ApiError => ({ kind: 'business', status: 401, code, message: 'Try again', details: null });

describe('password auth reducer', () => {
  it('checks the existing session once and treats 401 as anonymous', () => {
    const loading = authReducer(initialAuthState, { type: 'start' });
    expect(loading.effects).toEqual([{ type: 'loadSession' }]);
    expect(authReducer(loading.state, { type: 'start' }).effects).toEqual([]);
    expect(authReducer(loading.state, { type: 'sessionFailed', error: business('UNAUTHORIZED') }).state.status).toBe('anonymous');
  });
  it.each([anonymous, registration])('keeps the exact mutation and key after an uncertain response, blocking duplicate submits', state => {
    const sending = authReducer(state, { type: 'submit', key: 'first' });
    expect(authReducer(sending.state, { type: 'submit', key: 'duplicate' }).effects).toEqual([]);
    const failed = authReducer(sending.state, { type: 'failed', key: 'first', error: network }).state;
    expect(authReducer(failed, { type: 'submit', key: 'unused' }).effects).toEqual(sending.effects);
    expect(state.busy).toBe(false);
  });
  it('invalidates an uncertain request after editing a field, including the password', () => {
    const request = authReducer(anonymous, { type: 'submit', key: 'first' }).state;
    const failed = authReducer(request, { type: 'failed', key: 'first', error: network }).state;
    const edited = authReducer(failed, { type: 'fieldChanged', field: 'password', value: 'A different test passphrase' }).state;
    const submitted = authReducer(edited, { type: 'submit', key: 'new' });
    expect(submitted.state.operation?.key).toBe('new');
    expect(submitted.effects).not.toEqual(authReducer(failed, { type: 'submit', key: 'unused' }).effects);
  });
  it('creates a new request key after invalid credentials and preserves the form for correction', () => {
    const request = authReducer(anonymous, { type: 'submit', key: 'first' }).state;
    const denied = authReducer(request, { type: 'failed', key: 'first', error: business('AUTH_INVALID_CREDENTIALS') }).state;
    expect(denied).toMatchObject({ email: anonymous.email, password, error: 'Try again', busy: false, retry: null });
    expect(authReducer(denied, { type: 'submit', key: 'next' }).state.operation?.key).toBe('next');
  });
  it('validates nickname and matching passwords before registering without issuing a request', () => {
    const invalid = authReducer({ ...registration, displayName: ' ', password: 'short', confirmPassword: 'different' }, { type: 'submit', key: 'invalid' });
    expect(Object.keys(invalid.state.fieldErrors).sort()).toEqual(['confirmPassword', 'displayName', 'password']);
    expect(invalid.effects).toEqual([]);
    expect(validateAuthForm({ ...registration, displayName: 'Name\u0000' }).displayName).toBeDefined();
  });
  it('rejects a login password shorter than the API minimum before issuing a request', () => {
    const invalid = authReducer({ ...anonymous, password: 'short-input' }, { type: 'submit', key: 'short-login' });
    expect(invalid.state.fieldErrors.password).toBe('비밀번호를 12~128자로 입력해 주세요.');
    expect(invalid.state.busy).toBe(false);
    expect(invalid.effects).toEqual([]);
  });
  it('preserves all password whitespace and Unicode while normalizing display fields', () => {
    const value = '  🔐비밀번호를 그대로 유지합니다  ';
    const result = authReducer({ ...registration, email: ' person@example.test ', password: value, confirmPassword: value }, { type: 'submit', key: 'unicode' });
    expect(result.state.operation).toEqual({ kind: 'register', key: 'unicode', body: { email: 'person@example.test', display_name: 'Person', password: value } });
    expect(validateAuthForm({ ...registration, password: '🔐'.repeat(11), confirmPassword: '🔐'.repeat(11) }).password).toBeDefined();
    expect(validateAuthForm({ ...registration, password: '🔐'.repeat(12), confirmPassword: '🔐'.repeat(12) })).toEqual({});
  });
  it('clears passwords and uncertain credentials when switching between signup and login', () => {
    const request = authReducer(registration, { type: 'submit', key: 'register' }).state;
    const failed = authReducer(request, { type: 'failed', key: 'register', error: network }).state;
    const switched = authReducer(failed, { type: 'modeChanged', mode: 'login' }).state;
    expect(switched).toMatchObject({ mode: 'login', email: registration.email, password: '', confirmPassword: '', operation: null, retry: null, fieldErrors: {} });
    expect(authReducer(request, { type: 'modeChanged', mode: 'login' }).state).toBe(request);
  });
  it('ignores stale authentication responses and clears credentials after successful login and expiry', () => {
    const request = authReducer(registration, { type: 'submit', key: 'register' }).state;
    expect(authReducer(request, { type: 'authenticated', key: 'older', me }).state).toBe(request);
    const authenticated = authReducer(request, { type: 'authenticated', key: 'register', me }).state;
    expect(authenticated).toEqual({ ...initialAuthState, status: 'authenticated', me });
    expect(authReducer(authenticated, { type: 'fieldChanged', field: 'password', value: password }).state).toBe(authenticated);
    expect(authReducer(authenticated, { type: 'modeChanged', mode: 'register' }).state).toBe(authenticated);
    expect(authReducer(authenticated, { type: 'sessionExpired' }).state).toEqual({ ...initialAuthState, status: 'anonymous' });
  });
  it('preserves logout and clears all authentication state once it succeeds', () => {
    const authenticated = { ...initialAuthState, status: 'authenticated' as const, me };
    const logout = authReducer(authenticated, { type: 'logout', key: 'out' }).state;
    expect(authReducer(logout, { type: 'loggedOut', key: 'older' }).state).toBe(logout);
    expect(authReducer(logout, { type: 'loggedOut', key: 'out' }).state).toEqual({ ...initialAuthState, status: 'anonymous' });
  });
});

describe('password auth API effects', () => {
  it.each([anonymous, registration])('sends a stable mutation key to the password endpoint and validates Me', async state => {
    const operation = authReducer(state, { type: 'submit', key: 'stable' }).state.operation!;
    const fetch = vi.fn(async (input: RequestInfo | URL) => {
      const request = input instanceof Request ? input : new Request(input);
      expect(new URL(request.url).pathname).toBe(`/api/auth/${state.mode}`);
      expect(request.headers.get('Idempotency-Key')).toBe('stable');
      expect(await request.json()).toEqual(operation.kind === 'logout' ? {} : operation.body);
      return new Response(JSON.stringify(me), { status: 200 });
    });
    const handle = makeAuthEffects(createApiClient<paths>({ baseUrl: 'http://localhost', fetch }));
    const dispatch = vi.fn<(intent: AuthIntent) => void>();
    await handle({ type: 'perform', operation }, dispatch, new AbortController().signal);
    expect(dispatch).toHaveBeenCalledWith({ type: 'authenticated', key: 'stable', me });
  });
  it.each(['session', 'login', 'register'] as const)('rejects a malformed successful %s response', async kind => {
    const handle = makeAuthEffects(createApiClient<paths>({ baseUrl: 'http://localhost', fetch: async () => new Response(JSON.stringify({ account: null }), { status: 200 }) }));
    const dispatch = vi.fn();
    const operation = authReducer(kind === 'register' ? registration : anonymous, { type: 'submit', key: 'test' }).state.operation!;
    await handle(kind === 'session' ? { type: 'loadSession' } : { type: 'perform', operation }, dispatch, new AbortController().signal);
    expect(dispatch.mock.calls[0][0]).toMatchObject({ type: kind === 'session' ? 'sessionFailed' : 'failed', error: { kind: 'system', status: 502 } });
  });
  it('returns network failures as intents without copying the request into the failure', async () => {
    const handle = makeAuthEffects(createApiClient<paths>({ baseUrl: 'http://localhost', fetch: async () => { throw new TypeError('offline'); } }));
    const dispatch = vi.fn();
    const operation = authReducer(anonymous, { type: 'submit', key: 'test' }).state.operation!;
    await handle({ type: 'perform', operation }, dispatch, new AbortController().signal);
    expect(dispatch.mock.calls[0][0]).toMatchObject({ type: 'failed', key: 'test', error: { kind: 'network' } });
    expect(JSON.stringify(dispatch.mock.calls)).not.toContain(password);
  });
});

describe('participants reducer', () => {
  it('keeps late results from another project from overwriting the current list', () => {
    const first = participantsReducer(initialParticipantsState, { type: 'load', projectId: 'p1' }).state;
    const second = participantsReducer(first, { type: 'load', projectId: 'p2' }).state;
    expect(participantsReducer(second, { type: 'loaded', generation: first.generation, items: [me.account], project: null }).state).toBe(second);
  });
  it('marks a failed session for reauthentication and never invents online presence', () => {
    const loading = participantsReducer(initialParticipantsState, { type: 'load', projectId: 'p1' }).state;
    expect(participantsReducer(loading, { type: 'failed', generation: loading.generation, error: business('UNAUTHORIZED') }).state.unauthorized).toBe(true);
  });
});
