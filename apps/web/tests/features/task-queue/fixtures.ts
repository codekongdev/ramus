import type { components } from '../../../src/api/schema';
import type { ProjectEventOf } from '../../../src/lib/events';

export function task(overrides: Partial<components['schemas']['Task']> = {}): components['schemas']['Task'] {
  return {
    id: 'task-1', title: '경쟁사 비교', goal: '멤버십 정책 비교', source_conversation_id: 'parent-1',
    child_conversation_id: 'child-1', requested_by: 'account-1', status: 'pending', result_id: null,
    error: null, created_at: '2026-11-09T00:00:00Z', started_at: null, finished_at: null, ...overrides,
  };
}

export function taskEvent(overrides: Partial<components['schemas']['Task']> = {}): ProjectEventOf<'task.updated'> {
  const value = task(overrides);
  return {
    type: 'task.updated',
    data: {
      source_conversation_id: value.source_conversation_id, occurred_at: '2026-11-09T00:00:00Z',
      task: { id: value.id, title: value.title, status: value.status, child_conversation_id: value.child_conversation_id, result_id: value.result_id },
    },
  };
}
