import { createStore, type EffectHandler } from '../mvi';
import {
  connectionReducer,
  defaultBackoff,
  initialConnectionState,
  reconnectDelayMs,
  type BackoffOptions,
  type ConnectionEffect,
  type ConnectionIntent,
  type ConnectionStatus,
  type ResyncReason,
} from './connection';

/** The subset of `EventSource` we use, so tests can inject a fake. */
export interface EventSourceLike {
  onopen: ((event: Event) => void) | null;
  onerror: ((event: Event) => void) | null;
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void): void;
  close(): void;
}

export interface Timers {
  setTimeout(callback: () => void, ms: number): unknown;
  clearTimeout(handle: unknown): void;
}

export interface ProjectEventsOptions<E> {
  projectId: string;
  /**
   * Named SSE events to listen for. Until `src/lib/events.ts` is fixed by the contract
   * (부록 B), callers pass the list themselves.
   */
  eventTypes: readonly string[];
  /** Validates one event at the boundary. Throw to reject it; it is reported via `onInvalidEvent`. */
  decode: (type: string, data: string) => E;
  onEvent: (event: E) => void;
  /** Re-read server state. Called on the first open and after every reconnect. */
  onResync: (reason: ResyncReason) => void;
  onStatus?: (status: ConnectionStatus) => void;
  onInvalidEvent?: (type: string, data: string, error: unknown) => void;
  createEventSource?: (url: string) => EventSourceLike;
  timers?: Timers;
  random?: () => number;
  backoff?: BackoffOptions;
}

export interface ProjectEventsConnection {
  close(): void;
}

export const projectEventsUrl = (projectId: string) =>
  `/api/projects/${encodeURIComponent(projectId)}/events`;

const defaultTimers: Timers = {
  setTimeout: (callback, ms) => globalThis.setTimeout(callback, ms),
  clearTimeout: (handle) => globalThis.clearTimeout(handle as ReturnType<typeof setTimeout>),
};

export const reportInvalidEvent = (type: string, _data: string, error: unknown) => {
  // Payload is not logged: events may carry user content.
  console.error(`[realtime] rejected "${type}" event`, error);
};

/**
 * Opens the project SSE stream and keeps it alive. On any error the source is closed and
 * reopened with backoff (native EventSource gives up on HTTP errors), and `onResync` fires
 * after each successful open so features can re-read what they missed.
 */
export function connectProjectEvents<E>(options: ProjectEventsOptions<E>): ProjectEventsConnection {
  const createSource =
    options.createEventSource ?? ((url: string) => new EventSource(url) as EventSourceLike);
  const timers = options.timers ?? defaultTimers;
  const random = options.random ?? Math.random;
  const backoff = options.backoff ?? defaultBackoff;
  const onInvalidEvent = options.onInvalidEvent ?? reportInvalidEvent;
  const url = projectEventsUrl(options.projectId);

  let source: EventSourceLike | null = null;
  let retryHandle: unknown = null;

  const closeSource = () => {
    if (!source) return;
    source.onopen = null;
    source.onerror = null;
    source.close();
    source = null;
  };

  const cancelRetry = () => {
    if (retryHandle === null) return;
    timers.clearTimeout(retryHandle);
    retryHandle = null;
  };

  const handleEffect: EffectHandler<ConnectionEffect, ConnectionIntent> = (effect, dispatch) => {
    switch (effect.type) {
      case 'open': {
        closeSource();
        const { generation } = effect;
        const opened = createSource(url);
        opened.onopen = () => dispatch({ type: 'opened', generation });
        opened.onerror = () => dispatch({ type: 'failed', generation });
        for (const type of options.eventTypes) {
          opened.addEventListener(type, (message) => {
            if (opened !== source) return;
            let decoded: E;
            try {
              decoded = options.decode(type, message.data);
            } catch (error) {
              onInvalidEvent(type, message.data, error);
              return;
            }
            options.onEvent(decoded);
          });
        }
        source = opened;
        return;
      }
      case 'close':
        closeSource();
        return;
      case 'scheduleRetry': {
        cancelRetry();
        const { generation } = effect;
        retryHandle = timers.setTimeout(() => {
          retryHandle = null;
          dispatch({ type: 'retryDue', generation });
        }, reconnectDelayMs(effect.attempt, random, backoff));
        return;
      }
      case 'cancelRetry':
        cancelRetry();
        return;
      case 'resync':
        options.onResync(effect.reason);
        return;
    }
  };

  const store = createStore(connectionReducer, initialConnectionState, handleEffect);
  let lastStatus = store.getState().status;
  const unsubscribe = store.subscribe(() => {
    const { status } = store.getState();
    if (status === lastStatus) return;
    lastStatus = status;
    options.onStatus?.(status);
  });

  store.activate();
  store.dispatch({ type: 'start' });

  return {
    close() {
      store.dispatch({ type: 'stop' });
      store.deactivate();
      unsubscribe();
      closeSource();
      cancelRetry();
    },
  };
}
