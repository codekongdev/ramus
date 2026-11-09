import { formatDateTime } from '../../lib/format';
import { DEFAULT_LOCALE } from '../../lib/locale';
import { Badge, Button, Label, Spinner, Textarea } from '../../ui';
import { resultMessages as messages } from './messages';
import { generating, latestSourceRunId } from './model';
import type { TaskResultController } from './useTaskResult';
import './results.css';

export function SummaryAction({ controller, onShowResult }: { readonly controller: TaskResultController; readonly onShowResult: () => void }) {
  const { state, summarize } = controller;
  const active = generating(state);
  return <Button variant="outline" disabled={active || state.mutation !== null || Boolean(state.editor?.dirty)}
    title={state.editor?.dirty ? messages.unsaved : undefined}
    onClick={() => { onShowResult(); summarize(); }}>
    {active ? messages.generatingAction : state.result?.latest_revision_id ? messages.summarizeAgain : messages.summarize}
  </Button>;
}

export function TaskResultTab({ controller }: { readonly controller: TaskResultController }) {
  const { state, dispatch, save } = controller;
  const busy = state.mutation !== null;
  const active = generating(state);
  const viewed = state.viewed;
  return <div className="task-result">
    {state.loading && !state.result && <p role="status"><Spinner label={messages.loading} /> {messages.loading}</p>}
    {active && <p className="task-result__status" role="status"><Spinner label={messages.generatingAction} /> {messages.generating}</p>}
    {state.notice && <p className="task-result__status" role="status">{state.notice}</p>}
    {state.error && <div className="task-result__error" role="alert">
      <p>{state.error}</p>
      <div className="task-result__actions">
        <Button variant="outline" disabled={state.loading} onClick={() => dispatch({ type: 'refresh' })}>{state.conflict ? messages.reviewLatest : messages.retryLoad}</Button>
        {state.conflict && <Button variant="outline" disabled={state.loading || active || !latestSourceRunId(state)} onClick={() => dispatch({ type: 'rebase' })}>{messages.useLatestBase}</Button>}
      </div>
    </div>}
    {state.result?.draft?.status === 'failed' && <p className="task-result__error" role="alert">{state.result.draft.error?.message ?? messages.failed}</p>}
    {!state.result && !state.loading && !active && <div className="task-result__empty"><p>{messages.empty}</p><p>{messages.emptyHint}</p></div>}
    {state.editor && <form className="task-result__editor" onSubmit={event => { event.preventDefault(); save(); }}>
      <div className="task-result__heading"><h3>{messages.draft}</h3><Badge>{messages.version(state.editor.baseVersion + 1)}</Badge></div>
      <p id={`result-hint-${state.taskId}`} className="task-result__hint">{messages.draftHint}</p>
      <Label htmlFor={`result-conclusion-${state.taskId}`}>{messages.conclusion}</Label>
      <Textarea id={`result-conclusion-${state.taskId}`} value={state.editor.text} maxLength={20_000} aria-describedby={`result-hint-${state.taskId}`}
        onChange={event => dispatch({ type: 'editChanged', text: event.target.value })} />
      <div className="task-result__actions">
        <Button type="submit" disabled={!state.editor.text.trim() || busy || active || state.conflict}>{state.mutation?.kind === 'save' ? messages.saving : messages.save}</Button>
        <Button variant="ghost" disabled={busy} onClick={() => dispatch({ type: 'cancelEdit' })}>{messages.stopEditing}</Button>
      </div>
      {state.editor.dirty && <p className="task-result__hint">{messages.unsaved}</p>}
    </form>}
    {state.conflict && state.result?.draft?.status === 'ready' && state.result.draft.run_id !== state.editor?.sourceRunId && <section className="task-result__approved" aria-label={messages.latestDraft}>
      <h3>{messages.latestDraft}</h3><p className="task-result__hint">{messages.latestDraftHint}</p><p className="task-result__body">{state.result.draft.conclusion}</p>
    </section>}
    {viewed && <section className="task-result__approved" aria-label={messages.approved}>
      <div className="task-result__heading"><h3>{messages.approved}</h3><Badge>{messages.version(viewed.version)}</Badge>
        {!state.editor && viewed.id === state.approved?.id && <Button variant="outline" disabled={busy || active} onClick={() => dispatch({ type: 'editApproved' })}>{messages.edit}</Button>}
      </div>
      <p className="task-result__body">{viewed.conclusion}</p>
      <p className="task-result__hint"><time dateTime={viewed.created_at}>{formatDateTime(viewed.created_at, DEFAULT_LOCALE)}</time></p>
      <details className="task-result__source"><summary>{messages.source}</summary><p>{messages.sourceRange(viewed.source.message_from_seq, viewed.source.message_to_seq)}</p><p>{messages.sourceResources(viewed.source.resource_revision_ids.length)}</p></details>
    </section>}
    {state.result && state.result.revisions.length > 0 && <section aria-label={messages.history} className="task-result__history">
      <h3>{messages.history}</h3><div className="task-result__actions">{[...state.result.revisions].sort((a, b) => b.version - a.version).map(revision => <Button key={revision.id}
        variant={state.viewed?.id === revision.id ? 'secondary' : 'ghost'} aria-pressed={state.viewed?.id === revision.id}
        onClick={() => dispatch({ type: 'selectRevision', revisionId: revision.id })}>{messages.version(revision.version)}</Button>)}</div>
    </section>}
  </div>;
}
