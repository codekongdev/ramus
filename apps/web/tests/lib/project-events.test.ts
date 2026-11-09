import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  connectProjectEvents,
  projectEventsUrl,
  type ConnectionStatus,
  type EventSourceLike,
  type ProjectEventsOptions,
} from '../../src/lib/realtime';

class FakeEventSource implements EventSourceLike {
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;
  private listeners = new Map<string, ((event: MessageEvent<string>) => void)[]>();

  constructor(readonly url: string) {}

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  close() {
    this.closed = true;
  }
  open() {
    this.onopen?.(new Event('open'));
  }
  fail() {
    this.onerror?.(new Event('error'));
  }
  emit(type: string, data: string) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data }));
    }
  }
}

type TestEvent = { type: string; id: string };

function setup(overrides: Partial<ProjectEventsOptions<TestEvent>> = {}) {
  const sources: FakeEventSource[] = [];
  const statuses: ConnectionStatus[] = [];
  const onEvent = vi.fn();
  const onResync = vi.fn();
  const onInvalidEvent = vi.fn();
  const connection = connectProjectEvents<TestEvent>({
    projectId: 'p/1',
    eventTypes: ['message.created', 'task.updated'],
    decode: (type, data) => {
      const parsed: unknown = JSON.parse(data);
      if (typeof parsed !== 'object' || parsed === null || typeof (parsed as { id?: unknown }).id !== 'string') {
        throw new Error('invalid payload');
      }
      return { type, id: (parsed as { id: string }).id };
    },
    onEvent,
    onResync,
    onInvalidEvent,
    onStatus: (status) => statuses.push(status),
    createEventSource: (url) => {
      const source = new FakeEventSource(url);
      sources.push(source);
      return source;
    },
    timers: { setTimeout: globalThis.setTimeout.bind(globalThis), clearTimeout: (h) => globalThis.clearTimeout(h as never) },
    random: () => 0,
    backoff: { baseMs: 1_000, maxMs: 8_000 },
    ...overrides,
  });
  const latest = () => sources[sources.length - 1]!;
  return { connection, sources, latest, statuses, onEvent, onResync, onInvalidEvent };
}

afterEach(() => {
  vi.useRealTimers();
});

describe('connectProjectEvents', () => {
  it('opens the project stream and resyncs on first open', () => {
    const { latest, statuses, onResync } = setup();
    expect(latest().url).toBe('/api/projects/p%2F1/events');
    expect(projectEventsUrl('abc')).toBe('/api/projects/abc/events');
    latest().open();
    expect(onResync).toHaveBeenCalledWith('initial');
    expect(statuses).toEqual(['connecting', 'open']);
  });

  it('decodes named events and reports invalid ones without forwarding them', () => {
    const { latest, onEvent, onInvalidEvent } = setup();
    latest().open();
    latest().emit('message.created', '{"id":"m1"}');
    latest().emit('task.updated', 'not json');
    latest().emit('task.updated', '{"nope":1}');
    latest().emit('unknown.event', '{"id":"x"}');
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith({ type: 'message.created', id: 'm1' });
    expect(onInvalidEvent).toHaveBeenCalledTimes(2);
  });

  it('closes on error, reconnects with backoff and resyncs after reconnecting', () => {
    vi.useFakeTimers();
    const { sources, latest, statuses, onResync } = setup({
      timers: { setTimeout: (cb, ms) => setTimeout(cb, ms), clearTimeout: (h) => clearTimeout(h as never) },
    });
    latest().open();
    latest().fail();
    expect(sources[0]!.closed).toBe(true);
    expect(statuses.at(-1)).toBe('reconnecting');

    vi.advanceTimersByTime(499);
    expect(sources).toHaveLength(1);
    vi.advanceTimersByTime(1); // attempt 1: 1000ms ceiling, random 0 → 500ms
    expect(sources).toHaveLength(2);

    latest().fail(); // attempt 2 → 1000ms
    vi.advanceTimersByTime(999);
    expect(sources).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(sources).toHaveLength(3);

    latest().open();
    expect(onResync).toHaveBeenLastCalledWith('reconnect');
    expect(statuses.at(-1)).toBe('open');
  });

  it('ignores events from a source that has been replaced', () => {
    vi.useFakeTimers();
    const { sources, latest, onEvent } = setup({
      timers: { setTimeout: (cb, ms) => setTimeout(cb, ms), clearTimeout: (h) => clearTimeout(h as never) },
    });
    latest().open();
    latest().fail();
    vi.advanceTimersByTime(500);
    sources[0]!.emit('message.created', '{"id":"late"}');
    expect(onEvent).not.toHaveBeenCalled();
  });

  it('close stops the stream and cancels a pending retry', () => {
    vi.useFakeTimers();
    const { connection, sources, latest, statuses } = setup({
      timers: { setTimeout: (cb, ms) => setTimeout(cb, ms), clearTimeout: (h) => clearTimeout(h as never) },
    });
    latest().fail();
    connection.close();
    vi.advanceTimersByTime(60_000);
    expect(sources).toHaveLength(1);
    expect(sources[0]!.closed).toBe(true);
    expect(statuses.at(-1)).toBe('closed');
  });

  it('close on an open stream closes the source', () => {
    const { connection, latest } = setup();
    latest().open();
    connection.close();
    expect(latest().closed).toBe(true);
  });
});
