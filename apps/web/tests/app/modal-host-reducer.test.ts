import { describe, expect, it } from 'vitest';
import {
  initialModalHostState,
  modalHostReducer,
  type ModalEntry,
} from '../../src/app/modal/modalHostReducer';

const entry = (id: string): ModalEntry => ({ id, render: () => id });

describe('modalHostReducer', () => {
  it('opens a modal', () => {
    const a = entry('a');
    expect(modalHostReducer(initialModalHostState, { type: 'open', entry: a })).toEqual({ current: a });
  });

  it('replaces the current modal instead of stacking', () => {
    const b = entry('b');
    const state = modalHostReducer({ current: entry('a') }, { type: 'open', entry: b });
    expect(state.current).toBe(b);
  });

  it('closes the current modal', () => {
    expect(modalHostReducer({ current: entry('a') }, { type: 'close' })).toEqual({ current: null });
    expect(modalHostReducer({ current: entry('a') }, { type: 'close', id: 'a' })).toEqual({ current: null });
  });

  it('ignores a stale close for a modal that was already replaced', () => {
    const state = { current: entry('b') };
    expect(modalHostReducer(state, { type: 'close', id: 'a' })).toBe(state);
  });

  it('returns the same state when nothing is open', () => {
    expect(modalHostReducer(initialModalHostState, { type: 'close' })).toBe(initialModalHostState);
  });

  it('does not mutate the previous state', () => {
    const prev = Object.freeze({ current: Object.freeze(entry('a')) });
    expect(() => modalHostReducer(prev, { type: 'open', entry: entry('b') })).not.toThrow();
    expect(prev.current.id).toBe('a');
  });
});
