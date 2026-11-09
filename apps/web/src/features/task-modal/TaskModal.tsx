import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { api, newIdempotencyKey, type AppApi } from '../../lib/api';
import { formatDateTime } from '../../lib/format';
import { DEFAULT_LOCALE } from '../../lib/locale';
import { useStore } from '../../lib/mvi';
import { useProjectEventListener, useResyncListener } from '../../lib/realtime';
import { Button, Dialog, Label, MessageCard, Spinner, Tabs, TaskStatusBadge, Textarea } from '../../ui';
import { makeTaskModalEffectHandler } from './effects';
import { taskModalMessages as messages } from './messages';
import { hasActiveRun, initialTaskModalState, isActive, mentionsAi, taskModalReducer, type Task } from './model';
import './task-modal.css';

export type TaskModalProps = {
  readonly taskId: string;
  readonly onClose: () => void;
  readonly renderHeaderActions: (task: Task) => ReactNode;
  readonly renderResultTab: (task: Task, nav: { readonly closeModal: () => void }) => ReactNode;
  readonly client?: AppApi;
  readonly ensureAiConnection?: () => Promise<boolean>;
  readonly onTaskChanged?: (task: Task) => void;
};

/** Viewing or closing a task never cancels its server execution. */
export function TaskModal({ taskId, onClose, renderHeaderActions, renderResultTab, client = api, ensureAiConnection, onTaskChanged }: TaskModalProps) {
  const handler = useMemo(() => makeTaskModalEffectHandler(client, ensureAiConnection), [client, ensureAiConnection]);
  const [state, dispatch] = useStore(taskModalReducer, () => initialTaskModalState(taskId), handler);
  const [tab, setTab] = useState('conversation');
  const listRef = useRef<HTMLDivElement>(null);
  const keepBottom = useRef(true);
  useEffect(() => { dispatch({ type: 'select', taskId }); setTab('conversation'); }, [taskId, dispatch]);
  useProjectEventListener(event => dispatch({ type: 'serverEvent', event }));
  useResyncListener(() => dispatch({ type: 'refresh' }));
  useEffect(() => { if (state.task) onTaskChanged?.(state.task); }, [state.task, onTaskChanged]);
  useEffect(() => {
    const list = listRef.current;
    if (list && keepBottom.current) list.scrollTop = list.scrollHeight;
  }, [state.messages]);

  const task = state.task;
  const ownTask = task?.requested_by === state.me?.account.id;
  const active = hasActiveRun(state);
  const busy = state.mutation !== null;
  const canSend = Boolean(task && state.draft.trim() && !busy && !(mentionsAi(state.draft) && active));
  const submit = () => dispatch({ type: 'submit', key: newIdempotencyKey() });
  const hint = task ? { pending: messages.pendingHint, running: messages.runningHint, ready: messages.readyHint, failed: messages.failedHint, cancelled: messages.cancelledHint }[task.status] : null;
  const conversation = task && (
    <div className="task-modal__conversation">
      <section className="task-modal__goal" aria-label={messages.goal}>
        <h3>{messages.goal}</h3>
        <p>{task.goal}</p>
      </section>
      <div className="task-modal__progress" role="status">
        <p>{hint}</p>
        {task.error && <p>{task.error.message}</p>}
        {ownTask && (isActive(task.status) || ['failed', 'cancelled'].includes(task.status)) && (
          <Button variant="outline" disabled={busy} onClick={() => dispatch({ type: 'action', kind: isActive(task.status) ? 'cancel' : 'retry', key: newIdempotencyKey() })}>
            {busy && state.mutation?.kind !== 'send' ? messages.processing : task.status === 'pending' ? messages.cancel : task.status === 'running' ? messages.stop : messages.retry}
          </Button>
        )}
      </div>
      <div ref={listRef} className="task-modal__messages" role="region" aria-label={messages.messages} tabIndex={0}
        onScroll={event => { const list = event.currentTarget; keepBottom.current = list.scrollHeight - list.scrollTop - list.clientHeight < 48; }}>
        {state.messages.length === 0 && <p className="task-modal__empty">{messages.noMessages}</p>}
        {state.messages.map(message => (
          <MessageCard key={message.id} author={{ id: message.author.account_id ?? undefined, name: message.author.display_name }}
            timestamp={formatDateTime(message.created_at, DEFAULT_LOCALE)} dateTime={message.created_at} data-message-id={message.id}>
            {message.is_example && <small>{messages.example}</small>}
            <p className="task-modal__message-body">{message.body}</p>
          </MessageCard>
        ))}
      </div>
      <form className="task-modal__composer" onSubmit={event => { event.preventDefault(); if (canSend) submit(); }}>
        <Label htmlFor={`task-message-${taskId}`}>{messages.composer}</Label>
        <Textarea id={`task-message-${taskId}`} value={state.draft} placeholder={messages.composerPlaceholder}
          aria-describedby={`task-message-hint-${taskId}`} onChange={event => dispatch({ type: 'draftChanged', draft: event.target.value })}
          onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (canSend) submit(); } }} />
        <div className="task-modal__composer-actions">
          <p id={`task-message-hint-${taskId}`}>{active ? messages.activeHint : messages.composerHint}</p>
          <Button type="submit" disabled={!canSend}>{state.mutation?.kind === 'send' ? messages.sending : messages.send}</Button>
        </div>
      </form>
    </div>
  );

  return (
    <Dialog open title={task?.title ?? messages.loadingTitle} onOpenChange={open => { if (!open) onClose(); }} className="task-modal"
      headerActions={task && <><TaskStatusBadge status={task.status} />{task.status === 'ready' && renderHeaderActions(task)}</>}>
      {state.loading && !task && <p role="status"><Spinner /> {messages.loading}</p>}
      {state.error && <div className="task-modal__error" role="alert"><p>{state.error}</p><Button variant="outline" disabled={state.loading} onClick={() => dispatch({ type: 'refresh' })}>{messages.retryLoad}</Button></div>}
      {state.mutationError && <p className="task-modal__error" role="alert">{state.mutationError}</p>}
      {task && <Tabs label={messages.tabs} variant="underline" value={tab} onValueChange={setTab} items={[
        { value: 'conversation', label: messages.conversationTab, content: conversation },
        { value: 'result', label: messages.resultTab, content: renderResultTab(task, { closeModal: onClose }) },
      ]} />}
    </Dialog>
  );
}
