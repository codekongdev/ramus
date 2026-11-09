import { useEffect, useMemo, useState } from 'react';
import { Plus } from 'lucide-react';
import { newIdempotencyKey } from '../../lib/api';
import type { AppApi } from '../../lib/api/app';
import { useStore } from '../../lib/mvi';
import { useProjectEventListener, useResyncListener } from '../../lib/realtime';
import { Button, Input, Label, Spinner } from '../../ui';
import { makeEffects } from './effects';
import { messages } from './messages';
import { initialState, reducer, treeRows } from './model';
import './task-navigation.css';

export type TaskConversationTreeProps = {
  readonly projectId: string;
  readonly conversationId?: string;
  readonly onSelectConversation: (conversationId: string) => void;
  readonly onOpenTask: (taskId: string) => void;
  readonly client?: AppApi;
  /** Called after loading or creating; selection is owned by the workspace route. */
  readonly onInitialConversation?: (conversationId: string) => void;
};
/** Selection of a child uses its task ID, never the central conversation route. */
export function TaskConversationTree(props: TaskConversationTreeProps) {
  return <ProjectTree key={props.projectId} {...props} />;
}
function ProjectTree({ projectId, conversationId, onSelectConversation, onOpenTask, onInitialConversation, client }: TaskConversationTreeProps) {
  const effects = useMemo(() => makeEffects(client), [client]);
  const [state, dispatch] = useStore(reducer, () => initialState(projectId), effects);
  const [showCreate, setShowCreate] = useState(false);
  useEffect(() => dispatch({ type: 'load' }), [dispatch]);
  useResyncListener(() => dispatch({ type: 'load' }));
  useProjectEventListener((event) => {
    if (event.type === 'conversation.created' && event.data.project_id === projectId) dispatch({ type: 'load' });
  });
  useEffect(() => {
    if (!state.createdId) return;
    dispatch({ type: 'createdSelected' });
    setShowCreate(false);
    onSelectConversation(state.createdId);
  }, [state.createdId, dispatch, onSelectConversation]);
  useEffect(() => {
    if (!conversationId && !state.loading && !state.error && !state.creating && !showCreate) {
      const first = state.items.find(item => item.parent_id === null && item.task_id === null);
      if (first) onInitialConversation?.(first.id);
    }
  }, [conversationId, state.loading, state.error, state.items, state.creating, showCreate, onInitialConversation]);
  return <section className="task-navigation" aria-label={messages.heading}>
    <div className="task-navigation__heading"><h2>{messages.heading}</h2>
      <Button variant="ghost" size="sm" aria-label={messages.create} onClick={() => setShowCreate(true)}><Plus size={16} aria-hidden="true" /></Button>
    </div>
    {showCreate && <form className="task-navigation__create" onSubmit={event => { event.preventDefault(); dispatch({ type: 'create', key: newIdempotencyKey() }); }}>
      <Label htmlFor={`conversation-title-${projectId}`}>{messages.title}</Label>
      <Input id={`conversation-title-${projectId}`} autoFocus value={state.title} maxLength={100} placeholder={messages.titlePlaceholder}
        disabled={state.creating !== null} onChange={event => dispatch({ type: 'titleChanged', title: event.target.value })} />
      {state.createError && <p role="alert">{state.createError}</p>}
      <div className="task-navigation__create-actions">
        <Button size="sm" variant="ghost" disabled={state.creating !== null} onClick={() => setShowCreate(false)}>{messages.cancel}</Button>
        <Button size="sm" type="submit" disabled={!state.title.trim() || state.creating !== null}>{state.creating ? messages.creating : messages.createSubmit}</Button>
      </div>
    </form>}
    {state.loading && !state.items.length && <Spinner label={messages.loading} />}
    {state.error && <div role="alert"><p>{state.error}</p><Button variant="ghost" onClick={() => dispatch({ type: 'load' })}>{messages.retry}</Button></div>}
    {!state.loading && !state.error && !state.items.length && <p>{messages.empty}</p>}
    <ul>{treeRows(state.items).map(({ conversation, depth }) => <li key={conversation.id}>
      <button type="button" className="task-navigation__entry"
        style={{ paddingInlineStart: `calc(var(--spacing) * ${2 + Math.min(depth, 4) * 3})` }}
        aria-current={conversation.id === conversationId ? 'page' : undefined}
        aria-haspopup={conversation.task_id ? 'dialog' : undefined}
        onClick={() => conversation.task_id ? onOpenTask(conversation.task_id) : onSelectConversation(conversation.id)}>
        {conversation.task_id && <span aria-hidden="true">↳</span>}
        <span>{conversation.title}</span>
      </button>
    </li>)}</ul>
  </section>;
}
