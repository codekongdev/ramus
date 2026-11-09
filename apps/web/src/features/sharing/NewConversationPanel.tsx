import { useEffect, useId, useMemo, useRef } from 'react';
import { ArrowLeft } from 'lucide-react';
import { api, newIdempotencyKey, type AppApi } from '../../lib/api';
import { useStore } from '../../lib/mvi';
import { Badge, Button, Input, Label, Spinner } from '../../ui';
import type { ResultRevision } from '../results/contract';
import { makeEffects } from './effects';
import { sharingMessages as m } from './conversationMessages';
import { canCreate, initialState, MAX_TITLE_LENGTH, reducer, type Conversation } from './model';
import './sharing.css';

/** Renders inside the existing result dialog. The caller captures the viewed revision once. */
export type Conclusion = Pick<ResultRevision, 'id' | 'version' | 'title' | 'conclusion'>;
export function NewConversationPanel({ revision, onBack, onCreated, client = api }: {
  readonly revision: Conclusion;
  readonly onBack: () => void;
  readonly onCreated: (conversation: Conversation) => void;
  readonly client?: AppApi;
}) {
  const effects = useMemo(() => makeEffects(client, onCreated), [client, onCreated]);
  const [state, dispatch] = useStore(reducer, () => initialState(revision.id), effects);
  const id = useId();
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    dispatch({ type: 'search' });
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) searchRef.current?.focus(); });
    return () => { cancelled = true; };
  }, [dispatch]);

  return <form className="result-conversation" aria-label={m.title} aria-busy={state.creating}
    onSubmit={event => { event.preventDefault(); dispatch({ type: 'submit', key: newIdempotencyKey() }); }}>
    <Button variant="ghost" className="result-conversation__back" disabled={state.creating}
      onClick={onBack}><ArrowLeft size={16} aria-hidden="true" />{m.back}</Button>
    <section className="result-conversation__source" aria-label={m.source}>
      <h3>{m.source}</h3><div><strong>{revision.title}</strong><Badge>{m.version(revision.version)}</Badge></div>
      <p className="result-conversation__conclusion">{revision.conclusion}</p>
    </section>
    <div className="result-conversation__field">
      <Label htmlFor={`${id}-search`}>{m.project}</Label>
      <Input ref={searchRef} id={`${id}-search`} type="search" maxLength={100} value={state.query}
        disabled={state.creating} aria-describedby={`${id}-project-hint`}
        onChange={event => dispatch({ type: 'queryChanged', value: event.target.value })} />
      <p id={`${id}-project-hint`} className="result-conversation__hint">{m.projectHint}</p>
    </div>
    {state.loading && <p role="status"><Spinner label={m.loading} />{m.loading}</p>}
    {state.searchError && <div role="alert" className="result-conversation__error">{state.searchError}
      <Button variant="outline" onClick={() => dispatch({ type: 'search' })}>{m.retry}</Button></div>}
    {!state.loading && !state.searchError && state.projects.length === 0 && <p role="status">{m.empty}</p>}
    <ul className="result-conversation__projects" aria-label={m.projects}>
      {state.projects.map(project => <li key={project.id}><Button variant={state.selected?.id === project.id ? 'secondary' : 'outline'}
        disabled={state.creating} aria-label={m.select(project.name)} aria-pressed={state.selected?.id === project.id}
        onClick={() => dispatch({ type: 'select', projectId: project.id })}>{project.name}</Button></li>)}
    </ul>
    {state.selected && <p className="result-conversation__selected"><span>{m.selected}</span><strong>{state.selected.name}</strong></p>}
    <div className="result-conversation__field">
      <Label htmlFor={`${id}-title`}>{m.conversationTitle}</Label>
      <Input id={`${id}-title`} maxLength={MAX_TITLE_LENGTH} value={state.title} disabled={state.creating}
        onChange={event => dispatch({ type: 'titleChanged', value: event.target.value })} />
    </div>
    <p className="result-conversation__hint">{m.location}</p>
    {state.createError && <p role="alert" className="result-conversation__error">{state.createError}</p>}
    <div className="result-conversation__actions"><Button type="submit" disabled={!canCreate(state)}>{state.creating ? m.creating : m.create}</Button></div>
  </form>;
}
