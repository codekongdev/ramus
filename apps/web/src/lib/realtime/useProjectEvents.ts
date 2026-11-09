import { useEffect, useRef, useState } from 'react';
import type { ConnectionStatus } from './connection';
import {
  connectProjectEvents,
  reportInvalidEvent,
  type ProjectEventsOptions,
} from './projectEvents';

export type UseProjectEventsOptions<E> = Omit<ProjectEventsOptions<E>, 'projectId' | 'onStatus'>;

/**
 * Keeps one SSE connection per project while mounted. Feature stores receive events as
 * intents, e.g. `onEvent: (event) => dispatch({ type: 'serverEvent', event })`.
 * Callbacks may change between renders; only `projectId` and `eventTypes` reconnect.
 */
export function useProjectEvents<E>(
  projectId: string | null,
  options: UseProjectEventsOptions<E>,
): ConnectionStatus {
  const [status, setStatus] = useState<ConnectionStatus>('idle');
  const latest = useRef(options);
  latest.current = options;
  const eventTypesKey = options.eventTypes.join('\n');

  useEffect(() => {
    if (projectId === null) {
      setStatus('idle');
      return undefined;
    }
    const current = latest.current;
    const connection = connectProjectEvents<E>({
      ...current,
      projectId,
      eventTypes: eventTypesKey.split('\n'),
      decode: (type, data) => latest.current.decode(type, data),
      onEvent: (event) => latest.current.onEvent(event),
      onResync: (reason) => latest.current.onResync(reason),
      onInvalidEvent: (type, data, error) =>
        (latest.current.onInvalidEvent ?? reportInvalidEvent)(type, data, error),
      onStatus: setStatus,
    });
    return () => connection.close();
  }, [projectId, eventTypesKey]);

  return status;
}
