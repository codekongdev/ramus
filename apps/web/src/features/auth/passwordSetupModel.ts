import type { ApiError } from '../../lib/api';
import { errorMessage, isUnauthorized } from '../../lib/api';
import { next, type Reducer } from '../../lib/mvi';
import { passwordSetupMessages as m } from './messages';

export type PasswordSetupState = {
  readonly status: 'initial' | 'loading' | 'ready' | 'failed';
  readonly configured: boolean | null;
  readonly statusRequest: number;
  readonly statusError: string | null;
  readonly open: boolean;
  readonly password: string;
  readonly confirmation: string;
  readonly passwordError: string | null;
  readonly confirmationError: string | null;
  readonly saveRequest: number;
  readonly pending: { readonly key: string; readonly request: number } | null;
  readonly retryKey: string | null;
  readonly error: string | null;
  readonly notice: string | null;
};
export const initialPasswordSetupState: PasswordSetupState = {
  status: 'initial', configured: null, statusRequest: 0, statusError: null, open: false,
  password: '', confirmation: '', passwordError: null, confirmationError: null,
  saveRequest: 0, pending: null, retryKey: null, error: null, notice: null,
};
export type PasswordSetupIntent =
  | { readonly type: 'load' }
  | { readonly type: 'loaded'; readonly request: number; readonly configured: boolean }
  | { readonly type: 'loadFailed'; readonly request: number; readonly error: ApiError }
  | { readonly type: 'open' }
  | { readonly type: 'close' }
  | { readonly type: 'fieldChanged'; readonly field: 'password' | 'confirmation'; readonly value: string }
  | { readonly type: 'save'; readonly key: string }
  | { readonly type: 'saved'; readonly request: number }
  | { readonly type: 'saveFailed'; readonly request: number; readonly error: ApiError };
export type PasswordSetupEffect =
  | { readonly type: 'load'; readonly request: number }
  | { readonly type: 'save'; readonly request: number; readonly key: string; readonly password: string }
  | { readonly type: 'cancelSave'; readonly request: number }
  | { readonly type: 'expireSession' };

function cleared(state: PasswordSetupState): PasswordSetupState {
  return { ...state, open: false, password: '', confirmation: '', passwordError: null, confirmationError: null,
    pending: null, retryKey: null, saveRequest: state.saveRequest + 1, error: null };
}
const uncertain = (error: ApiError) => error.kind === 'network' || error.kind === 'system';
const alreadyConfigured = (error: ApiError) => error.kind === 'business' && error.status === 409 && error.code === 'PASSWORD_ALREADY_SET';
export const passwordSetupReducer: Reducer<PasswordSetupState, PasswordSetupIntent, PasswordSetupEffect> = (state, intent) => {
  switch (intent.type) {
    case 'load': {
      if (state.status === 'loading') return next(state);
      const request = state.statusRequest + 1;
      return next({ ...state, status: 'loading', statusError: null, statusRequest: request }, { type: 'load', request });
    }
    case 'loaded':
      if (intent.request !== state.statusRequest) return next(state);
      return next({ ...(intent.configured ? cleared(state) : state), status: 'ready', configured: intent.configured, statusError: null });
    case 'loadFailed':
      if (intent.request !== state.statusRequest) return next(state);
      if (isUnauthorized(intent.error)) return next({ ...cleared(state), status: 'failed', configured: null, statusError: null }, { type: 'expireSession' });
      return next({ ...state, status: 'failed', statusError: errorMessage(intent.error) ?? m.loadFailed });
    case 'open':
      if (state.status !== 'ready' || state.configured !== false || state.pending) return next(state);
      return next({ ...cleared(state), open: true, notice: null });
    case 'close':
      return state.pending ? next(cleared(state), { type: 'cancelSave', request: state.pending.request }) : next(cleared(state));
    case 'fieldChanged':
      if (!state.open || state.pending) return next(state);
      return next({ ...state, [intent.field]: intent.value, passwordError: null, confirmationError: null, retryKey: null, error: null });
    case 'save': {
      if (!state.open || state.configured !== false || state.pending) return next(state);
      const length = [...state.password].length;
      const passwordError = length < 12 || length > 128 ? m.passwordLength : null;
      const confirmationError = state.confirmation !== state.password || !state.confirmation ? m.passwordMismatch : null;
      if (passwordError || confirmationError) return next({ ...state, passwordError, confirmationError, error: m.checkFields });
      const request = state.saveRequest + 1;
      const key = state.retryKey ?? intent.key;
      return next({ ...state, pending: { key, request }, saveRequest: request, error: null }, { type: 'save', request, key, password: state.password });
    }
    case 'saved':
      if (!state.open || state.pending?.request !== intent.request) return next(state);
      return next({ ...cleared(state), status: 'ready', configured: true, statusRequest: state.statusRequest + 1, notice: m.saved });
    case 'saveFailed': {
      if (!state.open || state.pending?.request !== intent.request) return next(state);
      if (isUnauthorized(intent.error)) return next({ ...cleared(state), configured: null, statusRequest: state.statusRequest + 1 }, { type: 'expireSession' });
      if (alreadyConfigured(intent.error)) {
        const request = state.statusRequest + 1;
        return next({ ...cleared(state), configured: null, status: 'loading', statusError: null, statusRequest: request, notice: m.alreadySet }, { type: 'load', request });
      }
      return next({ ...state, pending: null, retryKey: uncertain(intent.error) ? state.pending.key : null, error: errorMessage(intent.error) });
    }
  }
};
