import { describe, expect, it } from 'vitest';
import { hasActiveRun, initialTaskModalState, mergeMessages, taskModalReducer } from '../../../src/features/task-modal/model';
import { conversation, date, me, message, readyState, task } from './fixtures';

describe('task modal reducer', () => {
  it('ignores responses for a previous task and previous refresh', () => {
    const initial = taskModalReducer(initialTaskModalState(task.id), { type: 'refresh' }).state;
    const latest = taskModalReducer(initial, { type: 'refresh' }).state;
    const loaded = { type: 'loaded' as const, taskId: task.id, request: initial.request, task, me, conversation, messages: [message()] };
    expect(taskModalReducer(latest, loaded).state).toBe(latest);
    expect(taskModalReducer(latest, { ...loaded, request: latest.request, taskId: 'other' }).state).toBe(latest);
    expect(taskModalReducer(latest, { ...loaded, request: latest.request }).state.task).toEqual(task);
  });
  it('switches task without leaking a previous draft', () => {
    const changed = taskModalReducer(readyState({ draft: '비밀 초안' }), { type: 'select', taskId: 'task-2' });
    expect(changed.state.draft).toBe('');
    expect(changed.state.task).toBeNull();
    expect(changed.effects).toEqual([{ type: 'load', taskId: 'task-2', request: 1 }]);
  });
  it('allows plain discussion while the child is running and blocks another AI run', () => {
    const active = readyState({ task: { ...task, status: 'running' }, draft: '논의를 계속합니다.' });
    expect(taskModalReducer(active, { type: 'submit', key: 'plain' }).effects).toHaveLength(1);
    const blocked = taskModalReducer({ ...active, draft: '@aI 보완해줘' }, { type: 'submit', key: 'ai' });
    expect(blocked.effects).toEqual([]);
    expect(blocked.state.draft).toBe('@aI 보완해줘');
    expect(blocked.state.mutationError).toContain('진행 중');
  });
  it('prevents duplicate clicks and reuses the action key after an uncertain failure', () => {
    const first = taskModalReducer(readyState({ draft: '메시지' }), { type: 'submit', key: 'first-key' });
    expect(taskModalReducer(first.state, { type: 'submit', key: 'duplicate' }).effects).toHaveLength(0);
    const failed = taskModalReducer(first.state, { type: 'mutationFailed', taskId: task.id, key: 'first-key', message: '네트워크 오류' }).state;
    const retry = taskModalReducer(failed, { type: 'submit', key: 'new-key' });
    expect(retry.state.mutation?.key).toBe('first-key');
    expect(retry.state.draft).toBe('메시지');
    const edited = taskModalReducer(failed, { type: 'draftChanged', draft: '변경' }).state;
    expect(taskModalReducer(edited, { type: 'submit', key: 'new-key' }).state.mutation?.key).toBe('new-key');
  });
  it('keeps edits made while a send is pending and ignores late mutation replies', () => {
    const sending = taskModalReducer(readyState({ draft: '원문' }), { type: 'submit', key: 'key' }).state;
    const changed = taskModalReducer(sending, { type: 'draftChanged', draft: '새 초안' }).state;
    const success = taskModalReducer(changed, { type: 'mutationSucceeded', taskId: task.id, key: 'key', message: message(2) });
    expect(success.state.draft).toBe('새 초안');
    expect(success.state.messages).toHaveLength(2);
    expect(taskModalReducer(changed, { type: 'mutationSucceeded', taskId: 'old-task', key: 'key' }).state).toBe(changed);
  });
  it('only lets the requester cancel an active task or retry a failed/cancelled task', () => {
    const active = readyState({ task: { ...task, status: 'running' } });
    expect(taskModalReducer(active, { type: 'action', kind: 'cancel', key: 'c' }).effects).toHaveLength(1);
    expect(taskModalReducer(active, { type: 'action', kind: 'retry', key: 'r' }).effects).toHaveLength(0);
    expect(taskModalReducer({ ...active, me: { ...me, account: { ...me.account, id: 'viewer' } } }, { type: 'action', kind: 'cancel', key: 'c' }).effects).toHaveLength(0);
    expect(taskModalReducer(readyState({ task: { ...task, status: 'failed' } }), { type: 'action', kind: 'retry', key: 'r' }).effects).toHaveLength(1);
  });
  it('refreshes only events for this child and marks a started summary run active immediately', () => {
    const state = readyState();
    const unrelated = { type: 'message.created' as const, data: { conversation_id: 'parent-1', message_id: 'm2', seq: 2, occurred_at: date } };
    expect(taskModalReducer(state, { type: 'serverEvent', event: unrelated }).effects).toHaveLength(0);
    const event = { type: 'run.updated' as const, data: { conversation_id: 'child-1', occurred_at: date, run: { id: 'run-1', purpose: 'summary' as const, status: 'running' as const, task_id: task.id, requested_by: me.account.id } } };
    const changed = taskModalReducer(state, { type: 'serverEvent', event });
    expect(changed.effects).toHaveLength(1);
    expect(hasActiveRun(changed.state)).toBe(true);
  });
  it('deduplicates and sorts messages by sequence', () => {
    expect(mergeMessages([message(3), message(1), message(3), message(2)]).map(item => item.seq)).toEqual([1, 2, 3]);
  });
});
