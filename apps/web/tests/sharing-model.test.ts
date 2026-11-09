import { describe, expect, it } from 'vitest';
import type { Conversation, ConversationInput } from '../src/features/sharing/contract';
import { initialSendState, sendReducer, type SendState, type SendTarget } from '../src/features/sharing/sendModel';
import { initialReceivedState, receivedReducer } from '../src/features/sharing/receivedModel';
import { revision } from './results-fixtures';
const target: SendTarget = { projectId: 'p1', currentConversationId: 'current', revision };
const conversation = (id: string, overrides: Partial<Conversation> = {}): Conversation => ({ id, title: '동명 대화', project_id: 'p1', parent_id: null, task_id: null, path: ['상위'], created_by: 'u1', created_at: revision.created_at, ...overrides });
const input: ConversationInput = { id: 'input', conversation_id: 'current', result_id: 'result1', result_revision_id: revision.id, version: 1, latest_version: 1, title: revision.title, origin: 'share', created_by: 'u1', created_at: revision.created_at };
function open(): SendState { return sendReducer(initialSendState(), { type: 'open', target }).state; }

describe('send conclusion reducer', () => {
  it('filters source/current/cross-project targets and duplicates, keeps selected chips across searches, and ignores stale responses', () => {
    let state = open();
    state = sendReducer(state, { type: 'matches', request: state.request, matches: [conversation('child1'), conversation('current'), conversation('other', { project_id: 'p2' }), conversation('a'), conversation('a')] }).state;
    expect(state.matches.map(item => item.id)).toEqual(['a']);
    state = sendReducer(state, { type: 'toggle', conversation: conversation('a') }).state;
    const previous = state.request;
    state = sendReducer(state, { type: 'query', query: '다음' }).state;
    expect(state.selected.map(item => item.id)).toEqual(['a']);
    expect(sendReducer(state, { type: 'matches', request: previous, matches: [conversation('stale')] }).state).toBe(state);
    state = sendReducer(state, { type: 'toggle', conversation: conversation('a') }).state;
    expect(state.selected).toEqual([]);
    expect(sendReducer(state, { type: 'send', key: 'empty' }).effects).toEqual([]);
  });
  it('retries an uncertain mutation with the same key and frozen targets, then returns to conclusion', () => {
    let state = sendReducer(open(), { type: 'toggle', conversation: conversation('a') }).state;
    const sending = sendReducer(state, { type: 'send', key: 'original' });
    state = sending.state;
    expect(sending.effects).toEqual([{ type: 'send', mutation: { key: 'original', revisionId: revision.id, conversationIds: ['a'] } }]);
    expect(sendReducer(state, { type: 'toggle', conversation: conversation('b') }).state).toBe(state);
    expect(sendReducer(state, { type: 'back' }).state).toBe(state);
    state = sendReducer(state, { type: 'sendFailed', key: 'original', message: '연결 오류' }).state;
    state = sendReducer(state, { type: 'send', key: 'new-key' }).state;
    expect(state.mutation?.key).toBe('original');
    state = sendReducer(state, { type: 'sent', key: 'original', outcomes: { items: [{ conversation_id: 'a', outcome: 'linked' }] } }).state;
    expect(state.target).toBeNull();
    expect(state.notice).toBe('1개 대화에 보냈습니다.');
    expect(sendReducer(state, { type: 'dismissNotice', id: state.noticeId - 1 }).state).toBe(state);
  });
  it('never claims an old revision replaced a newer input, and limits selection to 20', () => {
    let state = open();
    for (let i = 0; i < 21; i++) state = sendReducer(state, { type: 'toggle', conversation: conversation(String(i)) }).state;
    expect(state.selected).toHaveLength(20);
    state = sendReducer(state, { type: 'send', key: 'key' }).state;
    state = sendReducer(state, { type: 'sent', key: 'key', outcomes: { items: [{ conversation_id: '0', outcome: 'kept_newer' }] } }).state;
    expect(state.notice).toContain('더 새 버전');
  });
});
describe('received conclusion reducer', () => {
  it('re-reads pins on input events, source result updates, and reconnect; stale responses cannot change another conversation', () => {
    let state = receivedReducer(initialReceivedState('current'), { type: 'select', conversationId: 'current' }).state;
    state = receivedReducer(state, { type: 'loaded', conversationId: 'current', request: state.request, items: [input] }).state;
    const update = receivedReducer(state, { type: 'event', event: { type: 'result.updated', data: { result_id: 'result1', task_id: 't1', draft_status: null, latest_version: 2, occurred_at: revision.created_at } } });
    expect(update.effects).toEqual([{ type: 'load', conversationId: 'current', request: state.request + 1 }]);
    expect(update.state.items[0]?.result_revision_id).toBe(revision.id);
    const switched = receivedReducer(update.state, { type: 'select', conversationId: 'other' }).state;
    expect(receivedReducer(switched, { type: 'loaded', conversationId: 'current', request: update.state.request, items: [input] }).state).toBe(switched);
    expect(receivedReducer(switched, { type: 'refresh' }).effects[0]).toMatchObject({ conversationId: 'other' });
    expect(receivedReducer(state, { type: 'event', event: { type: 'conversation_inputs.updated', data: { conversation_id: 'current', occurred_at: revision.created_at } } }).effects).toHaveLength(1);
  });
});
