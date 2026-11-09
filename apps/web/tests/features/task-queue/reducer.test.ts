import { describe, expect, it } from 'vitest';
import { initialTaskQueueState, taskQueueReducer, type TaskQueueEffect, type TaskQueueState } from '../../../src/features/task-queue/model';
import { task, taskEvent } from './fixtures';

const selected = () => taskQueueReducer(initialTaskQueueState, { type: 'selectConversation', conversationId: 'parent-1' });
const loaded = (state: TaskQueueState, effect: TaskQueueEffect, items = [task()]) =>
  taskQueueReducer(state, { ...effect, type: 'loaded', items });

describe('taskQueueReducer', () => {
  it('loads the selected parent and ignores events for other parents', () => {
    const initial = selected();
    expect(initial.effects).toEqual([{ type: 'load', conversationId: 'parent-1', requestId: 1, eventRevision: 0 }]);
    const state = loaded(initial.state, initial.effects[0]).state;
    const other = taskQueueReducer(state, { type: 'serverEvent', event: taskEvent({ source_conversation_id: 'parent-2', status: 'ready' }) });
    expect(other.state).toBe(state);
    expect(other.effects).toEqual([]);
  });

  it('updates pending → running → ready without an effect that can open a modal', () => {
    const initial = selected();
    let state = loaded(initial.state, initial.effects[0]).state;
    for (const status of ['running', 'ready'] as const) {
      const result = taskQueueReducer(state, { type: 'serverEvent', event: taskEvent({ status }) });
      expect(result.effects).toEqual([]);
      expect(result.state.items[0].status).toBe(status);
      state = result.state;
    }
    expect(initial.state.items).toEqual([]);
  });

  it('keeps SSE changes and new tasks when an older GET snapshot arrives', () => {
    const initial = selected();
    let state = taskQueueReducer(initial.state, { type: 'serverEvent', event: taskEvent({ status: 'ready' }) }).state;
    state = taskQueueReducer(state, { type: 'serverEvent', event: taskEvent({ id: 'task-2', status: 'running' }) }).state;
    const result = loaded(state, initial.effects[0]);
    expect(result.state.items.map((item) => [item.id, item.status])).toEqual([['task-1', 'ready'], ['task-2', 'running']]);
    expect(result.state.loading).toBe(false);
  });

  it('lets a reconnect read replace changes received before that read started', () => {
    const initial = selected();
    const eventState = taskQueueReducer(initial.state, { type: 'serverEvent', event: taskEvent({ status: 'failed' }) }).state;
    const refresh = taskQueueReducer(eventState, { type: 'refresh' });
    const result = loaded(refresh.state, refresh.effects[0], [task({ status: 'running' })]);
    expect(result.state.items[0].status).toBe('running');
    expect(loaded(result.state, initial.effects[0]).state).toBe(result.state);
  });

  it('does not leak a previous conversation or request failure into a newer selection', () => {
    const initial = selected();
    const second = taskQueueReducer(initial.state, { type: 'selectConversation', conversationId: 'parent-2' });
    expect(second.state.items).toEqual([]);
    expect(loaded(second.state, initial.effects[0]).state).toBe(second.state);
    expect(taskQueueReducer(second.state, { ...initial.effects[0], type: 'failed', message: 'old failure' }).state).toBe(second.state);
    const done = loaded(second.state, second.effects[0], [task(), task({ id: 'task-2', source_conversation_id: 'parent-2' })]);
    expect(done.state.items.map((item) => item.id)).toEqual(['task-2']);
  });
});
