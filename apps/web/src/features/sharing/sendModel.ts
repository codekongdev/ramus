import { next, type Next } from '../../lib/mvi';
import type { ResultRevision } from '../../lib/api/result-contract';
import type { Conversation, ShareOutcomes } from './contract';
import { sharingMessages as m } from './messages';

export type SendTarget = { readonly projectId: string; readonly currentConversationId: string; readonly revision: ResultRevision };
export type SendMutation = { readonly key: string; readonly revisionId: string; readonly conversationIds: string[] };
export type SendState = {
  readonly target: SendTarget | null;
  readonly query: string;
  readonly matches: readonly Conversation[];
  readonly selected: readonly Conversation[];
  readonly loading: boolean;
  readonly request: number;
  readonly error: string | null;
  readonly mutation: SendMutation | null;
  readonly failedMutation: SendMutation | null;
  readonly notice: string | null;
  readonly noticeId: number;
};
export type SendEffect =
  | { readonly type: 'search'; readonly target: SendTarget; readonly query: string; readonly request: number }
  | { readonly type: 'send'; readonly mutation: SendMutation }
  | { readonly type: 'expireNotice'; readonly id: number };
export type SendIntent =
  | { readonly type: 'open'; readonly target: SendTarget }
  | { readonly type: 'back' }
  | { readonly type: 'query'; readonly query: string }
  | { readonly type: 'refresh' }
  | { readonly type: 'matches'; readonly request: number; readonly matches: Conversation[] }
  | { readonly type: 'searchFailed'; readonly request: number; readonly message: string }
  | { readonly type: 'toggle'; readonly conversation: Conversation }
  | { readonly type: 'send'; readonly key: string }
  | { readonly type: 'sent'; readonly key: string; readonly outcomes: ShareOutcomes }
  | { readonly type: 'sendFailed'; readonly key: string; readonly message: string }
  | { readonly type: 'dismissNotice'; readonly id: number };
export const initialSendState = (): SendState => ({ target: null, query: '', matches: [], selected: [], loading: false,
  request: 0, error: null, mutation: null, failedMutation: null, notice: null, noticeId: 0 });
const eligible = (target: SendTarget, item: Conversation) => item.project_id === target.projectId
  && item.id !== target.currentConversationId && item.id !== target.revision.source.conversation_id;
function search(state: SendState): Next<SendState, SendEffect> {
  if (!state.target) return next(state);
  const request = state.request + 1;
  return next({ ...state, loading: true, request, error: null }, { type: 'search', target: state.target, query: state.query, request });
}
export function sendReducer(state: SendState, intent: SendIntent): Next<SendState, SendEffect> {
  switch (intent.type) {
    case 'open': return state.mutation ? next(state) : search({ ...initialSendState(), request: state.request, noticeId: state.noticeId, target: intent.target });
    case 'back': return state.mutation ? next(state) : next({ ...state, target: null, request: state.request + 1, error: null });
    case 'query': return state.mutation ? next(state) : search({ ...state, query: intent.query, matches: [] });
    case 'refresh': return search(state);
    case 'matches': {
      if (!state.target || intent.request !== state.request) return next(state);
      const target = state.target;
      const ids = new Set<string>();
      const matches = intent.matches.filter(item => {
        if (!eligible(target, item) || ids.has(item.id)) return false;
        ids.add(item.id);
        return true;
      });
      return next({ ...state, matches, loading: false, error: null });
    }
    case 'searchFailed': return intent.request === state.request && state.target ? next({ ...state, loading: false, error: intent.message }) : next(state);
    case 'toggle': {
      if (!state.target || state.mutation || !eligible(state.target, intent.conversation)) return next(state);
      const found = state.selected.some(item => item.id === intent.conversation.id);
      if (!found && state.selected.length >= 20) return next(state);
      const selected = found ? state.selected.filter(item => item.id !== intent.conversation.id) : [...state.selected, intent.conversation];
      return next({ ...state, selected, error: null, failedMutation: null });
    }
    case 'send': {
      if (!state.target || state.mutation || state.selected.length === 0) return next(state);
      const mutation = state.failedMutation ?? { key: intent.key, revisionId: state.target.revision.id, conversationIds: state.selected.map(item => item.id) };
      return next({ ...state, mutation, error: null }, { type: 'send', mutation });
    }
    case 'sent': {
      if (state.mutation?.key !== intent.key) return next(state);
      const count = intent.outcomes.items.filter(item => item.outcome === 'linked' || item.outcome === 'replaced').length;
      const notice = count ? m.sent(count) : intent.outcomes.items.some(item => item.outcome === 'kept_newer') ? m.keptNewer : m.unchanged;
      const noticeId = state.noticeId + 1;
      return next({ ...state, target: null, mutation: null, failedMutation: null, notice, noticeId, request: state.request + 1 }, { type: 'expireNotice', id: noticeId });
    }
    case 'sendFailed': return state.mutation?.key === intent.key ? next({ ...state, error: intent.message, failedMutation: state.mutation, mutation: null }) : next(state);
    case 'dismissNotice': return state.noticeId === intent.id ? next({ ...state, notice: null }) : next(state);
  }
}
