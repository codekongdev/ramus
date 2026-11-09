import { describe, expect, it } from 'vitest';
import {
  EventDecodeError,
  PROJECT_EVENT_TYPES,
  decodeProjectEvent,
  type ProjectEventType,
} from '../../src/lib/events';

const at = '2026-11-09T04:17:23Z';
const conversation = {
  id: 'c1',
  project_id: 'p1',
  parent_id: null,
  task_id: null,
  title: '멤버십 기능 설계',
  path: ['상위'],
  created_by: 'a1',
  created_at: at,
};

// One valid payload per event in contracts.md 4장.
const valid: Record<ProjectEventType, Record<string, unknown>> = {
  'member.joined': { project_id: 'p1', account: { id: 'a1', display_name: '메이슨' } },
  'conversation.created': { project_id: 'p1', conversation },
  'message.created': { conversation_id: 'c1', message_id: 'm1', seq: 3 },
  'run.updated': {
    conversation_id: 'c1',
    run: { id: 'r1', purpose: 'work', status: 'running', task_id: null, requested_by: 'a1' },
  },
  'task.updated': {
    source_conversation_id: 'c1',
    task: { id: 't1', title: '경쟁사 비교', status: 'ready', child_conversation_id: 'c2', result_id: null },
  },
  'resource.updated': { project_id: 'p1', resource_id: 's1', latest_revision_id: 'sr2', latest_number: 2 },
  'conversation_resources.updated': { conversation_id: 'c1' },
  'result.updated': { result_id: 'r1', task_id: 't1', draft_status: 'generating', latest_version: null },
  'conversation_inputs.updated': { conversation_id: 'c1' },
};

const encode = (data: Record<string, unknown>) => JSON.stringify({ ...data, occurred_at: at });

describe('PROJECT_EVENT_TYPES', () => {
  it('lists exactly the contract events', () => {
    expect([...PROJECT_EVENT_TYPES].sort()).toEqual(Object.keys(valid).sort());
  });
});

describe('decodeProjectEvent', () => {
  it.each(Object.entries(valid))('accepts a valid %s', (type, data) => {
    expect(decodeProjectEvent(type, encode(data))).toEqual({ type, data: { ...data, occurred_at: at } });
  });

  it('drops unknown fields', () => {
    const event = decodeProjectEvent(
      'message.created',
      encode({ ...valid['message.created'], body: '본문은 이벤트에 오지 않아야 함' }),
    );
    expect(event.data).not.toHaveProperty('body');
  });

  it('requires occurred_at', () => {
    expect(() =>
      decodeProjectEvent('conversation_inputs.updated', JSON.stringify({ conversation_id: 'c1' })),
    ).toThrow(/occurred_at/);
  });

  it.each([
    ['unknown type', 'share.created', encode({ conversation_id: 'c1' }), /not a known event/],
    ['invalid JSON', 'message.created', '{', /not valid JSON/],
    ['non-object data', 'message.created', '[]', /must be an object/],
    ['missing field', 'message.created', encode({ conversation_id: 'c1', seq: 1 }), /message_id/],
    ['non-integer seq', 'message.created', encode({ conversation_id: 'c1', message_id: 'm', seq: 1.5 }), /seq/],
    [
      'unknown enum value',
      'task.updated',
      encode({ ...valid['task.updated'], task: { ...(valid['task.updated'].task as object), status: 'done' } }),
      /task.status/,
    ],
    [
      'bad nested array item',
      'conversation.created',
      encode({ project_id: 'p1', conversation: { ...conversation, path: ['ok', 1] } }),
      /conversation.path\[1\]/,
    ],
  ])('rejects %s', (_label, type, raw, message) => {
    expect(() => decodeProjectEvent(type, raw)).toThrow(EventDecodeError);
    expect(() => decodeProjectEvent(type, raw)).toThrow(message);
  });

  it('does not treat inherited object keys as event types', () => {
    expect(() => decodeProjectEvent('toString', '{}')).toThrow(/not a known event/);
  });
});
