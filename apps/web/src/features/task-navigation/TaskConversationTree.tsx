import { useEffect, useMemo } from 'react';
import type { AppApi } from '../../lib/api/app';
import { useStore } from '../../lib/mvi';
import { useProjectEventListener, useResyncListener } from '../../lib/realtime';
import { Button, Spinner } from '../../ui';
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
};
/** Selection of a child uses its task ID, never the central conversation route. */
export function TaskConversationTree(props: TaskConversationTreeProps) {
  return <ProjectTree key={props.projectId} {...props} />;
}
function ProjectTree({ projectId, conversationId, onSelectConversation, onOpenTask, client }: TaskConversationTreeProps) {
  const effects = useMemo(() => makeEffects(client), [client]);
  const [state, dispatch] = useStore(reducer, () => initialState(projectId), effects);
  useEffect(() => dispatch({ type: 'load' }), [dispatch]);
  useResyncListener(() => dispatch({ type: 'load' }));
  useProjectEventListener((event) => {
    if (event.type === 'conversation.created') dispatch({ type: 'load' });
  });
  return <section className="task-navigation" aria-label={messages.heading}>
    <h2>{messages.heading}</h2>
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
