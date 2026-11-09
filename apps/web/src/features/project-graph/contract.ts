import type { components } from '../../api/schema';

type Schemas = components['schemas'];
export type ProjectGraph = Schemas['ProjectGraph'];
export type GraphNode = Schemas['GraphNode'];
export type GraphEdge = Schemas['GraphEdge'];
const statuses = ['pending', 'running', 'ready', 'failed', 'cancelled'] as const;
const invalid = (): never => { throw new Error('Invalid project graph'); };
const record = (v: unknown): Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : invalid();
const text = (v: unknown): string => typeof v === 'string' && v.trim() ? v : invalid();
const nullableText = (v: unknown): string | null => v === null ? null : text(v);
export function parseProjectGraph(value: unknown): ProjectGraph {
  const data = record(value);
  if (!Array.isArray(data.nodes) || !Array.isArray(data.edges)) return invalid();
  const nodes: GraphNode[] = data.nodes.map((value: unknown) => {
    const n = record(value);
    const status = n.task_status;
    if (status !== null && (typeof status !== 'string' || !statuses.includes(status as typeof statuses[number]))) return invalid();
    return { conversation_id: text(n.conversation_id), title: text(n.title), parent_id: nullableText(n.parent_id), task_status: status as GraphNode['task_status'] };
  });
  const ids = new Set(nodes.map(n => n.conversation_id));
  if (ids.size !== nodes.length) return invalid();
  const edges: GraphEdge[] = data.edges.map((value: unknown) => {
    const edge = record(value);
    if (edge.kind !== 'branch' && edge.kind !== 'uses_result') return invalid();
    const from = text(edge.from), to = text(edge.to);
    if (!ids.has(from) || !ids.has(to)) return invalid();
    return { kind: edge.kind, from, to };
  });
  return { nodes, edges };
}
