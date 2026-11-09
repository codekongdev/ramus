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

  it('preserves an interrupted entry and resumes it only on a matching close', () => {
    const task = entry('task:1');
    const ai = entry('ai-connection');
    const interrupted = modalHostReducer({ current: task }, { type: 'open', entry: ai, preserveCurrent: true });
    expect(interrupted).toEqual({ current: ai, suspended: task });
    expect(modalHostReducer(interrupted, { type: 'close', id: task.id })).toBe(interrupted);
    expect(modalHostReducer(interrupted, { type: 'close', id: ai.id })).toEqual({ current: task });
  });

  it('dismisses both entries on a close without an id, such as route navigation', () => {
    const state = { current: entry('ai-connection'), suspended: entry('task:1') };
    expect(modalHostReducer(state, { type: 'close' })).toEqual({ current: null });
  });

  it('discards the suspended entry on an ordinary replacement', () => {
    const replacement = entry('task:2');
    expect(modalHostReducer({ current: entry('ai-connection'), suspended: entry('task:1') }, {
      type: 'open', entry: replacement,
    })).toEqual({ current: replacement });
  });

  it('keeps the original entry when re-opening or replacing an interruption', () => {
    const task = entry('task:1');
    const ai = entry('ai-connection');
    const state = { current: ai, suspended: task };
    expect(modalHostReducer(state, { type: 'open', entry: ai, preserveCurrent: true }))
      .toEqual(state);
    const alternate = entry('another-interruption');
    expect(modalHostReducer(state, { type: 'open', entry: alternate, preserveCurrent: true }))
      .toEqual({ current: alternate, suspended: task });
  });

  it('does not create a suspended entry when there was no current modal', () => {
    const ai = entry('ai-connection');
    expect(modalHostReducer(initialModalHostState, { type: 'open', entry: ai, preserveCurrent: true }))
      .toEqual({ current: ai });
  });
});
