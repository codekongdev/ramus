import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { PROJECT_EVENT_TYPES, decodeProjectEvent, type ProjectEvent } from '../events';
import type { ConnectionStatus, ResyncReason } from './connection';
import { connectProjectEvents, type ProjectEventsOptions } from './projectEvents';

type Listener<T> = (value: T) => void;

interface ProjectEventsContextValue {
  readonly status: ConnectionStatus;
  subscribe(listener: Listener<ProjectEvent>): () => void;
  subscribeResync(listener: Listener<ResyncReason>): () => void;
}

const ProjectEventsContext = createContext<ProjectEventsContextValue | null>(null);

export type ProjectEventsConnectionOptions = Pick<
  ProjectEventsOptions<ProjectEvent>,
  'createEventSource' | 'timers' | 'random' | 'backoff' | 'checkSession' | 'onInvalidEvent'
>;

export interface ProjectEventsProviderProps {
  readonly projectId: string;
  /** Session expired while connected. The app moves to the login screen (contracts.md 4장). */
  readonly onUnauthorized: () => void;
  readonly children?: ReactNode;
  /** Test seams; production uses the defaults. */
  readonly connectionOptions?: ProjectEventsConnectionOptions;
}

/** A throwing listener must not starve the others; its error still surfaces. */
function notifyAll<T>(listeners: ReadonlySet<Listener<T>>, value: T) {
  for (const listener of [...listeners]) {
    try {
      listener(value);
    } catch (error) {
      queueMicrotask(() => {
        throw error;
      });
    }
  }
}

/**
 * Opens one SSE connection for the project and fans events out to every feature, so
 * features never open their own EventSource (browsers allow few per origin).
 */
export function ProjectEventsProvider({
  projectId,
  onUnauthorized,
  children,
  connectionOptions,
}: ProjectEventsProviderProps) {
  const [status, setStatus] = useState<ConnectionStatus>('idle');
  const [channels] = useState(() => ({
    events: new Set<Listener<ProjectEvent>>(),
    resync: new Set<Listener<ResyncReason>>(),
  }));
  const onUnauthorizedRef = useRef(onUnauthorized);
  onUnauthorizedRef.current = onUnauthorized;
  const optionsRef = useRef(connectionOptions);
  optionsRef.current = connectionOptions;

  useEffect(() => {
    const connection = connectProjectEvents<ProjectEvent>({
      ...optionsRef.current,
      projectId,
      eventTypes: PROJECT_EVENT_TYPES,
      decode: decodeProjectEvent,
      onEvent: (event) => notifyAll(channels.events, event),
      onResync: (reason) => notifyAll(channels.resync, reason),
      onStatus: setStatus,
      onUnauthorized: () => onUnauthorizedRef.current(),
    });
    return () => connection.close();
  }, [projectId, channels]);

  // Subscribe functions stay stable across status changes so listeners don't resubscribe.
  const subscriptions = useMemo(
    () => ({
      subscribe(listener: Listener<ProjectEvent>) {
        channels.events.add(listener);
        return () => {
          channels.events.delete(listener);
        };
      },
      subscribeResync(listener: Listener<ResyncReason>) {
        channels.resync.add(listener);
        return () => {
          channels.resync.delete(listener);
        };
      },
    }),
    [channels],
  );
  const value = useMemo(() => ({ status, ...subscriptions }), [status, subscriptions]);

  return createElement(ProjectEventsContext.Provider, { value }, children);
}

function useProjectEventsContext(hook: string): ProjectEventsContextValue {
  const context = useContext(ProjectEventsContext);
  if (!context) throw new Error(`${hook} must be used inside <ProjectEventsProvider>`);
  return context;
}

export function useProjectEventsStatus(): ConnectionStatus {
  return useProjectEventsContext('useProjectEventsStatus').status;
}

/**
 * Receives every validated project event. Typical use turns it into an intent:
 * `useProjectEventListener((event) => dispatch({ type: 'serverEvent', event }))`.
 */
export function useProjectEventListener(listener: Listener<ProjectEvent>): void {
  const { subscribe } = useProjectEventsContext('useProjectEventListener');
  const latest = useRef(listener);
  latest.current = listener;
  useEffect(() => subscribe((event) => latest.current(event)), [subscribe]);
}

/**
 * Called whenever the connection (re)opens. Re-read the feature's server state here:
 * events missed while disconnected are not replayed (contracts.md C4).
 */
export function useResyncListener(listener: Listener<ResyncReason>): void {
  const { subscribeResync } = useProjectEventsContext('useResyncListener');
  const latest = useRef(listener);
  latest.current = listener;
  useEffect(() => subscribeResync((reason) => latest.current(reason)), [subscribeResync]);
}
