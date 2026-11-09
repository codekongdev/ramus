import type { components } from '../../../src/api/schema';
import type { TaskModalState } from '../../../src/features/task-modal/model';
import { initialTaskModalState } from '../../../src/features/task-modal/model';
export const date = '2026-11-09T01:00:00Z';
export const task: components['schemas']['Task'] = { id: 'task-1', title: '경쟁사 비교', goal: '혜택과 반품 정책 비교', source_conversation_id: 'parent-1', child_conversation_id: 'child-1', requested_by: 'account-1', status: 'ready', result_id: null, error: null, created_at: date, started_at: date, finished_at: date };
export const me: components['schemas']['Me'] = { account: { id: 'account-1', email: 'example@example.test', display_name: '테스터' }, ai_connection: { status: 'connected' }, default_project_id: 'project-1' };
export const conversation: components['schemas']['ConversationDetail'] = { id: 'child-1', project_id: 'project-1', parent_id: 'parent-1', task_id: 'task-1', title: task.title, path: ['멤버십 기획'], created_by: me.account.id, created_at: date, active_run: null };
export const message = (seq = 1, overrides: Partial<components['schemas']['Message']> = {}): components['schemas']['Message'] => ({ id: `message-${seq}`, conversation_id: 'child-1', seq, author: { kind: 'human', account_id: 'account-1', display_name: '테스터' }, body: `메시지 ${seq}`, requested_by: null, run_id: null, is_example: false, created_at: date, ...overrides });
export const readyState = (overrides: Partial<TaskModalState> = {}): TaskModalState => ({ ...initialTaskModalState(task.id), task, me, conversation, messages: [message()], ...overrides });
