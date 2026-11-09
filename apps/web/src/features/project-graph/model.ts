import { next, type Next } from '../../lib/mvi';
import type { ProjectGraph } from './contract';
import type { components } from '../../api/schema';
type Conversation = components['schemas']['Conversation'];
export type State = { readonly projectId: string; readonly request: number; readonly status: 'loading' | 'ready' | 'failed'; readonly graph: ProjectGraph | null; readonly conversations: readonly Conversation[]; readonly error: string | null };
export type Intent = { readonly type: 'refresh' } | { readonly type: 'loaded'; readonly request: number; readonly graph: ProjectGraph; readonly conversations: readonly Conversation[] } | { readonly type: 'failed'; readonly request: number; readonly error: string };
export type Effect = { readonly projectId: string; readonly request: number };
export const initialState = (projectId: string): State => ({ projectId, request: 0, status: 'loading', graph: null, conversations: [], error: null });
export function reducer(state: State, intent: Intent): Next<State, Effect> {
  switch (intent.type) {
    case 'refresh': { const request = state.request + 1; return next({ ...state, request, status: 'loading', error: null }, { projectId: state.projectId, request }); }
    case 'loaded': return intent.request === state.request ? next({ ...state, status: 'ready', graph: intent.graph, conversations: intent.conversations, error: null }) : next(state);
    case 'failed': return intent.request === state.request ? next({ ...state, status: 'failed', graph: null, conversations: [], error: intent.error }) : next(state);
  }
}

/** Each conversation has a stable column from its branch depth and a unique row. */
export function layoutGraph(graph: ProjectGraph) {
  const nodes = new Map(graph.nodes.map(node => [node.conversation_id, node]));
  const depthOf = (id: string) => {
    let depth = 0, current = nodes.get(id); const seen = new Set<string>([id]);
    while (current?.parent_id && nodes.has(current.parent_id) && !seen.has(current.parent_id)) {
      seen.add(current.parent_id); depth++; current = nodes.get(current.parent_id);
    }
    return depth;
  };
  const ordered = [...graph.nodes].sort((a, b) => depthOf(a.conversation_id) - depthOf(b.conversation_id) || a.title.localeCompare(b.title) || a.conversation_id.localeCompare(b.conversation_id));
  const positions = new Map(ordered.map((node, row) => [node.conversation_id, { x: 24 + depthOf(node.conversation_id) * 260, y: 24 + row * 104 }]));
  return { ordered, positions, width: Math.max(300, ...[...positions.values()].map(p => p.x + 224)), height: Math.max(140, ordered.length * 104 + 24) };
}

/** Separate conclusion use from a branch even when the endpoints are reversed. */
export function usageEdgePath(from: { readonly x: number; readonly y: number }, to: { readonly x: number; readonly y: number }): string {
  const x1 = from.x + 100, y1 = from.y + 38, x2 = to.x + 100, y2 = to.y + 38;
  const dx = x2 - x1, dy = y2 - y1, length = Math.hypot(dx, dy);
  if (length === 0) return `M ${x1} ${y1} C ${x1 + 150} ${y1 - 100}, ${x1 + 150} ${y1 + 100}, ${x1} ${y1}`;
  const offset = 48;
  const cx = (x1 + x2) / 2 - dy / length * offset;
  const cy = (y1 + y2) / 2 + dx / length * offset;
  return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
}
