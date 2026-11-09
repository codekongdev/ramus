import type { components } from '../../api/schema';
import { next, type Next } from '../../lib/mvi';
export type Conversation = components['schemas']['Conversation'];
export type State = {
  readonly projectId: string;
  readonly request: number;
  readonly loading: boolean;
  readonly items: readonly Conversation[];
  readonly error: string | null;
};
export type Intent =
  | { readonly type: 'load' }
  | { readonly type: 'loaded'; readonly request: number; readonly items: readonly Conversation[] }
  | { readonly type: 'failed'; readonly request: number; readonly error: string };
export type Effect = { readonly type: 'load'; readonly projectId: string; readonly request: number };
export const initialState = (projectId: string): State => ({ projectId, request: 0, loading: true, items: [], error: null });
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
