import type { ProjectEvent } from '../../lib/events';
import { next, type Next } from '../../lib/mvi';
import type { ConclusionRevision } from '../../lib/api/result-contract';
import type { ConversationInput } from './contract';

export type ReceivedState = {
  readonly conversationId: string;
  readonly items: readonly ConversationInput[];
  readonly loading: boolean;
  readonly request: number;
  readonly error: string | null;
};
export type ReceivedEffect = { readonly type: 'load'; readonly conversationId: string; readonly request: number };
export type ReceivedIntent =
  | { readonly type: 'select'; readonly conversationId: string }
  | { readonly type: 'refresh' }
  | { readonly type: 'loaded'; readonly conversationId: string; readonly request: number; readonly items: ConversationInput[] }
  | { readonly type: 'failed'; readonly conversationId: string; readonly request: number; readonly message: string }
  | { readonly type: 'event'; readonly event: ProjectEvent };
export const initialReceivedState = (conversationId: string): ReceivedState => ({ conversationId, items: [], loading: false, request: 0, error: null });
function load(state: ReceivedState): Next<ReceivedState, ReceivedEffect> {
  const request = state.request + 1;
  return next({ ...state, request, loading: true }, { type: 'load', conversationId: state.conversationId, request });
}
export function receivedReducer(state: ReceivedState, intent: ReceivedIntent): Next<ReceivedState, ReceivedEffect> {
  switch (intent.type) {
    case 'select': return load(intent.conversationId === state.conversationId ? state : { ...initialReceivedState(intent.conversationId), request: state.request });
    case 'refresh': return load(state);
    case 'loaded': return intent.conversationId === state.conversationId && intent.request === state.request ? next({ ...state, loading: false, items: intent.items, error: null }) : next(state);
    case 'failed': return intent.conversationId === state.conversationId && intent.request === state.request ? next({ ...state, loading: false, error: intent.message }) : next(state);
    case 'event': {
      const event = intent.event;
      return (event.type === 'conversation_inputs.updated' && event.data.conversation_id === state.conversationId)
        || (event.type === 'result.updated' && state.items.some(item => item.result_id === event.data.result_id)) ? load(state) : next(state);
    }
  }
}
export type RevisionState = { readonly input: ConversationInput; readonly revision: ConclusionRevision | null; readonly loading: boolean; readonly error: string | null; readonly request: number };
export type RevisionEffect = { readonly type: 'load'; readonly input: ConversationInput; readonly request: number };
export type RevisionIntent = { readonly type: 'refresh' }
  | { readonly type: 'loaded'; readonly request: number; readonly revision: ConclusionRevision }
  | { readonly type: 'failed'; readonly request: number; readonly message: string };
export const initialRevisionState = (input: ConversationInput): RevisionState => ({ input, revision: null, loading: false, error: null, request: 0 });
export function revisionReducer(state: RevisionState, intent: RevisionIntent): Next<RevisionState, RevisionEffect> {
  if (intent.type === 'refresh') {
    const request = state.request + 1;
    return next({ ...state, loading: true, error: null, request }, { type: 'load', input: state.input, request });
  }
  if (intent.request !== state.request) return next(state);
  return intent.type === 'loaded' ? next({ ...state, revision: intent.revision, loading: false, error: null }) : next({ ...state, loading: false, error: intent.message });
}
