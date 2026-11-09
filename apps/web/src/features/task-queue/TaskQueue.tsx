import { useEffect, useMemo } from 'react';
import { api, type AppApi } from '../../lib/api';
import { useStore } from '../../lib/mvi';
import { useProjectEventListener, useResyncListener } from '../../lib/realtime';
import { Button, TaskStatusBadge } from '../../ui';
import { makeTaskQueueEffectHandler } from './effects';
import { initialTaskQueueState, taskQueueReducer } from './model';
import { taskQueueMessages as messages } from './messages';
import './task-queue.css';

export interface TaskQueueProps {
  readonly conversationId: string;
  readonly onOpenTask: (taskId: string) => void;
  readonly client?: AppApi;
}

/** Mount below the project's shared ProjectEventsProvider. Opening a task never navigates. */
export function TaskQueue({ conversationId, onOpenTask, client = api }: TaskQueueProps) {
  const handleEffect = useMemo(() => makeTaskQueueEffectHandler(client), [client]);
  const [state, dispatch] = useStore(taskQueueReducer, initialTaskQueueState, handleEffect);
  useEffect(() => dispatch({ type: 'selectConversation', conversationId }), [conversationId, dispatch]);
  useProjectEventListener((event) => dispatch({ type: 'serverEvent', event }));
  useResyncListener(() => dispatch({ type: 'refresh' }));

  const current = state.conversationId === conversationId;
  const items = current ? state.items : [];
  const loading = !current || state.loading;
  const error = current ? state.error : null;

  return (
    <div className="task-queue" aria-busy={loading}>
      <div className="task-queue__heading">
        <h2>{messages.title}</h2>
        {items.length > 0 && <span className="task-queue__count" aria-label={messages.count(items.length)}>{items.length}</span>}
      </div>
      {loading && items.length === 0 && <p className="task-queue__hint" role="status">{messages.loading}</p>}
      {error && (
        <div className="task-queue__error" role="alert">
          <p>{error}</p>
          <Button variant="outline" size="sm" onClick={() => dispatch({ type: 'refresh' })}>{messages.reload}</Button>
        </div>
      )}
      {!loading && !error && items.length === 0 && (
        <p className="task-queue__hint">{messages.empty}</p>
      )}
      {items.length > 0 && (
        <ul className="task-queue__list" aria-label={messages.listLabel}>
          {items.map((task) => (
            <li key={task.id}>
              <Button variant="ghost" className="task-queue__row" onClick={() => onOpenTask(task.id)}>
                <span className="task-queue__title">{task.title}</span>
                <TaskStatusBadge status={task.status} />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
