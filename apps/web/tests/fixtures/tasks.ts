import type { components } from '../../src/api/schema';
type S = components['schemas'];
export const createdAt = '2026-11-09T01:00:00Z';
export const me: S['Me'] = {
  account: { id: 'u1', email: 'member@example.test', display_name: '민서' },
  ai_connection: { status: 'connected' }, default_project_id: 'p1',
};
export const task: S['Task'] = {
  id: 't1', title: '경쟁사 분석', goal: '멤버십 혜택과 반품 예외를 비교해 주세요.',
  source_conversation_id: 'c1', child_conversation_id: 'child1', requested_by: 'u1',
  status: 'pending', result_id: null, error: null, created_at: createdAt, started_at: null, finished_at: null,
};
export const conversation: S['ConversationDetail'] = {
  id: 'child1', project_id: 'p1', parent_id: 'c1', task_id: 't1', title: task.title,
  path: ['서비스 방향'], created_by: 'u1', created_at: createdAt, active_run: null,
};
export const parent: S['Conversation'] = { ...conversation, id: 'c1', title: '서비스 방향', parent_id: null, task_id: null, path: [] };
export const message: S['Message'] = {
  id: 'm1', conversation_id: 'child1', seq: 1, author: { kind: 'ai', account_id: null, display_name: 'AI' },
  body: '쇼핑몰 A는 반품 시 사용한 혜택을 회수합니다.', requested_by: 'u1', run_id: 'run1',
  is_example: false, created_at: createdAt,
};
