import { describe, expect, it } from 'vitest';
import {
  connectionReducer,
  initialConnectionState,
  reconnectDelayMs,
  type ConnectionIntent,
  type ConnectionState,
} from '../../src/lib/realtime';

const run = (intents: ConnectionIntent[], from: ConnectionState = initialConnectionState) =>
  intents.reduce((state, intent) => connectionReducer(state, intent).state, from);

describe('connectionReducer', () => {
  it('start opens generation 1', () => {
    const result = connectionReducer(initialConnectionState, { type: 'start' });
    expect(result.state).toEqual({ status: 'connecting', attempt: 0, generation: 1, hasOpened: false });
    expect(result.effects).toEqual([{ type: 'open', generation: 1 }]);
  });

  it('start is ignored while already connecting or open', () => {
    const connecting = run([{ type: 'start' }]);
    expect(connectionReducer(connecting, { type: 'start' })).toEqual({ state: connecting, effects: [] });
    const open = run([{ type: 'opened', generation: 1 }], connecting);
    expect(connectionReducer(open, { type: 'start' }).effects).toEqual([]);
  });

  it('first open requests an initial resync', () => {
    const result = connectionReducer(run([{ type: 'start' }]), { type: 'opened', generation: 1 });
    expect(result.state.status).toBe('open');
    expect(result.state.hasOpened).toBe(true);
    expect(result.effects).toEqual([{ type: 'resync', reason: 'initial' }]);
  });

  it('failure closes the source and schedules a retry with a growing attempt', () => {
    const open = run([{ type: 'start' }, { type: 'opened', generation: 1 }]);
    const first = connectionReducer(open, { type: 'failed', generation: 1 });
    expect(first.state).toMatchObject({ status: 'reconnecting', attempt: 1, generation: 1 });
    expect(first.effects).toEqual([
      { type: 'close' },
      { type: 'scheduleRetry', attempt: 1, generation: 1 },
    ]);

    const retried = connectionReducer(first.state, { type: 'retryDue', generation: 1 });
    expect(retried.state).toMatchObject({ status: 'reconnecting', generation: 2 });
    expect(retried.effects).toEqual([{ type: 'open', generation: 2 }]);

    const second = connectionReducer(retried.state, { type: 'failed', generation: 2 });
    expect(second.state.attempt).toBe(2);
    expect(second.effects).toContainEqual({ type: 'scheduleRetry', attempt: 2, generation: 2 });
  });

  it('reopening after a drop requests a reconnect resync and resets attempts', () => {
    const state = run([
      { type: 'start' },
      { type: 'opened', generation: 1 },
      { type: 'failed', generation: 1 },
      { type: 'retryDue', generation: 1 },
    ]);
    const result = connectionReducer(state, { type: 'opened', generation: 2 });
    expect(result.state).toMatchObject({ status: 'open', attempt: 0 });
    expect(result.effects).toEqual([{ type: 'resync', reason: 'reconnect' }]);
  });

  it('a first connection that never opened still counts as initial on success', () => {
    const state = run([
      { type: 'start' },
      { type: 'failed', generation: 1 },
      { type: 'retryDue', generation: 1 },
    ]);
    expect(connectionReducer(state, { type: 'opened', generation: 2 }).effects).toEqual([
      { type: 'resync', reason: 'initial' },
    ]);
  });

  it('ignores intents from a replaced generation', () => {
    const state = run([
      { type: 'start' },
      { type: 'failed', generation: 1 },
      { type: 'retryDue', generation: 1 },
    ]);
    for (const intent of [
      { type: 'opened', generation: 1 },
      { type: 'failed', generation: 1 },
      { type: 'retryDue', generation: 1 },
    ] as const) {
      expect(connectionReducer(state, intent)).toEqual({ state, effects: [] });
    }
  });

  it('stop closes, cancels the retry and invalidates pending intents', () => {
    const reconnecting = run([{ type: 'start' }, { type: 'failed', generation: 1 }]);
    const stopped = connectionReducer(reconnecting, { type: 'stop' });
    expect(stopped.state).toMatchObject({ status: 'closed', generation: 2 });
    expect(stopped.effects).toEqual([{ type: 'close' }, { type: 'cancelRetry' }]);
    expect(connectionReducer(stopped.state, { type: 'retryDue', generation: 1 }).effects).toEqual([]);
    expect(connectionReducer(stopped.state, { type: 'stop' }).effects).toEqual([]);
  });

  it('can start again after stop', () => {
    const stopped = run([{ type: 'start' }, { type: 'stop' }]);
    const restarted = connectionReducer(stopped, { type: 'start' });
    expect(restarted.state).toMatchObject({ status: 'connecting', generation: 3 });
    expect(restarted.effects).toEqual([{ type: 'open', generation: 3 }]);
  });

  it('does not mutate the previous state', () => {
    const before = Object.freeze({ ...initialConnectionState });
    expect(() => connectionReducer(before, { type: 'start' })).not.toThrow();
    expect(before.status).toBe('idle');
  });
});

describe('reconnectDelayMs', () => {
  const options = { baseMs: 500, maxMs: 15_000 };

  it('doubles per attempt within the jitter band', () => {
    expect(reconnectDelayMs(1, () => 0, options)).toBe(250);
    expect(reconnectDelayMs(1, () => 1, options)).toBe(500);
    expect(reconnectDelayMs(2, () => 0, options)).toBe(500);
    expect(reconnectDelayMs(3, () => 1, options)).toBe(2_000);
  });

  it('caps at maxMs even for huge attempts', () => {
    expect(reconnectDelayMs(10, () => 1, options)).toBe(15_000);
    expect(reconnectDelayMs(10_000, () => 1, options)).toBe(15_000);
    expect(reconnectDelayMs(10_000, () => 0, options)).toBe(7_500);
  });

  it('treats attempt 0 like the first attempt', () => {
    expect(reconnectDelayMs(0, () => 1, options)).toBe(500);
  });
});
