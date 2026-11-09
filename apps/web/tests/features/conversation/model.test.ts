import { describe, expect, it } from 'vitest';
import type { components } from '../../../src/api/schema';
import { hasActiveRun, initialState, mergeMessages, reducer, type State } from '../../../src/features/conversation/model';

const date = '2026-11-09T01:00:00Z';
const conversation: components['schemas']['ConversationDetail'] = {
  id: 'conversation-1', project_id: 'project-1', parent_id: null, task_id: null,
  title: '멤버십 기획', path: ['멤버십 기획'], created_by: 'author-1', created_at: date, active_run: null,
};
const message = (seq = 1): components['schemas']['Message'] => ({
  id: `message-${seq}`, conversation_id: conversation.id, seq,
  author: { kind: 'human', account_id: 'author-1', display_name: '테스터' }, body: `본문 ${seq}`,
  requested_by: null, run_id: null, is_example: false, created_at: date,
});
const ready = (overrides: Partial<State> = {}): State => ({ ...initialState('project-1', conversation.id), conversation, messages: [message()], ...overrides });
const run: components['schemas']['Run'] = {
  id: 'run-1', conversation_id: conversation.id, task_id: null, purpose: 'work', status: 'pending',
  requested_by: 'author-1', error: null, created_at: date, started_at: null, finished_at: null,
};

describe('conversation reducer', () => {
  it('ignores stale reads and responses for a different conversation', () => {
    const one = reducer(ready(), { type: 'load' }).state;
    const two = reducer(one, { type: 'refresh' }).state;
    const loaded = { type: 'loaded' as const, conversationId: conversation.id, request: one.request, conversation, messages: [message(2)] };
    expect(reducer(two, loaded).state).toBe(two);
    expect(reducer(two, { ...loaded, request: two.request, conversationId: 'other' }).state).toBe(two);
    expect(reducer(two, { type: 'loadFailed', conversationId: 'other', request: two.request, message: '늦은 오류' }).state).toBe(two);
  });

  it('keeps server-confirmed messages when a read began before their commit and deduplicates by id', () => {
    const state = ready({ messages: [message(3), message(1)], request: 2, loading: true, draft: '초안' });
    const loaded = reducer(state, { type: 'loaded', conversationId: conversation.id, request: 2, conversation, messages: [message(1), message(2)] });
    expect(loaded.state.messages.map(item => item.seq)).toEqual([1, 2, 3]);
    expect(loaded.state.draft).toBe('초안');
    expect(mergeMessages([message(2), message(1), message(2)]).map(item => item.seq)).toEqual([1, 2]);
  });

  it('uses the exact draft body, permits discussion during active work and blocks only another AI request', () => {
    const active = ready({ liveRunStatus: 'running', draft: '  사람 논의\n' });
    const sent = reducer(active, { type: 'submit', key: 'human' });
    expect(sent.state.mutation?.body).toBe('  사람 논의\n');
    expect(sent.effects).toHaveLength(1);
    const blocked = reducer({ ...active, draft: '@aI 새 요청' }, { type: 'submit', key: 'ai' });
    expect(blocked.effects).toEqual([]);
    expect(blocked.state.mutationError).toContain('진행 중');
    expect(blocked.state.draft).toBe('@aI 새 요청');
    expect(reducer(ready({ draft: ' \n' }), { type: 'submit', key: 'empty' }).effects).toEqual([]);
  });

  it('prevents duplicate clicks and keeps the same key for a failed action with the same body', () => {
    const sending = reducer(ready({ draft: '첫 메시지' }), { type: 'submit', key: 'original' }).state;
    expect(reducer(sending, { type: 'submit', key: 'duplicate' }).effects).toEqual([]);
    const failed = reducer(sending, { type: 'mutationFailed', conversationId: conversation.id, key: 'original', message: '네트워크 오류' }).state;
    expect(failed.draft).toBe('첫 메시지');
    expect(reducer(failed, { type: 'submit', key: 'retry' }).state.mutation?.key).toBe('original');
    const edited = reducer(failed, { type: 'draftChanged', draft: '다른 메시지' }).state;
    expect(reducer(edited, { type: 'submit', key: 'new' }).state.mutation?.key).toBe('new');
  });

  it('keeps new edits made while sending and refreshes after a server acknowledgement', () => {
    const sending = reducer(ready({ draft: '전송 본문' }), { type: 'submit', key: 'key' }).state;
    const edited = reducer(sending, { type: 'draftChanged', draft: '다음 초안' }).state;
    const success = reducer(edited, { type: 'mutationSucceeded', conversationId: conversation.id, key: 'key', message: message(2), run: null });
    expect(success.state.draft).toBe('다음 초안');
    expect(success.state.messages.map(item => item.seq)).toEqual([1, 2]);
    expect(success.effects).toHaveLength(1);
    expect(reducer(edited, { type: 'mutationSucceeded', conversationId: 'other', key: 'key', message: message(2), run: null }).state).toBe(edited);
    expect(reducer(edited, { type: 'mutationFailed', conversationId: conversation.id, key: 'old', message: '늦은 실패' }).state).toBe(edited);
    expect(reducer(sending, { type: 'mutationSucceeded', conversationId: conversation.id, key: 'key', message: message(2), run: null }).state.draft).toBe('');
  });

  it('handles only relevant SSE events and never resurrects a run finished before the POST acknowledgement', () => {
    const sending = reducer(ready({ draft: '@AI 비교해줘' }), { type: 'submit', key: 'key' }).state;
    const event = { type: 'run.updated' as const, data: { conversation_id: conversation.id, occurred_at: date,
      run: { id: run.id, purpose: run.purpose, status: 'succeeded' as const, task_id: null, requested_by: run.requested_by } } };
    const finished = reducer(sending, { type: 'serverEvent', event }).state;
    const success = reducer(finished, { type: 'mutationSucceeded', conversationId: conversation.id, key: 'key', message: message(2), run });
    expect(hasActiveRun(success.state)).toBe(false);
    const started = reducer(ready(), { type: 'serverEvent', event: { ...event, data: { ...event.data, run: { ...event.data.run, status: 'running' } } } });
    expect(hasActiveRun(started.state)).toBe(true);
    expect(started.effects).toHaveLength(1);
    expect(reducer(ready(), { type: 'serverEvent', event: { type: 'message.created', data: { conversation_id: 'other', message_id: 'm', seq: 1, occurred_at: date } } }).effects).toEqual([]);
    expect(reducer(ready(), { type: 'serverEvent', event: { type: 'message.created', data: { conversation_id: conversation.id, message_id: 'm', seq: 1, occurred_at: date } } }).effects).toHaveLength(1);
  });
});
