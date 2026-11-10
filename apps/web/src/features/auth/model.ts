import type { components, paths } from '../../api/schema';
import { errorMessage, isUnauthorized, type ApiError } from '../../lib/api';
import { next, type Reducer } from '../../lib/mvi';
import { authMessages as m } from './messages';

export type Me = components['schemas']['Me'];
export type Account = components['schemas']['Account'];
export type AuthMode = 'login' | 'register';
export type AuthField = 'email' | 'password' | 'displayName' | 'confirmPassword';
type RegisterBody = NonNullable<paths['/api/auth/register']['post']['requestBody']>['content']['application/json'];
type LoginBody = NonNullable<paths['/api/auth/login']['post']['requestBody']>['content']['application/json'];
export type AuthOperation =
  | { readonly kind: 'register'; readonly key: string; readonly body: RegisterBody }
  | { readonly kind: 'login'; readonly key: string; readonly body: LoginBody }
  | { readonly kind: 'logout'; readonly key: string };
export type FieldErrors = Partial<Record<AuthField, string>>;

export interface AuthState {
  readonly status: 'initial' | 'checking' | 'checkFailed' | 'anonymous' | 'authenticated';
  readonly me: Me | null;
  readonly mode: AuthMode;
  readonly email: string;
  readonly displayName: string;
  readonly password: string;
  readonly confirmPassword: string;
  readonly fieldErrors: FieldErrors;
  readonly busy: boolean;
  readonly operation: AuthOperation | null;
  readonly retry: AuthOperation | null;
  readonly error: string | null;
}
export const initialAuthState: AuthState = {
  status: 'initial', me: null, mode: 'login', email: '', displayName: '', password: '', confirmPassword: '',
  fieldErrors: {}, busy: false, operation: null, retry: null, error: null,
};
export type AuthIntent =
  | { readonly type: 'start' }
  | { readonly type: 'sessionLoaded'; readonly me: Me }
  | { readonly type: 'sessionFailed'; readonly error: ApiError }
  | { readonly type: 'modeChanged'; readonly mode: AuthMode }
  | { readonly type: 'fieldChanged'; readonly field: AuthField; readonly value: string }
  | { readonly type: 'submit'; readonly key: string }
  | { readonly type: 'logout'; readonly key: string }
  | { readonly type: 'authenticated'; readonly key: string; readonly me: Me }
  | { readonly type: 'loggedOut'; readonly key: string }
  | { readonly type: 'failed'; readonly key: string; readonly error: ApiError }
  | { readonly type: 'sessionExpired' };
export type AuthEffect = { readonly type: 'loadSession' } | { readonly type: 'perform'; readonly operation: AuthOperation };

/** Match server character limits while preserving every password character, including whitespace. */
export function validateAuthForm(state: AuthState): FieldErrors {
  const errors: FieldErrors = {};
  const email = state.email.trim();
  if (!email || email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = m.emailInvalid;
  const length = [...state.password].length;
  if (length < 12 || length > 128) errors.password = m.passwordLength;
  if (state.mode === 'register') {
    const name = state.displayName.trim();
    if (!name || [...name].length > 100 || /[\u0000-\u001f\u007f]/.test(name)) errors.displayName = m.nicknameInvalid;
    if (state.confirmPassword !== state.password || !state.confirmPassword) errors.confirmPassword = m.passwordMismatch;
  }
  return errors;
}

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
    case 'modeChanged':
      if (state.busy || state.status !== 'anonymous' || state.mode === intent.mode) return next(state);
      return next({ ...initialAuthState, status: state.status, mode: intent.mode, email: state.email, displayName: state.displayName });
    case 'fieldChanged':
      if (state.busy || state.status !== 'anonymous') return next(state);
      return next({ ...state, [intent.field]: intent.value, fieldErrors: { ...state.fieldErrors, [intent.field]: undefined }, retry: null, error: null });
    case 'submit': {
      if (state.busy || state.status !== 'anonymous') return next(state);
      const fieldErrors = validateAuthForm(state);
      if (Object.keys(fieldErrors).length > 0) return next({ ...state, fieldErrors, error: m.checkFields });
      const operation: AuthOperation = state.retry?.kind === state.mode ? state.retry
        : state.mode === 'register' ? { kind: 'register', key: intent.key, body: { email: state.email.trim(), password: state.password, display_name: state.displayName.trim() } }
          : { kind: 'login', key: intent.key, body: { email: state.email.trim(), password: state.password } };
      return next({ ...state, busy: true, operation, fieldErrors: {}, error: null }, { type: 'perform', operation });
    }
    case 'logout': {
      if (state.busy || state.status !== 'authenticated') return next(state);
      const operation: AuthOperation = state.retry?.kind === 'logout' ? state.retry : { kind: 'logout', key: intent.key };
      return next({ ...state, busy: true, operation, error: null }, { type: 'perform', operation });
    }
    case 'authenticated':
      if (state.operation?.key !== intent.key || state.operation.kind === 'logout') return next(state);
      return next({ ...initialAuthState, status: 'authenticated', me: intent.me });
    case 'loggedOut':
      if (state.operation?.key !== intent.key || state.operation.kind !== 'logout') return next(state);
      return next({ ...initialAuthState, status: 'anonymous' });
    case 'failed':
      if (state.operation?.key !== intent.key) return next(state);
      return next({ ...state, busy: false, operation: null, retry: retryable(intent.error) ? state.operation : null, error: errorMessage(intent.error) });
  }
};
