import type { Result, ResultRevision } from '../src/features/results/contract';
import { task, createdAt } from './fixtures/tasks';

export const revision: ResultRevision = {
  id: 'revision1', result_id: 'result1', version: 1, title: task.title, conclusion: '저장된 결론', saved_by: 'u1', created_at: createdAt,
  source: { conversation_id: 'child1', message_from_seq: 1, message_to_seq: 3, resource_revision_ids: ['resource1'], input_result_revision_ids: [], run_id: 'summary1' },
};
export const result: Result = {
  id: 'result1', project_id: 'p1', source_conversation_id: 'child1', source_task_id: task.id, title: task.title,
  latest_version: null, latest_revision_id: null, revisions: [],
  draft: { status: 'ready', conclusion: '생성된 결론', base_version: 0, run_id: 'summary1', error: null, updated_at: createdAt },
};
