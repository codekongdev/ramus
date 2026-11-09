import type { components } from '../../api/schema';
import type { ProjectEvent } from '../../lib/events';
import { next, type Next } from '../../lib/mvi';
import { conversationMessages as messages } from './messages';

type Schemas = components['schemas'];
export type Conversation = Schemas['ConversationDetail'];
export type Message = Schemas['Message'];
export type Run = Schemas['Run'];
export type Mutation = { readonly key: string; readonly body: string; readonly runVersion: number };
export type State = {
  readonly projectId: string;
  readonly conversationId: string;
  readonly conversation: Conversation | null;
  readonly messages: readonly Message[];
  readonly draft: string;
  readonly loading: boolean;
  readonly request: number;
  readonly error: string | null;
  readonly mutation: Mutation | null;
  readonly failedMutation: Mutation | null;
  readonly mutationError: string | null;
  readonly liveRunStatus: Run['status'] | null;
  /** Changes whenever a newer server run state arrives, including a send acknowledgement. */
  readonly runVersion: number;
};
export type Intent =
  | { readonly type: 'load' | 'refresh' }
  | { readonly type: 'loaded'; readonly conversationId: string; readonly request: number; readonly conversation: Conversation; readonly messages: readonly Message[] }
  | { readonly type: 'loadFailed'; readonly conversationId: string; readonly request: number; readonly message: string }
  | { readonly type: 'draftChanged'; readonly draft: string }
  | { readonly type: 'submit'; readonly key: string }
  | { readonly type: 'mutationSucceeded'; readonly conversationId: string; readonly key: string; readonly message: Message; readonly run: Run | null }
  | { readonly type: 'mutationFailed'; readonly conversationId: string; readonly key: string; readonly message: string }
  | { readonly type: 'serverEvent'; readonly event: ProjectEvent };
export type Effect =
  | { readonly type: 'load'; readonly projectId: string; readonly conversationId: string; readonly request: number }
  | { readonly type: 'send'; readonly conversationId: string; readonly mutation: Mutation };

export const initialState = (projectId: string, conversationId: string): State => ({
  projectId, conversationId, conversation: null, messages: [], draft: '', loading: false,
  request: 0, error: null, mutation: null, failedMutation: null, mutationError: null,
  liveRunStatus: null, runVersion: 0,
});
export const mentionsAi = (body: string): boolean => /@ai/i.test(body);
export const hasActiveRun = (state: State): boolean => {
  const status = state.liveRunStatus ?? state.conversation?.active_run?.status;
  return status === 'pending' || status === 'running';
};
/** Messages are append-only; identities and ordering always come from the server. */
export function mergeMessages(items: readonly Message[]): Message[] {
  return [...new Map(items.map(item => [item.id, item])).values()]
    .sort((a, b) => a.seq - b.seq || a.id.localeCompare(b.id));
}
function refresh(state: State): Next<State, Effect> {
  const request = state.request + 1;
  return next({ ...state, request, loading: true, error: null }, {
    type: 'load', projectId: state.projectId, conversationId: state.conversationId, request,
  });
}
export function reducer(state: State, intent: Intent): Next<State, Effect> {
  switch (intent.type) {
    case 'load':
    case 'refresh': return refresh(state);
    case 'loaded':
      if (intent.conversationId !== state.conversationId || intent.request !== state.request) return next(state);
      return next({ ...state, conversation: intent.conversation, loading: false, error: null,
        // A read started before a POST acknowledgement may omit that newly accepted message.
        messages: mergeMessages([...state.messages, ...intent.messages]), liveRunStatus: null });
    case 'loadFailed':
      if (intent.conversationId !== state.conversationId || intent.request !== state.request) return next(state);
      return next({ ...state, loading: false, error: intent.message });
    case 'draftChanged': return next({ ...state, draft: intent.draft, mutationError: null });
    case 'submit': {
      const body = state.draft;
      if (!state.conversation || !body.trim() || state.mutation) return next(state);
      if (mentionsAi(body) && hasActiveRun(state)) return next({ ...state, mutationError: messages.aiBusy });
      const key = state.failedMutation?.body === body ? state.failedMutation.key : intent.key;
      const mutation: Mutation = { body, key, runVersion: state.runVersion };
      return next({ ...state, mutation, mutationError: null }, { type: 'send', conversationId: state.conversationId, mutation });
    }
    case 'mutationSucceeded': {
      if (intent.conversationId !== state.conversationId || intent.key !== state.mutation?.key) return next(state);
      const mutation = state.mutation;
      // A run may finish via SSE before its POST responds. Do not resurrect its pending state.
      const applyRun = intent.run !== null && mutation.runVersion === state.runVersion;
      return refresh({ ...state,
        conversation: applyRun && state.conversation ? { ...state.conversation, active_run: intent.run } : state.conversation,
        liveRunStatus: applyRun ? intent.run!.status : state.liveRunStatus,
        runVersion: state.runVersion + 1,
        messages: mergeMessages([...state.messages, intent.message]),
        draft: state.draft === mutation.body ? '' : state.draft,
        mutation: null, failedMutation: null, mutationError: null,
      });
    }
    case 'mutationFailed':
      if (intent.conversationId !== state.conversationId || intent.key !== state.mutation?.key) return next(state);
      return refresh({ ...state, mutation: null, failedMutation: state.mutation, mutationError: intent.message });
    case 'serverEvent': {
      const event = intent.event;
      if ((event.type !== 'message.created' && event.type !== 'run.updated') || event.data.conversation_id !== state.conversationId) return next(state);
      return refresh(event.type === 'run.updated'
        ? { ...state, liveRunStatus: event.data.run.status, runVersion: state.runVersion + 1 }
        : state);
    }
  }
}
