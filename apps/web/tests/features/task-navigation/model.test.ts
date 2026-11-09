import { describe, expect, it } from 'vitest';
import { initialState, reducer, treeRows } from '../../../src/features/task-navigation/model';
import { parent, conversation } from '../../fixtures/tasks';

describe('task navigation', () => {
  it('ignores an obsolete tree response after reconnection', () => {
    const first = reducer(initialState('p1'), { type: 'load' }).state;
    const second = reducer(first, { type: 'load' }).state;
    expect(reducer(second, { type: 'loaded', request: first.request, items: [parent] }).state).toBe(second);
    expect(reducer(second, { type: 'loaded', request: second.request, items: [parent] }).state.items).toEqual([parent]);
  });
  it('orders parents before child tasks and terminates malformed cycles', () => {
    expect(treeRows([conversation, parent]).map(row => [row.conversation.id, row.depth])).toEqual([['c1', 0], ['child1', 1]]);
    const cycle = treeRows([{ ...parent, parent_id: 'child1' }, conversation]);
    expect(cycle).toHaveLength(2);
    expect(new Set(cycle.map(row => row.conversation.id)).size).toBe(2);
  });
  it('keeps a failed title and reuses its request key without duplicating a creation', () => {
    const titled = reducer(initialState('p1'), { type: 'titleChanged', title: '  새 논의  ' }).state;
    const pending = reducer(titled, { type: 'create', key: 'first' });
    expect(pending.effects).toEqual([{ type: 'create', projectId: 'p1', title: '새 논의', key: 'first' }]);
    expect(reducer(pending.state, { type: 'create', key: 'double-click' }).effects).toEqual([]);
    const failed = reducer(pending.state, { type: 'createFailed', key: 'first', error: 'network' }).state;
    expect(failed.title).toBe('  새 논의  ');
    expect(reducer(failed, { type: 'create', key: 'retry' }).effects[0]).toMatchObject({ key: 'first' });
    const edited = reducer(failed, { type: 'titleChanged', title: '다른 논의' }).state;
    expect(reducer(edited, { type: 'create', key: 'new' }).effects[0]).toMatchObject({ key: 'new' });
  });
  it('invalidates pre-creation list reads and includes a created conversation exactly once', () => {
    let state = reducer(initialState('p1'), { type: 'load' }).state;
    const oldRequest = state.request;
    state = reducer(state, { type: 'loaded', request: oldRequest, items: [parent] }).state;
    state = reducer(state, { type: 'titleChanged', title: parent.title }).state;
    state = reducer(state, { type: 'create', key: 'new' }).state;
    state = reducer(state, { type: 'created', key: 'new', conversation: parent }).state;
    expect(state.items).toEqual([parent]);
    expect(state.createdId).toBe(parent.id);
    expect(state.title).toBe('');
    expect(reducer(state, { type: 'loaded', request: oldRequest, items: [] }).state).toBe(state);
  });
});
