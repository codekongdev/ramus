import { describe, expect, it, vi } from 'vitest';
import type { paths } from '../../src/api/schema';
import { createApiClient, SYSTEM_ERROR_MESSAGE } from '../../src/lib/api';
import { parseProjectGraph } from '../../src/features/project-graph/contract';
import { makeEffects } from '../../src/features/project-graph/effects';
import { initialState, layoutGraph, reducer, usageEdgePath } from '../../src/features/project-graph/model';

const graph = { nodes: [
  { conversation_id: 'root', title: '기획', parent_id: null, task_status: null },
  { conversation_id: 'child', title: '분석', parent_id: 'root', task_status: 'ready' },
], edges: [{ kind: 'branch', from: 'root', to: 'child' }, { kind: 'uses_result', from: 'child', to: 'root' }] };
const conversation = { id: 'child', project_id: 'project-1', parent_id: 'root', task_id: 'task-1', title: '분석', path: ['root', 'child'], created_by: 'account-1', created_at: '2026-11-09T00:00:00Z' };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const client = (fetch: typeof globalThis.fetch) => createApiClient<paths>({ baseUrl: 'http://localhost', fetch });

describe('project graph boundary and layout', () => {
  it('preserves both relationship kinds and gives each node a distinct position', () => {
    const parsed = parseProjectGraph(graph), layout = layoutGraph(parsed);
    expect(parsed.edges.map(edge => edge.kind)).toEqual(['branch', 'uses_result']);
    expect(layout.positions.get('child')!.x).toBeGreaterThan(layout.positions.get('root')!.x);
    expect(layout.positions.get('child')!.y).not.toBe(layout.positions.get('root')!.y);
  });
  it('separates a reverse conclusion-use edge from the branch at the midpoint', () => {
    const layout = layoutGraph(parseProjectGraph(graph));
    const parent = layout.positions.get('root')!, child = layout.positions.get('child')!;
    const coordinates = usageEdgePath(child, parent).match(/-?\d+(?:\.\d+)?/g)!.map(Number);
    const [x1, y1, cx, cy, x2, y2] = coordinates;
    // A quadratic curve reaches halfway between its control point and the straight midpoint.
    const straightMidpoint = [(x1 + x2) / 2, (y1 + y2) / 2];
    const curveMidpoint = [(x1 + 2 * cx + x2) / 4, (y1 + 2 * cy + y2) / 4];
    expect(Math.hypot(curveMidpoint[0] - straightMidpoint[0], curveMidpoint[1] - straightMidpoint[1])).toBeGreaterThan(20);
    expect(usageEdgePath(parent, child)).not.toBe(usageEdgePath(child, parent));
  });
  it.each([
    { ...graph, nodes: [graph.nodes[0], graph.nodes[0]] },
    { ...graph, nodes: [{ ...graph.nodes[0], task_status: 'unknown' }] },
    { ...graph, edges: [{ kind: 'branch', from: 'root', to: 'missing' }] },
    { ...graph, edges: [{ kind: 'unknown', from: 'root', to: 'child' }] },
  ])('rejects invalid responses', value => expect(() => parseProjectGraph(value)).toThrow());
  it('does not allow an older refresh to replace the newer data', () => {
    const first = reducer(initialState('project-1'), { type: 'refresh' }).state;
    const second = reducer(first, { type: 'refresh' }).state;
    const loaded = reducer(second, { type: 'loaded', request: 2, graph: parseProjectGraph(graph), conversations: [] }).state;
    expect(reducer(loaded, { type: 'failed', request: 1, error: 'late' }).state).toBe(loaded);
  });
});
describe('project graph requests', () => {
  it('reads the graph and conversation task identifiers for the selected project', async () => {
    const requests: Request[] = [];
    const api = client(async request => { requests.push(request as Request); return json((request as Request).url.endsWith('/graph') ? graph : { items: [conversation] }); });
    const dispatch = vi.fn();
    await makeEffects(api)({ projectId: 'project-1', request: 1 }, dispatch, new AbortController().signal);
    expect(requests.map(r => [r.method, new URL(r.url).pathname]).sort()).toEqual([
      ['GET', '/api/projects/project-1/conversations'], ['GET', '/api/projects/project-1/graph'],
    ]);
    expect(dispatch).toHaveBeenCalledExactlyOnceWith({ type: 'loaded', request: 1, graph, conversations: [conversation] });
  });
  it('rejects malformed graph or conversations from another project', async () => {
    for (const [g, c] of [[{ ...graph, edges: [{ kind: 'branch', from: 'root', to: 'missing' }] }, conversation], [graph, { ...conversation, project_id: 'other' }]] as const) {
      const dispatch = vi.fn();
      await makeEffects(client(async request => json((request as Request).url.endsWith('/graph') ? g : { items: [c] })))({ projectId: 'project-1', request: 1 }, dispatch, new AbortController().signal);
      expect(dispatch).toHaveBeenCalledExactlyOnceWith({ type: 'failed', request: 1, error: SYSTEM_ERROR_MESSAGE });
    }
  });
  it('drops responses from an obsolete request', async () => {
    const resolve: ((value: Response) => void)[] = [];
    const effects = makeEffects(client(() => new Promise(r => resolve.push(r))));
    const dispatch = vi.fn(), signal = new AbortController().signal;
    const first = effects({ projectId: 'project-1', request: 1 }, dispatch, signal);
    const second = effects({ projectId: 'project-1', request: 2 }, dispatch, signal);
    await vi.waitFor(() => expect(resolve).toHaveLength(4));
    resolve[2](json(graph)); resolve[3](json({ items: [conversation] })); await second;
    resolve[0](json(graph)); resolve[1](json({ items: [conversation] })); await first;
    expect(dispatch).toHaveBeenCalledExactlyOnceWith({ type: 'loaded', request: 2, graph, conversations: [conversation] });
  });
});
