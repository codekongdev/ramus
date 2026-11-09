import { useEffect, useMemo, useRef } from 'react';
import { api, newIdempotencyKey, type AppApi } from '../../lib/api';
import { formatDateTime } from '../../lib/format';
import { DEFAULT_LOCALE } from '../../lib/locale';
import { useStore } from '../../lib/mvi';
import { useProjectEventListener, useProjectEventsStatus, useResyncListener } from '../../lib/realtime';
import { Badge, Button, Label, MessageCard, Spinner, Textarea } from '../../ui';
import { makeConversationEffectHandler } from './effects';
import { hasActiveRun, initialState, mentionsAi, reducer } from './model';
import { viewMessages as m } from './messages';
import './conversation.css';

export type ConversationProps = {
  readonly projectId: string;
  readonly conversationId?: string;
  readonly client?: AppApi;
  readonly ensureAiConnection?: () => Promise<boolean>;
};

/** The task modal is composed alongside this panel so it never unmounts its parent. */
export function Conversation(props: ConversationProps) {
  return props.conversationId
    ? <ConversationPanel key={`${props.projectId}:${props.conversationId}`} {...props} conversationId={props.conversationId} />
    : <div className="conversation__empty"><h1>{m.noConversation}</h1><p>{m.selectHint}</p></div>;
}

function ConversationPanel({ projectId, conversationId, client = api, ensureAiConnection }: ConversationProps & { readonly conversationId: string }) {
  const effects = useMemo(() => makeConversationEffectHandler(client, ensureAiConnection), [client, ensureAiConnection]);
  const [state, dispatch] = useStore(reducer, () => initialState(projectId, conversationId), effects);
  const status = useProjectEventsStatus();
  const listRef = useRef<HTMLDivElement>(null);
  const keepBottom = useRef(true);
  useEffect(() => dispatch({ type: 'load' }), [dispatch]);
  useProjectEventListener(event => dispatch({ type: 'serverEvent', event }));
  useResyncListener(() => dispatch({ type: 'refresh' }));
  useEffect(() => {
    const list = listRef.current;
    if (list && keepBottom.current) list.scrollTop = list.scrollHeight;
  }, [state.messages]);

  const active = hasActiveRun(state);
  const canSend = Boolean(state.conversation && state.draft.trim() && !state.mutation && !(mentionsAi(state.draft) && active));
  const submit = () => { if (canSend) dispatch({ type: 'submit', key: newIdempotencyKey() }); };
  return <section className="conversation" aria-label={state.conversation?.title ?? m.messageList}>
    {state.conversation && <header className="conversation__header"><h1>{state.conversation.title}</h1></header>}
    {state.loading && !state.conversation && <div className="conversation__empty" role="status"><Spinner label={m.loading} /></div>}
    {state.error && <div className="conversation__notice" role="alert"><p>{state.error}</p><Button variant="outline" onClick={() => dispatch({ type: 'refresh' })}>{m.retry}</Button></div>}
    {(status === 'reconnecting' || status === 'closed') && <p className="conversation__notice" role="status">{status === 'reconnecting' ? m.reconnecting : m.disconnected}</p>}
    {state.conversation && <>
      <div ref={listRef} className="conversation__messages" role="log" aria-label={m.messageList} tabIndex={0}
        onScroll={event => { const list = event.currentTarget; keepBottom.current = list.scrollHeight - list.scrollTop - list.clientHeight < 48; }}>
        {state.messages.length === 0 && <div className="conversation__empty"><p>{m.noMessages}</p><p>{m.emptyHint}</p></div>}
        {state.messages.map(message => <MessageCard key={message.id}
          author={{ id: message.author.account_id ?? undefined, name: message.author.display_name }}
          timestamp={formatDateTime(message.created_at, DEFAULT_LOCALE)} dateTime={message.created_at}
          data-message-id={message.id} data-message-seq={message.seq}>
          <div className="conversation__badges">
            {message.author.kind !== 'human' && <Badge>{message.author.kind === 'ai' ? m.ai : m.system}</Badge>}
            {message.is_example && <Badge>{m.example}</Badge>}
          </div>
          <p className="conversation__body">{message.body}</p>
        </MessageCard>)}
      </div>
      <form className="conversation__composer" onSubmit={event => { event.preventDefault(); submit(); }}>
        <Label htmlFor={`message-${conversationId}`}>{m.composer}</Label>
        <Textarea id={`message-${conversationId}`} value={state.draft} maxLength={20000} placeholder={m.placeholder}
          aria-describedby={`message-hint-${conversationId}`} onChange={event => dispatch({ type: 'draftChanged', draft: event.target.value })}
          onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229) {
              event.preventDefault(); submit();
            }
          }} />
        {state.mutationError && <p className="conversation__send-error" role="alert">{state.mutationError}</p>}
        <div className="conversation__composer-actions"><p id={`message-hint-${conversationId}`} role={active ? 'status' : undefined}>{active ? m.active : m.hint}</p>
          <Button type="submit" disabled={!canSend}>{state.mutation ? m.sending : m.send}</Button>
        </div>
      </form>
    </>}
  </section>;
}
