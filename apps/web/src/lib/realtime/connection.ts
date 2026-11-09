import { next, type Next } from '../mvi';

/**
 * SSE connection lifecycle as an MVI feature (P0-B3 예시 기능). The reducer only decides;
 * opening sockets and timers happen in the effect handler in `projectEvents.ts`.
 *
 * Each EventSource gets a `generation`. Intents from an older generation are ignored, so a
 * late `error`/`open` from a replaced connection cannot clobber the current state.
 * Every successful open asks for a resync: the server state is the source of truth and
 * events missed while disconnected are not replayed (roadmap 3장 실시간).
 */

export type ConnectionStatus = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed';

export interface ConnectionState {
  readonly status: ConnectionStatus;
  /** Consecutive failures since the last successful open. */
  readonly attempt: number;
  readonly generation: number;
  readonly hasOpened: boolean;
}

export type ConnectionIntent =
  | { readonly type: 'start' }
  | { readonly type: 'opened'; readonly generation: number }
  | { readonly type: 'failed'; readonly generation: number }
  | { readonly type: 'retryDue'; readonly generation: number }
  | { readonly type: 'stop' };

export type ResyncReason = 'initial' | 'reconnect';

export type ConnectionEffect =
  | { readonly type: 'open'; readonly generation: number }
  | { readonly type: 'close' }
  | { readonly type: 'scheduleRetry'; readonly attempt: number; readonly generation: number }
  | { readonly type: 'cancelRetry' }
  | { readonly type: 'resync'; readonly reason: ResyncReason };

export const initialConnectionState: ConnectionState = {
  status: 'idle',
  attempt: 0,
  generation: 0,
  hasOpened: false,
};

type Result = Next<ConnectionState, ConnectionEffect>;

export function connectionReducer(state: ConnectionState, intent: ConnectionIntent): Result {
  switch (intent.type) {
    case 'start': {
      if (state.status !== 'idle' && state.status !== 'closed') return next(state);
      const generation = state.generation + 1;
      return next<ConnectionState, ConnectionEffect>(
        { ...state, status: 'connecting', attempt: 0, generation },
        { type: 'open', generation },
      );
    }
    case 'opened': {
      if (intent.generation !== state.generation) return next(state);
      if (state.status !== 'connecting' && state.status !== 'reconnecting') return next(state);
      return next<ConnectionState, ConnectionEffect>(
        { ...state, status: 'open', attempt: 0, hasOpened: true },
        { type: 'resync', reason: state.hasOpened ? 'reconnect' : 'initial' },
      );
    }
    case 'failed': {
      if (intent.generation !== state.generation) return next(state);
      if (state.status === 'idle' || state.status === 'closed') return next(state);
      const attempt = state.attempt + 1;
      return next<ConnectionState, ConnectionEffect>(
        { ...state, status: 'reconnecting', attempt },
        { type: 'close' },
        { type: 'scheduleRetry', attempt, generation: state.generation },
      );
    }
    case 'retryDue': {
      if (intent.generation !== state.generation || state.status !== 'reconnecting') return next(state);
      const generation = state.generation + 1;
      return next<ConnectionState, ConnectionEffect>({ ...state, generation }, { type: 'open', generation });
    }
    case 'stop': {
      if (state.status === 'idle' || state.status === 'closed') return next(state);
      return next<ConnectionState, ConnectionEffect>(
        { ...state, status: 'closed', generation: state.generation + 1 },
        { type: 'close' },
        { type: 'cancelRetry' },
      );
    }
  }
}

export interface BackoffOptions {
  readonly baseMs: number;
  readonly maxMs: number;
}

export const defaultBackoff: BackoffOptions = { baseMs: 500, maxMs: 15_000 };

/**
 * Exponential backoff with "equal jitter": half fixed, half random, so many clients that
 * lost the server at the same moment don't reconnect in lockstep. `attempt` starts at 1.
 */
export function reconnectDelayMs(
  attempt: number,
  random: () => number,
  { baseMs, maxMs }: BackoffOptions = defaultBackoff,
): number {
  const exponent = Math.max(0, attempt - 1);
  const ceiling = Math.min(maxMs, baseMs * 2 ** Math.min(exponent, 30));
  return Math.round(ceiling / 2 + random() * (ceiling / 2));
}
