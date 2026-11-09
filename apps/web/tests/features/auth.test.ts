import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../../src/api/schema';
import { createApiClient, type ApiError } from '../../src/lib/api';
import { makeAuthEffects } from '../../src/features/auth/api';
import { authReducer, initialAuthState, type AuthIntent, type AuthState } from '../../src/features/auth/model';
import { initialParticipantsState, participantsReducer } from '../../src/features/auth/participants';

const anonymous: AuthState = { ...initialAuthState, status: 'anonymous', email: 'person@example.test', now: 1000 };
const network: ApiError = { kind: 'network', cause: new TypeError('unavailable') };
const me = { account: { id: 'a1', email: 'person@example.test', display_name: 'Person' }, default_project_id: 'p1', ai_connection: { status: 'none' as const } };
const business = (code: string): ApiError => ({ kind: 'business', status: 422, code, message: 'Try again', details: null });

describe('auth reducer', () => {
  it('checks the existing session once and treats 401 as anonymous', () => {
    const loading = authReducer(initialAuthState, { type: 'start' });
    expect(loading.effects).toEqual([{ type: 'loadSession' }]);
    expect(authReducer(loading.state, { type: 'start' }).effects).toEqual([]);
    expect(authReducer(loading.state, { type: 'sessionFailed', error: { kind: 'business', status: 401, code: 'UNAUTHORIZED', message: 'login', details: null } }).state.status).toBe('anonymous');
  });
  it('keeps an uncertain email-code request key on retry, blocking duplicate clicks', () => {
    const sending = authReducer(anonymous, { type: 'send', key: 'first' });
    expect(authReducer(sending.state, { type: 'send', key: 'duplicate' }).effects).toEqual([]);
    const failure = authReducer(sending.state, { type: 'failed', key: 'first', error: network }).state;
    const retry = authReducer(failure, { type: 'send', key: 'second' });
    expect(retry.effects).toEqual(sending.effects);
    expect(anonymous.busy).toBe(false);
  });
  it('enforces resend countdown, clears the old code, and permits email correction', () => {
    const sending = authReducer(anonymous, { type: 'send', key: 's' }).state;
    const codeState = authReducer(sending, { type: 'sent', key: 's', resendAt: 61000, now: 1000 }).state;
    expect(codeState.phase).toBe('code');
    expect(authReducer(codeState, { type: 'send', key: 'early' }).effects).toEqual([]);
    const elapsed = authReducer(codeState, { type: 'tick', now: 61000 }).state;
    expect(authReducer(elapsed, { type: 'send', key: 'resend' }).effects).toHaveLength(1);
    const edited = authReducer({ ...codeState, code: '123456' }, { type: 'editEmail' }).state;
    expect(edited).toMatchObject({ phase: 'email', code: '', email: anonymous.email });
  });
  it('retries uncertain verification using its key and creates a new key after a rejected code', () => {
    const codeState = { ...anonymous, phase: 'code' as const, code: '123456' };
    const verifying = authReducer(codeState, { type: 'verify', key: 'verify-first' }).state;
    const uncertain = authReducer(verifying, { type: 'failed', key: 'verify-first', error: network }).state;
    expect(authReducer(uncertain, { type: 'verify', key: 'unused' }).state.operation?.key).toBe('verify-first');
    const rejected = authReducer(verifying, { type: 'failed', key: 'verify-first', error: business('AUTH_CODE_INVALID') }).state;
    expect(authReducer(rejected, { type: 'verify', key: 'new-attempt' }).state.operation?.key).toBe('new-attempt');
  });
  it('shows expiry without dropping the email and ignores stale operation results', () => {
    const state = authReducer({ ...anonymous, phase: 'code', code: '123456' }, { type: 'verify', key: 'v1' }).state;
    expect(authReducer(state, { type: 'verified', key: 'older', me }).state).toBe(state);
    const expired = authReducer(state, { type: 'failed', key: 'v1', error: business('AUTH_CODE_EXPIRED') }).state;
    expect(expired).toMatchObject({ email: anonymous.email, phase: 'code', error: 'Try again', busy: false });
  });
  it('removes authentication and sensitive drafts after successful login/logout', () => {
    const verifying = authReducer({ ...anonymous, phase: 'code', code: '123456' }, { type: 'verify', key: 'v' }).state;
    const authenticated = authReducer(verifying, { type: 'verified', key: 'v', me }).state;
    expect(authenticated).toMatchObject({ status: 'authenticated', me, code: '', operation: null });
    const logout = authReducer(authenticated, { type: 'logout', key: 'out' }).state;
    expect(authReducer(logout, { type: 'loggedOut', key: 'out' }).state).toEqual({ ...initialAuthState, status: 'anonymous' });
  });
});

describe('auth API effects', () => {
  it('sends the stable mutation key and validates the successful code response', async () => {
    const fetch = vi.fn(async (input: RequestInfo | URL) => {
      const request = input instanceof Request ? input : new Request(input);
      expect(request.headers.get('Idempotency-Key')).toBe('stable');
      expect(await request.json()).toEqual({ email: anonymous.email });
      return new Response(JSON.stringify({ resend_available_at: '2026-11-09T12:00:00Z' }), { status: 202 });
    });
    const handle = makeAuthEffects(createApiClient<paths>({ baseUrl: 'http://localhost', fetch }), () => 42);
    const dispatch = vi.fn<(intent: AuthIntent) => void>();
    await handle({ type: 'perform', operation: { kind: 'send', key: 'stable', email: anonymous.email } }, dispatch, new AbortController().signal);
    expect(dispatch).toHaveBeenCalledWith({ type: 'sent', key: 'stable', resendAt: Date.parse('2026-11-09T12:00:00Z'), now: 42 });
  });
  it('rejects malformed session responses at the API boundary', async () => {
    const handle = makeAuthEffects(createApiClient<paths>({ baseUrl: 'http://localhost', fetch: async () => new Response(JSON.stringify({ account: null }), { status: 200 }) }));
    const dispatch = vi.fn();
    await handle({ type: 'loadSession' }, dispatch, new AbortController().signal);
    expect(dispatch.mock.calls[0][0]).toMatchObject({ type: 'sessionFailed', error: { kind: 'system', status: 502 } });
  });
  it('returns network failures as intents so they can be retried', async () => {
    const handle = makeAuthEffects(createApiClient<paths>({ baseUrl: 'http://localhost', fetch: async () => { throw new TypeError('offline'); } }));
    const dispatch = vi.fn();
    await handle({ type: 'perform', operation: { kind: 'verify', key: 'v', email: anonymous.email, code: '123456' } }, dispatch, new AbortController().signal);
    expect(dispatch.mock.calls[0][0]).toMatchObject({ type: 'failed', key: 'v', error: { kind: 'network' } });
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
    expect(participantsReducer(loading, { type: 'failed', generation: loading.generation, error: { kind: 'business', status: 401, code: 'UNAUTHORIZED', message: 'login', details: null } }).state.unauthorized).toBe(true);
  });
});
