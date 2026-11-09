// @vitest-environment jsdom
import { StrictMode, act, createElement, useEffect } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { next, useStore, type EffectHandler, type Reducer } from '../../src/lib/mvi';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

type State = { readonly items: readonly string[]; readonly status: 'idle' | 'loading' | 'ready' };
type Intent = { type: 'mounted' } | { type: 'loaded'; items: string[] };
type Effect = { type: 'load' };

const reducer: Reducer<State, Intent, Effect> = (state, intent) => {
  switch (intent.type) {
    case 'mounted':
      // Ignores a duplicate load while one is in flight (the shape the review reproduced).
      if (state.status === 'loading') return next(state);
      return next({ ...state, status: 'loading' }, { type: 'load' });
    case 'loaded':
      return next({ items: intent.items, status: 'ready' });
  }
};

let container: HTMLElement;
let root: Root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

describe('useStore', () => {
  it('finishes loading under StrictMode with a reducer that ignores duplicate loads', async () => {
    const signals: AbortSignal[] = [];
    const handler: EffectHandler<Effect, Intent> = async (_effect, dispatch, signal) => {
      signals.push(signal);
      await new Promise((resolve) => setTimeout(resolve, 0));
      dispatch({ type: 'loaded', items: ['a', 'b'] });
    };
    function List() {
      const [state, dispatch] = useStore(reducer, { items: [], status: 'idle' }, handler);
      useEffect(() => dispatch({ type: 'mounted' }), [dispatch]);
      return createElement('p', null, `${state.status}:${state.items.join(',')}`);
    }

    await act(async () => {
      root.render(createElement(StrictMode, null, createElement(List)));
    });
    await vi.waitFor(() => expect(container.textContent).toBe('ready:a,b'));
    expect(signals).toHaveLength(1);
    expect(signals[0]!.aborted).toBe(false);
  });

  it('runs an initial intent a child dispatches before the parent effect activates the store', async () => {
    const handler: EffectHandler<Effect, Intent> = async (_effect, dispatch) => {
      await Promise.resolve();
      dispatch({ type: 'loaded', items: ['x'] });
    };
    function Child({ dispatch }: { dispatch: (intent: Intent) => void }) {
      useEffect(() => dispatch({ type: 'mounted' }), [dispatch]);
      return null;
    }
    function Parent() {
      const [state, dispatch] = useStore(reducer, { items: [], status: 'idle' }, handler);
      return createElement('div', null, `${state.status}:${state.items.join(',')}`, createElement(Child, { dispatch }));
    }

    for (const tree of [createElement(Parent), createElement(StrictMode, null, createElement(Parent))]) {
      await act(async () => root.render(createElement('div', { key: Math.random() }, tree)));
      await vi.waitFor(() => expect(container.textContent).toBe('ready:x'));
    }
  });

  it('drops results that arrive after unmount', async () => {
    let finish!: () => void;
    const seen: AbortSignal[] = [];
    const handler: EffectHandler<Effect, Intent> = async (_effect, dispatch, signal) => {
      seen.push(signal);
      await new Promise<void>((resolve) => (finish = resolve));
      dispatch({ type: 'loaded', items: ['late'] });
    };
    function List() {
      const [state, dispatch] = useStore(reducer, { items: [], status: 'idle' }, handler);
      useEffect(() => dispatch({ type: 'mounted' }), [dispatch]);
      return createElement('p', null, state.status);
    }

    act(() => root.render(createElement(List)));
    expect(container.textContent).toBe('loading');
    act(() => root.render(createElement('p', null, 'gone')));
    await Promise.resolve(); // teardown runs one microtask after unmount
    expect(seen.every((signal) => signal.aborted)).toBe(true);
    await act(async () => finish());
    expect(container.textContent).toBe('gone');
  });
});
