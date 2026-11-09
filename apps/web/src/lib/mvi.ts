import { useEffect, useState, useSyncExternalStore } from 'react';

/**
 * MVI helpers (CONVENTIONS.md 프론트엔드 흐름).
 *
 *   View → Intent → Reducer → 새 State → View
 *   외부 작업: EffectHandler → 결과 Intent → Reducer
 *
 * The reducer stays pure: instead of calling APIs or timers it returns the effects it wants
 * run. The EffectHandler runs them and reports success/failure back as intents.
 */

export interface Next<S, E> {
  readonly state: S;
  readonly effects: readonly E[];
}

export type Reducer<S, I, E> = (state: S, intent: I) => Next<S, E>;

export type Dispatch<I> = (intent: I) => void;

/**
 * Runs one effect. `signal` aborts when the store is deactivated (e.g. the view unmounts);
 * intents dispatched after that are dropped so late results never touch a dead store.
 * Expected failures must be turned into result intents — a thrown error is treated as a bug.
 */
export type EffectHandler<E, I> = (
  effect: E,
  dispatch: Dispatch<I>,
  signal: AbortSignal,
) => void | Promise<void>;

/** Builds a reducer result. `next(state)` means "new state, no effects". */
export function next<S, E = never>(state: S, ...effects: E[]): Next<S, E> {
  return { state, effects };
}

export interface Store<S, I> {
  getState(): S;
  dispatch: Dispatch<I>;
  subscribe(listener: () => void): () => void;
  /** Starts accepting intents and running effects. Idempotent. */
  activate(): void;
  /** Aborts running effects and drops further intents until activated again. Idempotent. */
  deactivate(): void;
}

export interface StoreOptions {
  /** Called when an EffectHandler throws or rejects. Defaults to rethrowing asynchronously. */
  onEffectError?: (error: unknown) => void;
}

const rethrowAsync = (error: unknown) => {
  queueMicrotask(() => {
    throw error;
  });
};

/** Framework-free store. Starts inactive; call `activate()` before dispatching. */
export function createStore<S, I, E>(
  reducer: Reducer<S, I, E>,
  initialState: S,
  handleEffect: EffectHandler<E, I>,
  options: StoreOptions = {},
): Store<S, I> {
  const onEffectError = options.onEffectError ?? rethrowAsync;
  const listeners = new Set<() => void>();
  let state = initialState;
  let controller: AbortController | null = null;

  const runEffect = (effect: E, signal: AbortSignal) => {
    const guardedDispatch: Dispatch<I> = (intent) => {
      if (!signal.aborted) dispatch(intent);
    };
    try {
      const pending = handleEffect(effect, guardedDispatch, signal);
      if (pending) pending.catch(onEffectError);
    } catch (error) {
      onEffectError(error);
    }
  };

  const dispatch: Dispatch<I> = (intent) => {
    if (!controller) return;
    const result = reducer(state, intent);
    if (result.state !== state) {
      state = result.state;
      for (const listener of [...listeners]) listener();
    }
    const signal = controller.signal;
    for (const effect of result.effects) runEffect(effect, signal);
  };

  return {
    getState: () => state,
    dispatch,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    activate() {
      controller ??= new AbortController();
    },
    deactivate() {
      controller?.abort();
      controller = null;
    },
  };
}

/**
 * React binding. The reducer and effect handler are captured on first render, so define
 * them at module level (or memoise them) rather than inline.
 */
export function useStore<S, I, E>(
  reducer: Reducer<S, I, E>,
  initialState: S | (() => S),
  handleEffect: EffectHandler<E, I>,
  options?: StoreOptions,
): readonly [S, Dispatch<I>] {
  const [store] = useState(() =>
    createStore(
      reducer,
      typeof initialState === 'function' ? (initialState as () => S)() : initialState,
      handleEffect,
      options,
    ),
  );
  useEffect(() => {
    store.activate();
    return () => store.deactivate();
  }, [store]);
  const state = useSyncExternalStore(store.subscribe, store.getState, store.getState);
  return [state, store.dispatch] as const;
}
