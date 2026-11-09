import { describe, expect, it, vi } from 'vitest';
import { createStore, next, type EffectHandler, type Reducer } from '../../src/lib/mvi';

type State = { readonly count: number; readonly loading: boolean };
type Intent = { type: 'load' } | { type: 'loaded'; value: number } | { type: 'noop' };
type Effect = { type: 'fetch' };

const reducer: Reducer<State, Intent, Effect> = (state, intent) => {
  switch (intent.type) {
    case 'load':
      return next({ ...state, loading: true }, { type: 'fetch' });
    case 'loaded':
      return next({ count: intent.value, loading: false });
    case 'noop':
      return next(state);
  }
};

const initial: State = { count: 0, loading: false };

describe('next', () => {
  it('collects effects in order', () => {
    expect(next(1, 'a', 'b')).toEqual({ state: 1, effects: ['a', 'b'] });
    expect(next(1)).toEqual({ state: 1, effects: [] });
  });
});

describe('createStore', () => {
  it('drops intents before activation', () => {
    const store = createStore(reducer, initial, vi.fn());
    store.dispatch({ type: 'loaded', value: 3 });
    expect(store.getState()).toBe(initial);
  });

  it('reduces, notifies listeners and runs effects with a result dispatch', async () => {
    const handler: EffectHandler<Effect, Intent> = async (_effect, dispatch) => {
      await Promise.resolve();
      dispatch({ type: 'loaded', value: 7 });
    };
    const store = createStore(reducer, initial, handler);
    const listener = vi.fn();
    store.subscribe(listener);
    store.activate();

    store.dispatch({ type: 'load' });
    expect(store.getState()).toEqual({ count: 0, loading: true });
    await vi.waitFor(() => expect(store.getState()).toEqual({ count: 7, loading: false }));
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it('does not notify when the reducer returns the same state', () => {
    const store = createStore(reducer, initial, vi.fn());
    const listener = vi.fn();
    store.subscribe(listener);
    store.activate();
    store.dispatch({ type: 'noop' });
    expect(listener).not.toHaveBeenCalled();
  });

  it('unsubscribe stops notifications', () => {
    const store = createStore(reducer, initial, vi.fn());
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);
    store.activate();
    unsubscribe();
    store.dispatch({ type: 'loaded', value: 1 });
    expect(listener).not.toHaveBeenCalled();
  });

  it('aborts effects on deactivate and drops their late results', async () => {
    let resolve!: () => void;
    let seenSignal!: AbortSignal;
    const handler: EffectHandler<Effect, Intent> = async (_effect, dispatch, signal) => {
      seenSignal = signal;
      await new Promise<void>((r) => (resolve = r));
      dispatch({ type: 'loaded', value: 99 });
    };
    const store = createStore(reducer, initial, handler);
    store.activate();
    store.dispatch({ type: 'load' });
    store.deactivate();
    expect(seenSignal.aborted).toBe(true);

    store.activate(); // e.g. StrictMode remount: a fresh signal, the old effect stays dead
    resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(store.getState()).toEqual({ count: 0, loading: true });
  });

  it('reports effect handler failures instead of swallowing them', async () => {
    const onEffectError = vi.fn();
    const syncFail = createStore(reducer, initial, () => {
      throw new Error('sync');
    }, { onEffectError });
    syncFail.activate();
    syncFail.dispatch({ type: 'load' });
    expect(onEffectError).toHaveBeenCalledWith(new Error('sync'));

    const asyncFail = createStore(reducer, initial, async () => {
      throw new Error('async');
    }, { onEffectError });
    asyncFail.activate();
    asyncFail.dispatch({ type: 'load' });
    await vi.waitFor(() => expect(onEffectError).toHaveBeenCalledWith(new Error('async')));
  });
});
