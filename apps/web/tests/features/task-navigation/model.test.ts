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
});
