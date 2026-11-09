import { next, type Reducer } from '../../lib/mvi';
import type { ConnectionStatus } from './api';
import { aiConnectionMessages as messages } from './messages';

export interface AiConnectionState {
  readonly status: ConnectionStatus | 'unknown';
  readonly phase: 'idle' | 'checking' | 'saving' | 'removing';
  readonly open: boolean;
  readonly required: boolean;
  readonly request: number;
  readonly clearKey: number;
  readonly error: string | null;
  readonly notice: string | null;
}

export type AiConnectionIntent =
  | { type: 'ensure' }
  | { type: 'manage' }
  | { type: 'retry' }
  | { type: 'cancel' }
  | { type: 'connect'; apiKey: string }
  | { type: 'disconnect' }
  | { type: 'loaded'; request: number; status: ConnectionStatus }
  | { type: 'connected'; request: number }
  | { type: 'disconnected'; request: number }
  | { type: 'failed'; request: number; message: string };

export type AiConnectionEffect =
  | { type: 'read'; request: number }
  | { type: 'connect'; request: number; apiKey: string }
  | { type: 'disconnect'; request: number }
  | { type: 'finish'; connected: boolean }
  | { type: 'abort' };

export const initialAiConnectionState: AiConnectionState = {
  status: 'unknown', phase: 'idle', open: false, required: false,
  request: 0, clearKey: 0, error: null, notice: null,
};

export const aiConnectionReducer: Reducer<AiConnectionState, AiConnectionIntent, AiConnectionEffect> = (state, intent) => {
  switch (intent.type) {
    case 'ensure':
      if (state.phase === 'removing') return next(state, { type: 'finish', connected: false });
      if (state.phase !== 'idle') return next({ ...state, required: true });
      return next({ ...state, phase: 'checking', required: true, request: state.request + 1, error: null, notice: null },
        { type: 'read', request: state.request + 1 });
    case 'manage':
      if (state.open || state.phase !== 'idle') return next(state);
      return next({ ...state, open: true, phase: 'checking', request: state.request + 1, error: null, notice: null },
        { type: 'read', request: state.request + 1 });
    case 'retry':
      if (state.phase !== 'idle') return next(state);
      return next({ ...state, phase: 'checking', request: state.request + 1, error: null },
        { type: 'read', request: state.request + 1 });
    case 'cancel':
      return next({ ...state, open: false, required: false, phase: 'idle', request: state.request + 1,
        clearKey: state.clearKey + 1, error: null, notice: null }, { type: 'abort' }, { type: 'finish', connected: false });
    case 'connect': {
      if (!state.open || state.phase !== 'idle') return next(state);
      const apiKey = intent.apiKey.trim();
      if (apiKey.length === 0 || apiKey.length > 512) {
        return next({ ...state, error: apiKey.length === 0 ? messages.keyRequired : messages.keyTooLong });
      }
      return next({ ...state, phase: 'saving', request: state.request + 1, error: null, notice: null },
        { type: 'connect', request: state.request + 1, apiKey });
    }
    case 'disconnect':
      if (!state.open || state.phase !== 'idle' || state.status === 'none' || state.status === 'unknown') return next(state);
      return next({ ...state, phase: 'removing', request: state.request + 1, error: null, notice: null },
        { type: 'disconnect', request: state.request + 1 });
    case 'loaded':
      if (intent.request !== state.request) return next(state);
      if (state.required && intent.status === 'connected') {
        return next({ ...state, status: intent.status, phase: 'idle', open: false, required: false },
          { type: 'finish', connected: true });
      }
      return next({ ...state, status: intent.status, phase: 'idle', open: true });
    case 'connected':
      if (intent.request !== state.request) return next(state);
      return next({ ...state, status: 'connected', phase: 'idle', open: !state.required, required: false,
        clearKey: state.clearKey + 1, notice: messages.connected }, { type: 'finish', connected: true });
    case 'disconnected':
      if (intent.request !== state.request) return next(state);
      return next({ ...state, status: 'none', phase: 'idle', clearKey: state.clearKey + 1, notice: messages.disconnected });
    case 'failed':
      if (intent.request !== state.request) return next(state);
      return next({ ...state, phase: 'idle', open: true, error: intent.message });
  }
};
