import type { components } from '../../api/schema';
import { next, type Next } from '../../lib/mvi';
export type Conversation = components['schemas']['Conversation'];
export type State = {
  readonly projectId: string;
  readonly request: number;
  readonly loading: boolean;
  readonly items: readonly Conversation[];
  readonly error: string | null;
  readonly title: string;
  readonly creating: { readonly title: string; readonly key: string } | null;
  readonly failedCreate: { readonly title: string; readonly key: string } | null;
  readonly createError: string | null;
  readonly createdId: string | null;
};
export type Intent =
  | { readonly type: 'load' }
  | { readonly type: 'loaded'; readonly request: number; readonly items: readonly Conversation[] }
  | { readonly type: 'failed'; readonly request: number; readonly error: string }
  | { readonly type: 'titleChanged'; readonly title: string }
  | { readonly type: 'create'; readonly key: string }
  | { readonly type: 'created'; readonly key: string; readonly conversation: Conversation }
  | { readonly type: 'createFailed'; readonly key: string; readonly error: string }
  | { readonly type: 'createdSelected' };
export type Effect = { readonly type: 'load'; readonly projectId: string; readonly request: number }
  | { readonly type: 'create'; readonly projectId: string; readonly title: string; readonly key: string };
export const initialState = (projectId: string): State => ({ projectId, request: 0, loading: true, items: [], error: null,
  title: '', creating: null, failedCreate: null, createError: null, createdId: null });
export function reducer(state: State, intent: Intent): Next<State, Effect> {
  switch (intent.type) {
    case 'load': {
      const request = state.request + 1;
      return next({ ...state, request, loading: true, error: null }, { type: 'load', projectId: state.projectId, request });
    }
    case 'loaded': return intent.request === state.request
      ? next({ ...state, items: intent.items, loading: false, error: null }) : next(state);
    case 'failed': return intent.request === state.request
      ? next({ ...state, loading: false, error: intent.error }) : next(state);
    case 'titleChanged': return next({ ...state, title: intent.title, createError: null });
    case 'create': {
      const title = state.title.trim();
      if (!title || state.creating) return next(state);
      const creating = state.failedCreate?.title === title ? state.failedCreate : { title, key: intent.key };
      return next({ ...state, creating, createError: null }, { type: 'create', projectId: state.projectId, ...creating });
    }
    case 'created': {
      if (state.creating?.key !== intent.key) return next(state);
      const request = state.request + 1;
      return next({ ...state, request, loading: true, title: state.title.trim() === state.creating.title ? '' : state.title,
        creating: null, failedCreate: null, createError: null, createdId: intent.conversation.id,
        items: [...state.items.filter(item => item.id !== intent.conversation.id), intent.conversation] },
      { type: 'load', projectId: state.projectId, request });
    }
    case 'createFailed': return state.creating?.key === intent.key
      ? next({ ...state, creating: null, failedCreate: state.creating, createError: intent.error }) : next(state);
    case 'createdSelected': return next({ ...state, createdId: null });
  }
}
/** Parent-first ordering; corrupt/cyclic relationships still render once, without recursion. */
export function treeRows(items: readonly Conversation[]): { readonly conversation: Conversation; readonly depth: number }[] {
  const rows: { conversation: Conversation; depth: number }[] = [];
  const seen = new Set<string>();
  const children = new Map<string | null, Conversation[]>();
  const ids = new Set(items.map((item) => item.id));
  for (const item of items) {
    const parent = item.parent_id && ids.has(item.parent_id) ? item.parent_id : null;
    children.set(parent, [...(children.get(parent) ?? []), item]);
  }
  const visit = (start: Conversation, depth: number) => {
    const stack = [{ conversation: start, depth }];
    while (stack.length) {
      const row = stack.pop()!;
      if (seen.has(row.conversation.id)) continue;
      seen.add(row.conversation.id);
      rows.push(row);
      for (const child of [...(children.get(row.conversation.id) ?? [])].reverse()) {
        stack.push({ conversation: child, depth: row.depth + 1 });
      }
    }
  };
  for (const item of children.get(null) ?? []) visit(item, 0);
  for (const item of items) if (!seen.has(item.id)) visit(item, 0);
  return rows;
}
