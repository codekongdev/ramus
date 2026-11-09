import type { components } from '../../api/schema';
import { errorMessage, hasErrorCode, isUnauthorized, type ApiError } from '../../lib/api';
import { next, type Reducer } from '../../lib/mvi';

export type Me = components['schemas']['Me'];
export type Account = components['schemas']['Account'];
type Operation =
  | { readonly kind: 'send'; readonly key: string; readonly email: string }
  | { readonly kind: 'verify'; readonly key: string; readonly email: string; readonly code: string }
  | { readonly kind: 'logout'; readonly key: string };

export interface AuthState {
  readonly status: 'initial' | 'checking' | 'checkFailed' | 'anonymous' | 'authenticated';
  readonly me: Me | null;
  readonly phase: 'email' | 'code';
  readonly email: string;
  readonly code: string;
  readonly resendAt: number;
  readonly now: number;
  readonly busy: boolean;
  readonly operation: Operation | null;
  readonly retry: Operation | null;
  readonly error: string | null;
}
export const initialAuthState: AuthState = {
  status: 'initial', me: null, phase: 'email', email: '', code: '', resendAt: 0, now: 0,
  busy: false, operation: null, retry: null, error: null,
};
export type AuthIntent =
  | { readonly type: 'start' }
  | { readonly type: 'sessionLoaded'; readonly me: Me }
  | { readonly type: 'sessionFailed'; readonly error: ApiError }
  | { readonly type: 'emailChanged'; readonly email: string }
  | { readonly type: 'codeChanged'; readonly code: string }
  | { readonly type: 'editEmail' }
  | { readonly type: 'send'; readonly key: string }
  | { readonly type: 'verify'; readonly key: string }
  | { readonly type: 'logout'; readonly key: string }
  | { readonly type: 'sent'; readonly key: string; readonly resendAt: number; readonly now: number }
  | { readonly type: 'verified'; readonly key: string; readonly me: Me }
  | { readonly type: 'loggedOut'; readonly key: string }
  | { readonly type: 'failed'; readonly key: string; readonly error: ApiError }
  | { readonly type: 'tick'; readonly now: number }
  | { readonly type: 'sessionExpired' };
export type AuthEffect = { readonly type: 'loadSession' } | { readonly type: 'perform'; readonly operation: Operation };

const retryable = (error: ApiError) => error.kind === 'network' || error.kind === 'system';
export const authReducer: Reducer<AuthState, AuthIntent, AuthEffect> = (state, intent) => {
  switch (intent.type) {
    case 'start':
      if (state.status !== 'initial' && state.status !== 'checkFailed') return next(state);
      return next({ ...state, status: 'checking', error: null }, { type: 'loadSession' });
    case 'sessionLoaded':
      return next({ ...initialAuthState, status: 'authenticated', me: intent.me });
    case 'sessionFailed':
      return next({ ...initialAuthState, status: isUnauthorized(intent.error) ? 'anonymous' : 'checkFailed', error: isUnauthorized(intent.error) ? null : errorMessage(intent.error) });
    case 'sessionExpired':
      return next({ ...initialAuthState, status: 'anonymous' });
    case 'tick':
      return next({ ...state, now: intent.now });
    case 'emailChanged':
      if (state.busy) return next(state);
      return next({ ...state, email: intent.email, retry: null, error: null });
    case 'codeChanged':
      if (state.busy) return next(state);
      return next({ ...state, code: intent.code.replace(/[^0-9]/g, '').slice(0, 6), retry: null, error: null });
    case 'editEmail':
      if (state.busy) return next(state);
      return next({ ...state, phase: 'email', code: '', retry: null, error: null });
    case 'send': {
      if (state.busy || state.status !== 'anonymous' || !state.email.trim()) return next(state);
      if (state.phase === 'code' && state.now < state.resendAt && state.retry?.kind !== 'send') return next(state);
      const operation: Operation = state.retry?.kind === 'send' ? state.retry : { kind: 'send', key: intent.key, email: state.email.trim() };
      return next({ ...state, busy: true, operation, error: null }, { type: 'perform', operation });
    }
    case 'verify': {
      if (state.busy || state.status !== 'anonymous' || state.phase !== 'code' || !/^[0-9]{6}$/.test(state.code)) return next(state);
      const operation: Operation = state.retry?.kind === 'verify' ? state.retry : { kind: 'verify', key: intent.key, email: state.email.trim(), code: state.code };
      return next({ ...state, busy: true, operation, error: null }, { type: 'perform', operation });
    }
    case 'logout': {
      if (state.busy || state.status !== 'authenticated') return next(state);
      const operation: Operation = state.retry?.kind === 'logout' ? state.retry : { kind: 'logout', key: intent.key };
      return next({ ...state, busy: true, operation, error: null }, { type: 'perform', operation });
    }
    case 'sent':
      if (state.operation?.key !== intent.key) return next(state);
      return next({ ...state, busy: false, operation: null, retry: null, phase: 'code', code: '', resendAt: intent.resendAt, now: intent.now, error: null });
    case 'verified':
      if (state.operation?.key !== intent.key) return next(state);
      return next({ ...initialAuthState, status: 'authenticated', me: intent.me });
    case 'loggedOut':
      if (state.operation?.key !== intent.key) return next(state);
      return next({ ...initialAuthState, status: 'anonymous' });
    case 'failed': {
      if (state.operation?.key !== intent.key) return next(state);
      const details = (intent.error.kind === 'business' || intent.error.kind === 'system') ? intent.error.details : null;
      const availableAt = details && typeof details === 'object' && 'resend_available_at' in details && typeof details.resend_available_at === 'string' ? Date.parse(details.resend_available_at) : NaN;
      return next({ ...state, busy: false, operation: null, retry: retryable(intent.error) ? state.operation : null,
        resendAt: hasErrorCode(intent.error, 'AUTH_RATE_LIMITED') && Number.isFinite(availableAt) ? availableAt : state.resendAt,
        error: errorMessage(intent.error) });
    }
  }
};
