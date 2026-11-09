import { useEffect, useMemo, type ReactNode, type Ref } from 'react';
import type { components } from '../../api/schema';
import { api, type AppApi } from '../../lib/api';
import { useStore } from '../../lib/mvi';
import { useProjectEventListener, useResyncListener } from '../../lib/realtime';
import { Badge, Button, Dialog, Spinner } from '../../ui';
import type { ConversationInput } from './contract';
import { sharingMessages as m } from './messages';
import { makeReceivedEffectHandler, makeRevisionEffectHandler } from './receivedEffects';
import { initialReceivedState, initialRevisionState, receivedReducer, revisionReducer } from './receivedModel';
import { SendConclusion, useSendConclusion } from './SendConclusion';
import './sharing.css';

type ResultRevision = components['schemas']['ResultRevision'];

export function ReceivedResults({ conversationId, onOpen, client = api }: {
  readonly conversationId: string; readonly onOpen: (input: ConversationInput) => void; readonly client?: AppApi;
}) {
  const handle = useMemo(() => makeReceivedEffectHandler(client), [client]);
  const [state, dispatch] = useStore(receivedReducer, () => initialReceivedState(conversationId), handle);
  useEffect(() => { dispatch({ type: 'select', conversationId }); }, [conversationId, dispatch]);
  useProjectEventListener(event => dispatch({ type: 'event', event }));
  useResyncListener(() => dispatch({ type: 'refresh' }));
  return <div className="received-results">
    <h2>{m.received}</h2>
    {state.loading && state.items.length === 0 && <p className="sharing-hint" role="status"><Spinner label={m.loadingInputs} /> {m.loadingInputs}</p>}
    {state.error && <div role="alert"><p>{state.error}</p><Button variant="outline" disabled={state.loading} onClick={() => dispatch({ type: 'refresh' })}>{m.retry}</Button></div>}
    {!state.loading && !state.error && state.items.length === 0 && <p className="sharing-hint">{m.empty}</p>}
    <ul className="received-results__list">{state.items.map(item => <li key={item.id}>
      <Button variant="ghost" className="received-results__row" onClick={() => onOpen(item)}><span className="sharing-title">{item.title}</span>
        <span className="received-results__versions"><Badge>{m.version(item.version)}</Badge>{item.latest_version > item.version && <Badge>{m.newer}</Badge>}</span>
      </Button>
    </li>)}</ul>
  </div>;
}

export function ReceivedResultDialog({ projectId, input, onClose, renderConclusion, client = api }: {
  readonly projectId: string; readonly input: ConversationInput; readonly onClose: () => void; readonly client?: AppApi;
  readonly renderConclusion: (revision: ResultRevision, controls: {
    readonly onSendToConversation: () => void;
    readonly sendButtonRef: Ref<HTMLButtonElement>;
  }) => ReactNode;
}) {
  const handle = useMemo(() => makeRevisionEffectHandler(client), [client]);
  const [state, dispatch] = useStore(revisionReducer, () => initialRevisionState(input), handle);
  const send = useSendConclusion(client);
  useEffect(() => { dispatch({ type: 'refresh' }); }, [dispatch]);
  const revision = state.revision;
  return <Dialog open title={input.title} onOpenChange={open => { if (!open) onClose(); }} className="received-result-modal">
    {send.state.target ? <SendConclusion controller={send} /> : <div className="sharing-step">
      {state.loading && <p role="status"><Spinner label={m.loadingRevision} /> {m.loadingRevision}</p>}
      {state.error && <div role="alert"><p>{state.error}</p><Button variant="outline" disabled={state.loading} onClick={() => dispatch({ type: 'refresh' })}>{m.retry}</Button></div>}
      {send.state.notice && <p role="status">{send.state.notice}</p>}
      {revision && renderConclusion(revision, {
        onSendToConversation: () => send.dispatch({ type: 'open', target: { projectId, currentConversationId: input.conversation_id, revision } }),
        sendButtonRef: send.returnFocusRef,
      })}
    </div>}
  </Dialog>;
}
