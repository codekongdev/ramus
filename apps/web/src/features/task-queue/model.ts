import type { components } from '../../api/schema';
import type { ProjectEvent } from '../../lib/events';
import { next, type Next } from '../../lib/mvi';

type Task = components['schemas']['Task'];
export type QueueTask = Pick<Task, 'id' | 'title' | 'status' | 'child_conversation_id' | 'result_id'>;

export interface TaskQueueState {
  readonly conversationId: string | null;
  readonly items: readonly QueueTask[];
  readonly loading: boolean;
  readonly error: string | null;
  readonly requestId: number;
  readonly eventRevision: number;
  /** Only events received after a read starts override that read's snapshot. */
  readonly changes: Readonly<Record<string, { readonly revision: number; readonly task: QueueTask }>>;
}

export type TaskQueueIntent =
  | { readonly type: 'selectConversation'; readonly conversationId: string }
  | { readonly type: 'refresh' }
  | { readonly type: 'serverEvent'; readonly event: ProjectEvent }
  | { readonly type: 'loaded'; readonly conversationId: string; readonly requestId: number; readonly eventRevision: number; readonly items: readonly Task[] }
  | { readonly type: 'failed'; readonly conversationId: string; readonly requestId: number; readonly message: string };

export interface TaskQueueEffect {
  readonly type: 'load';
  readonly conversationId: string;
  readonly requestId: number;
  readonly eventRevision: number;
}

export const initialTaskQueueState: TaskQueueState = {
  conversationId: null, items: [], loading: false, error: null,
  requestId: 0, eventRevision: 0, changes: {},
};

function load(state: TaskQueueState): Next<TaskQueueState, TaskQueueEffect> {
  if (!state.conversationId) return next(state);
  const requestId = state.requestId + 1;
  return next(
    { ...state, requestId, loading: true, error: null },
    { type: 'load', conversationId: state.conversationId, requestId, eventRevision: state.eventRevision },
  );
}

export function taskQueueReducer(state: TaskQueueState, intent: TaskQueueIntent): Next<TaskQueueState, TaskQueueEffect> {
  switch (intent.type) {
    case 'selectConversation':
      if (state.conversationId === intent.conversationId) return next(state);
      return load({ ...initialTaskQueueState, conversationId: intent.conversationId, requestId: state.requestId });
    case 'refresh':
      return load(state);
    case 'serverEvent': {
      const { event } = intent;
      if (event.type !== 'task.updated' || event.data.source_conversation_id !== state.conversationId) return next(state);
      const task = event.data.task;
      const eventRevision = state.eventRevision + 1;
      const exists = state.items.some((item) => item.id === task.id);
      return next({
        ...state,
        eventRevision,
        items: exists ? state.items.map((item) => item.id === task.id ? task : item) : [...state.items, task],
        changes: { ...state.changes, [task.id]: { revision: eventRevision, task } },
      });
    }
    case 'loaded': {
      if (intent.conversationId !== state.conversationId || intent.requestId !== state.requestId) return next(state);
      // An SSE update can arrive while the server's earlier GET snapshot is in flight.
      const items: QueueTask[] = intent.items.filter((task) => task.source_conversation_id === state.conversationId);
      for (const change of Object.values(state.changes)) {
        if (change.revision <= intent.eventRevision) continue;
        const index = items.findIndex((task) => task.id === change.task.id);
        if (index === -1) items.push(change.task);
        else items[index] = change.task;
      }
      return next({ ...state, items, loading: false, error: null });
    }
    case 'failed':
      if (intent.conversationId !== state.conversationId || intent.requestId !== state.requestId) return next(state);
      return next({ ...state, loading: false, error: intent.message });
  }
}
