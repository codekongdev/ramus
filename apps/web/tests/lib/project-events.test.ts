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
    checkSession: async () => false,
    random: () => 0,
    backoff: { baseMs: 1_000, maxMs: 8_000 },
    ...overrides,
  });
  const latest = () => sources[sources.length - 1]!;
  return { connection, sources, latest, statuses, onEvent, onResync, onInvalidEvent };
}

const fakeTimers = () => ({
  setTimeout: (cb: () => void, ms: number) => setTimeout(cb, ms),
  clearTimeout: (h: unknown) => clearTimeout(h as never),
});

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

  it('closes on error, checks the session, reconnects with backoff and resyncs', async () => {
    vi.useFakeTimers();
    const checkSession = vi.fn(async () => false);
    const { sources, latest, statuses, onResync } = setup({ checkSession, timers: fakeTimers() });
    latest().open();
    latest().fail();
    expect(sources[0]!.closed).toBe(true);
    expect(statuses.at(-1)).toBe('reconnecting');
    expect(checkSession).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(499);
    expect(sources).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1); // attempt 1: 1000ms ceiling, random 0 → 500ms
    expect(sources).toHaveLength(2);

    latest().fail(); // attempt 2 → 1000ms
    await vi.advanceTimersByTimeAsync(999);
    expect(sources).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(sources).toHaveLength(3);

    latest().open();
    expect(onResync).toHaveBeenLastCalledWith('reconnect');
    expect(statuses.at(-1)).toBe('open');
  });

  it('stops reconnecting and notifies when the session has expired', async () => {
    vi.useFakeTimers();
    const onUnauthorized = vi.fn();
    const { sources, latest, statuses } = setup({
      checkSession: async () => true,
      onUnauthorized,
      timers: fakeTimers(),
    });
    latest().open();
    latest().fail();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(statuses.at(-1)).toBe('unauthorized');
    expect(sources).toHaveLength(1);
  });

  it('keeps retrying when the session check itself fails', async () => {
    vi.useFakeTimers();
    const { sources, latest } = setup({
      checkSession: async () => {
        throw new TypeError('Failed to fetch');
      },
      timers: fakeTimers(),
    });
    latest().fail();
    await vi.advanceTimersByTimeAsync(500);
    expect(sources).toHaveLength(2);
  });

  it('ignores events from a source that has been replaced', async () => {
    vi.useFakeTimers();
    const { sources, latest, onEvent } = setup({ timers: fakeTimers() });
    latest().open();
    latest().fail();
    await vi.advanceTimersByTimeAsync(500);
    expect(sources).toHaveLength(2);
    sources[0]!.emit('message.created', '{"id":"late"}');
    expect(onEvent).not.toHaveBeenCalled();
  });

  it('close stops the stream and cancels a pending retry', async () => {
    vi.useFakeTimers();
    const { connection, sources, latest, statuses } = setup({ timers: fakeTimers() });
    latest().fail();
    await vi.advanceTimersByTimeAsync(0); // session check done, retry scheduled
    connection.close();
    await vi.advanceTimersByTimeAsync(60_000);
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
