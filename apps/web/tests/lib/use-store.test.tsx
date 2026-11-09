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
  it('runs the load effect and renders the result under StrictMode', async () => {
    const handler: EffectHandler<Effect, Intent> = async (_effect, dispatch) => {
      await Promise.resolve();
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
    expect(seen.every((signal) => signal.aborted)).toBe(true);
    await act(async () => finish());
    expect(container.textContent).toBe('gone');
  });
});
