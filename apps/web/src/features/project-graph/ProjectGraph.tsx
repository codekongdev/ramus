import { useEffect, useMemo } from 'react';
import { useModalHost } from '../../app/modal/ModalHost';
import type { AppApi } from '../../lib/api';
import { useStore } from '../../lib/mvi';
import { useProjectEventListener, useResyncListener } from '../../lib/realtime';
import { Alert, Button, Dialog, EmptyState, Spinner, TaskStatusBadge } from '../../ui';
import { makeEffects } from './effects';
import { projectGraphMessages as m } from './messages';
import { initialState, layoutGraph, reducer, usageEdgePath } from './model';
import './project-graph.css';

type Props = { readonly projectId: string; readonly onOpenTask: (id: string) => void; readonly onSelectConversation: (id: string) => void; readonly client?: AppApi };
export function ProjectGraphMenuButton(props: Props) {
  const { openModal } = useModalHost();
  return <Button variant="ghost" className="project-graph-menu-button" onClick={() => openModal({ id: `graph:${props.projectId}`,
    render: close => <ProjectGraphModal key={props.projectId} {...props} onClose={close} /> })}>{m.title}</Button>;
}
export function ProjectGraphModal({ projectId, onClose, onOpenTask, onSelectConversation, client }: Props & { readonly onClose: () => void }) {
  const effects = useMemo(() => makeEffects(client), [client]);
  const [state, dispatch] = useStore(reducer, () => initialState(projectId), effects);
  useEffect(() => { dispatch({ type: 'refresh' }); }, [dispatch]);
  useResyncListener(() => dispatch({ type: 'refresh' }));
  useProjectEventListener(event => { if (['conversation.created', 'task.updated', 'result.updated', 'conversation_inputs.updated'].includes(event.type)) dispatch({ type: 'refresh' }); });
  const graph = state.graph; const layout = graph ? layoutGraph(graph) : null;
  const tasks = new Map(state.conversations.map(item => [item.id, item.task_id]));
  const names = new Map(graph?.nodes.map(node => [node.conversation_id, node.title]) ?? []);
  return <Dialog open title={m.title} className="project-graph-modal" onOpenChange={open => { if (!open) onClose(); }}>
    <div className="project-graph-toolbar"><p>{m.description}</p><Button variant="outline" disabled={state.status === 'loading'} onClick={() => dispatch({ type: 'refresh' })}>{m.refresh}</Button></div>
    <div className="project-graph-legend" aria-label={m.legend}><span><i className="project-graph-line" />{m.branch}</span><span><i className="project-graph-line is-dashed" />{m.usage}</span></div>
    {state.status === 'loading' && <p role="status"><Spinner /> {m.loading}</p>}
    {state.status === 'failed' && <Alert variant="destructive"><p>{state.error}</p><Button variant="link" onClick={() => dispatch({ type: 'refresh' })}>{m.retry}</Button></Alert>}
    {state.status !== 'failed' && graph && layout && (graph.nodes.length === 0 ? <EmptyState title={m.empty} description={m.emptyHint} /> : <>
      <div className="project-graph-viewport" role="region" aria-label={m.map} tabIndex={0}>
        <div className="project-graph-canvas" style={{ width: layout.width, height: layout.height }}>
          <svg className="project-graph-edges" width={layout.width} height={layout.height} aria-hidden="true">
            {graph.edges.map((edge, index) => { const from = layout.positions.get(edge.from)!, to = layout.positions.get(edge.to)!; return edge.kind === 'uses_result'
              ? <path key={`${edge.kind}-${edge.from}-${edge.to}-${index}`} d={usageEdgePath(from, to)} className="is-dashed" />
              : <line key={`${edge.kind}-${edge.from}-${edge.to}-${index}`} x1={from.x + 100} y1={from.y + 38} x2={to.x + 100} y2={to.y + 38} />; })}
          </svg>
          {layout.ordered.map(node => { const pos = layout.positions.get(node.conversation_id)!; const taskId = tasks.get(node.conversation_id);
            return <button type="button" key={node.conversation_id} className="project-graph-node" style={{ left: pos.x, top: pos.y }}
              title={node.title} aria-haspopup={taskId ? 'dialog' : undefined} onClick={() => { if (taskId) onOpenTask(taskId); else if (node.task_status === null) { onClose(); onSelectConversation(node.conversation_id); } }} disabled={node.task_status !== null && !taskId}>
              <span>{node.title}</span>{node.task_status && <TaskStatusBadge status={node.task_status} />}
            </button>; })}
        </div>
      </div>
      <details className="project-graph-relations"><summary>{m.relations}</summary><ul>{graph.edges.length ? graph.edges.map((edge, index) => <li key={index}>{names.get(edge.from)} → {names.get(edge.to)}: {edge.kind === 'branch' ? m.branch : m.usage}</li>) : <li>{m.noRelations}</li>}</ul></details>
    </>)}
  </Dialog>;
}
