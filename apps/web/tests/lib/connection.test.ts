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

// start(g1) → opened → failed(g2, check) → session ok(retry g2) → retryDue(open g3)
const afterOneDrop: ConnectionIntent[] = [
  { type: 'start' },
  { type: 'opened', generation: 1 },
  { type: 'failed', generation: 1 },
  { type: 'sessionChecked', generation: 2, expired: false },
  { type: 'retryDue', generation: 2 },
];

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

  it('failure closes the source and checks the session before retrying', () => {
    const open = run([{ type: 'start' }, { type: 'opened', generation: 1 }]);
    const failed = connectionReducer(open, { type: 'failed', generation: 1 });
    expect(failed.state).toMatchObject({ status: 'reconnecting', attempt: 1, generation: 2 });
    expect(failed.effects).toEqual([{ type: 'close' }, { type: 'checkSession', generation: 2 }]);

    const checked = connectionReducer(failed.state, { type: 'sessionChecked', generation: 2, expired: false });
    expect(checked.state).toBe(failed.state);
    expect(checked.effects).toEqual([{ type: 'scheduleRetry', attempt: 1, generation: 2 }]);

    const retried = connectionReducer(checked.state, { type: 'retryDue', generation: 2 });
    expect(retried.state).toMatchObject({ status: 'reconnecting', generation: 3 });
    expect(retried.effects).toEqual([{ type: 'open', generation: 3 }]);

    const again = connectionReducer(retried.state, { type: 'failed', generation: 3 });
    expect(again.state.attempt).toBe(2);
  });

  it('an expired session stops reconnecting', () => {
    const failed = run([{ type: 'start' }, { type: 'failed', generation: 1 }]);
    const result = connectionReducer(failed, { type: 'sessionChecked', generation: 2, expired: true });
    expect(result.state).toMatchObject({ status: 'unauthorized', generation: 3 });
    expect(result.effects).toEqual([{ type: 'notifyUnauthorized' }]);
    expect(connectionReducer(result.state, { type: 'retryDue', generation: 2 }).effects).toEqual([]);
  });

  it('can start again after an expired session (new login)', () => {
    const unauthorized = run([
      { type: 'start' },
      { type: 'failed', generation: 1 },
      { type: 'sessionChecked', generation: 2, expired: true },
    ]);
    const restarted = connectionReducer(unauthorized, { type: 'start' });
    expect(restarted.state).toMatchObject({ status: 'connecting', attempt: 0, generation: 4 });
    expect(restarted.effects).toEqual([{ type: 'open', generation: 4 }]);
  });

  it('a repeated error from the closed source does not start a second check', () => {
    const failed = run([{ type: 'start' }, { type: 'failed', generation: 1 }]);
    expect(connectionReducer(failed, { type: 'failed', generation: 1 })).toEqual({ state: failed, effects: [] });
  });

  it('reopening after a drop requests a reconnect resync and resets attempts', () => {
    const result = connectionReducer(run(afterOneDrop), { type: 'opened', generation: 3 });
    expect(result.state).toMatchObject({ status: 'open', attempt: 0 });
    expect(result.effects).toEqual([{ type: 'resync', reason: 'reconnect' }]);
  });

  it('a first connection that never opened still counts as initial on success', () => {
    const state = run([
      { type: 'start' },
      { type: 'failed', generation: 1 },
      { type: 'sessionChecked', generation: 2, expired: false },
      { type: 'retryDue', generation: 2 },
    ]);
    expect(connectionReducer(state, { type: 'opened', generation: 3 }).effects).toEqual([
      { type: 'resync', reason: 'initial' },
    ]);
  });

  it('ignores intents from a replaced generation', () => {
    const state = run(afterOneDrop);
    for (const intent of [
      { type: 'opened', generation: 2 },
      { type: 'failed', generation: 1 },
      { type: 'retryDue', generation: 2 },
      { type: 'sessionChecked', generation: 2, expired: true },
    ] as const) {
      expect(connectionReducer(state, intent)).toEqual({ state, effects: [] });
    }
  });

  it('stop closes, cancels the retry and invalidates pending intents', () => {
    const reconnecting = run([{ type: 'start' }, { type: 'failed', generation: 1 }]);
    const stopped = connectionReducer(reconnecting, { type: 'stop' });
    expect(stopped.state).toMatchObject({ status: 'closed', generation: 3 });
    expect(stopped.effects).toEqual([{ type: 'close' }, { type: 'cancelRetry' }]);
    expect(connectionReducer(stopped.state, { type: 'sessionChecked', generation: 2, expired: false }).effects).toEqual([]);
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
