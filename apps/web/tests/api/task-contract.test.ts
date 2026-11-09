import { describe, expect, it } from 'vitest';
import { parseTask, parseTaskList, parseMessageList, parseConversationDetail, parseMe, parsePostMessageResponse, TaskDecodeError } from '../../src/lib/api/task-contract';
import { task, conversation, message, me } from '../fixtures/tasks';

describe('task API boundary validation', () => {
  it('reads generated-contract responses and rejects malformed nested data', () => {
    expect(parseTaskList({ items: [task] })).toEqual([task]);
    expect(parseConversationDetail(conversation)).toEqual(conversation);
    expect(parseMe(me)).toEqual(me);
    expect(parsePostMessageResponse({ message, run: null })).toEqual({ message, run: null });
    expect(() => parseMe({ ...me, ai_connection: { status: 'secret' } })).toThrow(TaskDecodeError);
    expect(() => parseConversationDetail({ ...conversation, active_run: {} })).toThrow(TaskDecodeError);
  });
  it.each(['complete', undefined, null, 1])('rejects unknown task status %s', status => {
    expect(() => parseTask({ ...task, status })).toThrow(TaskDecodeError);
  });
  it('rejects missing fields and malformed message pagination/author', () => {
    expect(() => parseTask({ id: 't1' })).toThrow(TaskDecodeError);
    expect(() => parseTaskList({ items: [null] })).toThrow(TaskDecodeError);
    expect(() => parseMessageList({ items: [{ ...message, author: { kind: 'tool' } }], next_after_seq: null })).toThrow(TaskDecodeError);
    expect(() => parseMessageList({ items: [message], next_after_seq: -1 })).toThrow(TaskDecodeError);
  });
});
