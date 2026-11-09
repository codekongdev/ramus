import type { components } from '../../api/schema';
import type { ProjectEvent } from '../../lib/events';
import { next, type Next } from '../../lib/mvi';
import { taskModalMessages as messages } from './messages';

type Schemas = components['schemas'];
export type Task = Schemas['Task'];
export type Message = Schemas['Message'];
export type Run = Schemas['Run'];
export type Mutation = { readonly kind: 'send' | 'cancel' | 'retry'; readonly key: string; readonly body?: string };
export type TaskModalState = {
  readonly taskId: string;
  readonly task: Task | null;
  readonly conversation: Schemas['ConversationDetail'] | null;
  readonly me: Schemas['Me'] | null;
  readonly messages: readonly Message[];
  readonly liveRunStatus: Run['status'] | null;
  readonly draft: string;
  readonly loading: boolean;
  readonly request: number;
  readonly error: string | null;
  readonly mutationError: string | null;
  readonly mutation: Mutation | null;
  readonly failedMutation: Mutation | null;
};
export type TaskModalEffect =
  | { readonly type: 'load'; readonly taskId: string; readonly request: number }
  | { readonly type: 'mutate'; readonly task: Task; readonly mutation: Mutation };
export type TaskModalIntent =
  | { readonly type: 'select'; readonly taskId: string }
  | { readonly type: 'refresh' }
  | { readonly type: 'loaded'; readonly taskId: string; readonly request: number; readonly task: Task; readonly conversation: Schemas['ConversationDetail']; readonly me: Schemas['Me']; readonly messages: readonly Message[] }
  | { readonly type: 'loadFailed'; readonly taskId: string; readonly request: number; readonly message: string }
  | { readonly type: 'draftChanged'; readonly draft: string }
  | { readonly type: 'submit'; readonly key: string }
  | { readonly type: 'action'; readonly kind: 'cancel' | 'retry'; readonly key: string }
  | { readonly type: 'mutationSucceeded'; readonly taskId: string; readonly key: string; readonly task?: Task; readonly message?: Message; readonly run?: Run | null }
  | { readonly type: 'mutationFailed'; readonly taskId: string; readonly key: string; readonly message: string }
  | { readonly type: 'serverEvent'; readonly event: ProjectEvent };

export const initialTaskModalState = (taskId: string): TaskModalState => ({ taskId, task: null, conversation: null, me: null, messages: [], liveRunStatus: null, draft: '', loading: false, request: 0, error: null, mutationError: null, mutation: null, failedMutation: null });
export const mentionsAi = (body: string): boolean => /@ai/i.test(body);
export const isActive = (status?: string): boolean => status === 'pending' || status === 'running';
export const hasActiveRun = (state: TaskModalState): boolean => isActive(state.task?.status) || isActive(state.liveRunStatus ?? state.conversation?.active_run?.status);
export function mergeMessages(messages: readonly Message[]): Message[] {
  return [...new Map(messages.map(message => [message.id, message])).values()].sort((a, b) => a.seq - b.seq || a.id.localeCompare(b.id));
}
function refresh(state: TaskModalState): Next<TaskModalState, TaskModalEffect> {
  const request = state.request + 1;
  return next({ ...state, loading: true, error: null, request }, { type: 'load', taskId: state.taskId, request });
}
export function taskModalReducer(state: TaskModalState, intent: TaskModalIntent): Next<TaskModalState, TaskModalEffect> {
  switch (intent.type) {
    case 'select': return intent.taskId === state.taskId ? refresh(state) : refresh({ ...initialTaskModalState(intent.taskId), request: state.request });
    case 'refresh': return refresh(state);
    case 'loaded':
      if (intent.taskId !== state.taskId || intent.request !== state.request) return next(state);
      return next({ ...state, task: intent.task, conversation: intent.conversation, me: intent.me, messages: mergeMessages(intent.messages), liveRunStatus: null, loading: false, error: null });
    case 'loadFailed':
      if (intent.taskId !== state.taskId || intent.request !== state.request) return next(state);
      return next({ ...state, loading: false, error: intent.message });
    case 'draftChanged': return next({ ...state, draft: intent.draft, mutationError: null, failedMutation: null });
    case 'submit': {
      const body = state.draft.trim();
      if (!state.task || !body || state.mutation) return next(state);
      if (mentionsAi(body) && hasActiveRun(state)) return next({ ...state, mutationError: messages.aiBusy });
      const mutation: Mutation = state.failedMutation?.kind === 'send' && state.failedMutation.body === body ? state.failedMutation : { kind: 'send', body, key: intent.key };
      return next({ ...state, mutation, mutationError: null }, { type: 'mutate', task: state.task, mutation });
    }
    case 'action': {
      if (!state.task || state.mutation || state.task.requested_by !== state.me?.account.id) return next(state);
      if (intent.kind === 'cancel' ? !isActive(state.task.status) : !['failed', 'cancelled'].includes(state.task.status)) return next(state);
      const mutation: Mutation = state.failedMutation?.kind === intent.kind ? state.failedMutation : { kind: intent.kind, key: intent.key };
      return next({ ...state, mutation, mutationError: null }, { type: 'mutate', task: state.task, mutation });
    }
    case 'mutationSucceeded': {
      if (state.taskId !== intent.taskId || state.mutation?.key !== intent.key) return next(state);
      const sentBody = state.mutation.kind === 'send' ? state.mutation.body : undefined;
      return refresh({ ...state, task: intent.task ?? state.task, messages: intent.message ? mergeMessages([...state.messages, intent.message]) : state.messages,
        conversation: state.conversation && intent.run !== undefined ? { ...state.conversation, active_run: intent.run } : state.conversation,
        liveRunStatus: intent.run?.status ?? state.liveRunStatus,
        draft: sentBody !== undefined && state.draft.trim() === sentBody ? '' : state.draft, mutation: null, failedMutation: null, mutationError: null });
    }
    case 'mutationFailed':
      if (state.taskId !== intent.taskId || state.mutation?.key !== intent.key) return next(state);
      return next({ ...state, mutation: null, failedMutation: state.mutation, mutationError: intent.message });
    case 'serverEvent': {
      const event = intent.event;
      const relevant = event.type === 'task.updated' ? event.data.task.id === state.taskId
        : event.type === 'result.updated' ? event.data.task_id === state.taskId
        : (event.type === 'message.created' || event.type === 'run.updated') && event.data.conversation_id === state.task?.child_conversation_id;
      if (!relevant) return next(state);
      const task = event.type === 'task.updated' && state.task ? { ...state.task, ...event.data.task } : state.task;
      // Mark a newly started child run immediately, before the refresh returns.
      const liveRunStatus = event.type === 'run.updated' ? event.data.run.status : state.liveRunStatus;
      return refresh({ ...state, task, liveRunStatus });
    }
  }
}
