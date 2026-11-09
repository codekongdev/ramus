import { Button } from '../../ui';
import type { Ref } from 'react';
import type { ResultRevision } from './contract';
import { resultMessages as messages } from './messages';
import './results.css';

/** Explicit actions receive the exact version being read, including older versions. */
export type ConclusionActions = {
  readonly onCreateConversation?: (revision: ResultRevision) => void;
  readonly onSendToConversation?: (revision: ResultRevision) => void;
};

/** WF-08/16: only the conclusion is content; opening this view has no effects. */
export function ConclusionView({ revision, onCreateConversation, onSendToConversation, sendButtonRef }: ConclusionActions & {
  readonly revision: ResultRevision;
  readonly sendButtonRef?: Ref<HTMLButtonElement>;
}) {
  return <section className="conclusion-view" aria-label={messages.conclusionBody}>
    <h3>{messages.conclusion}</h3>
    <p className="conclusion-view__body">{revision.conclusion}</p>
    <div className="conclusion-view__actions">
      <Button variant="outline" disabled={!onCreateConversation}
        title={!onCreateConversation ? messages.actionUnavailable : undefined}
        onClick={() => onCreateConversation?.(revision)}>{messages.createConversation}</Button>
      <Button variant="outline" disabled={!onSendToConversation} ref={sendButtonRef}
        title={!onSendToConversation ? messages.actionUnavailable : undefined}
        onClick={() => onSendToConversation?.(revision)}>{messages.sendToConversation}</Button>
    </div>
  </section>;
}
