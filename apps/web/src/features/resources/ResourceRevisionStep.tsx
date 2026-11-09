import { useEffect, useId, useRef, useState } from 'react';
import { errorMessage, hasErrorCode, newIdempotencyKey, type ApiError, type AppApi } from '../../lib/api';
import { formatDateTime } from '../../lib/format';
import { DEFAULT_LOCALE } from '../../lib/locale';
import { useStore, type Dispatch } from '../../lib/mvi';
import { useProjectEventListener, useResyncListener } from '../../lib/realtime';
import { Alert, Badge, Button, Label, Spinner, Textarea, TextField } from '../../ui';
import { fileProblemMessage, kindLabel, versionLabel } from './messages';
import type { SelectedRevision } from './model';
import { makeRevisionEffects } from './revisionEffects';
import { revisionBaseLabel, revisionMessages as m, revisionProblemMessage, revisionViewLabel } from './revisionMessages';
import { initialRevisionState, type RevisionIntent, type RevisionState } from './revisionModel';
import { revisionReducer, validateRevisionDraft } from './revisionReducer';
import './revisions.css';

export type ResourceRevisionStepProps = {
  readonly resourceId: string;
  readonly projectId: string;
  readonly api: AppApi;
  readonly onBack: () => void;
  readonly onApply: (revision: SelectedRevision) => void;
  readonly canApply: boolean;
  readonly applying: boolean;
  readonly applyError: ApiError | null;
  readonly appliedRevisionId: string | null;
  readonly onBusyChange?: (busy: boolean) => void;
  readonly readBytes?: (file: File) => Promise<Uint8Array>;
};

/** WF-17/18: changes the body of the resource modal; saving never applies a revision. */
export function ResourceRevisionStep(props: ResourceRevisionStepProps) {
  const [handler] = useState(() => makeRevisionEffects({ api: props.api, readBytes: props.readBytes }));
  const [state, dispatch] = useStore(revisionReducer, () => initialRevisionState(props.resourceId, props.projectId), handler);
  const heading = useRef<HTMLHeadingElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  useEffect(() => { dispatch({ type: 'opened' }); }, [dispatch]);
  useProjectEventListener(event => {
    if (event.type === 'resource.updated' && event.data.resource_id === props.resourceId && event.data.project_id === props.projectId) dispatch({ type: 'refresh' });
  });
  useResyncListener(() => dispatch({ type: 'refresh' }));
  useEffect(() => { props.onBusyChange?.(state.saving); }, [props.onBusyChange, state.saving]);
  useEffect(() => () => props.onBusyChange?.(false), [props.onBusyChange]);
  useEffect(() => {
    if (state.phase === 'edit') nameInput.current?.focus();
    else heading.current?.focus({ preventScroll: true });
  }, [state.phase, state.detail?.revision.id]);

  if (state.phase === 'edit' && state.draft) {
    return <RevisionEditor state={state} dispatch={dispatch} nameInput={nameInput} />;
  }
  const detail = state.detail;
  const revision = detail?.revision;
  const locked = state.saving || props.applying;
  return <div className="resources-step revisions-step" data-step="detail">
    <Button type="button" variant="link" size="sm" className="resources-back" disabled={locked} onClick={props.onBack}>{`← ${m.back}`}</Button>
    {state.pending && <div className="resources-status" role="status"><Spinner /><span>{m.loading}</span></div>}
    {state.loadError && <RevisionError error={state.loadError} onRetry={() => dispatch({ type: 'retryLoad' })} />}
    {state.notice && <p className="revisions-notice" role="status">{state.notice === 'saved' ? m.saved : m.unchanged}</p>}
    {state.draft && <div className="revisions-preserved">
      <p className="resources-note">{m.draftPreserved}</p>
      <Button type="button" variant="outline" disabled={locked} onClick={() => dispatch({ type: 'resumeDraft' })}>{m.resumeDraft}</Button>
    </div>}
    {detail && revision && <>
      <div className="revisions-heading-row">
        <h3 ref={heading} tabIndex={-1} className="resources-heading">{revision.name}</h3>
        <Badge variant="secondary">{kindLabel(detail.kind)}</Badge>
      </div>
      {revision.description && <p className="revisions-description">{revision.description}</p>}
      <dl className="revisions-metadata">
        <div><dt>{m.version}</dt><dd>{versionLabel(revision.number)} {revision.id === detail.latest_revision_id && <Badge variant="secondary">{m.latest}</Badge>} {revision.id === props.appliedRevisionId && <Badge variant="secondary">{m.applied}</Badge>}</dd></div>
        <div><dt>{m.author}</dt><dd>{state.authors[revision.created_by] ?? revision.created_by}</dd></div>
        <div><dt>{m.savedAt}</dt><dd><time dateTime={revision.created_at}>{formatDateTime(revision.created_at, DEFAULT_LOCALE)}</time></dd></div>
        {revision.file_name && <div><dt>{m.fileName}</dt><dd>{revision.file_name}</dd></div>}
      </dl>
      <section className="revisions-content">
        <h4>{detail.kind === 'skill' ? m.instructions : m.content}</h4>
        <pre>{detail.kind === 'skill' ? revision.instructions : revision.content}</pre>
      </section>
      <section className="revisions-history">
        <h4>{m.history}</h4>
        <ol aria-label={m.history}>
          {[...detail.revisions].sort((a, b) => b.number - a.number).map(entry => <li key={entry.id}>
            <Button type="button" variant="ghost" className="revisions-history-entry" disabled={locked}
              aria-label={revisionViewLabel(entry.number)} aria-current={entry.id === revision.id ? 'true' : undefined}
              onClick={() => dispatch({ type: 'viewRequested', revisionId: entry.id })}>
              <span className="revisions-history-version">{versionLabel(entry.number)}{entry.id === detail.latest_revision_id && <Badge variant="secondary">{m.latest}</Badge>}</span>
              <span className="revisions-history-name">{entry.name}</span>
              <span className="revisions-history-meta"><span>{state.authors[entry.created_by] ?? entry.created_by}</span><time dateTime={entry.created_at}>{formatDateTime(entry.created_at, DEFAULT_LOCALE)}</time></span>
            </Button>
          </li>)}
        </ol>
      </section>
      {props.applyError && <RevisionError error={props.applyError} />}
      <div className="revisions-actions">
        <Button type="button" variant="outline" disabled={locked || Boolean(state.pending) || state.draft !== null} onClick={() => dispatch({ type: 'editRequested' })}>{m.edit}</Button>
        <Button type="button" disabled={locked || Boolean(state.pending) || !props.canApply || revision.id === props.appliedRevisionId}
          onClick={() => props.onApply({ resourceId: detail.id, revisionId: revision.id, number: revision.number, name: revision.name, kind: detail.kind })}>
          {props.applying ? m.applying : m.apply}
        </Button>
      </div>
    </>}
  </div>;
}

function RevisionError({ error, onRetry }: { readonly error: ApiError; readonly onRetry?: () => void }) {
  const message = errorMessage(error);
  return message && <Alert variant="destructive" className="resources-alert"><span>{message}</span>{onRetry && <Button type="button" variant="link" size="sm" onClick={onRetry}>{m.retry}</Button>}</Alert>;
}

function RevisionEditor({ state, dispatch, nameInput }: {
  readonly state: RevisionState;
  readonly dispatch: Dispatch<RevisionIntent>;
  readonly nameInput: React.Ref<HTMLInputElement>;
}) {
  const bodyId = useId();
  const helpId = useId();
  const fileInput = useRef<HTMLInputElement>(null);
  const draft = state.draft!;
  const problems = state.showProblems ? validateRevisionDraft(draft) : {};
  const busy = state.saving || state.fileReading;
  const conflict = state.saveError !== null && hasErrorCode(state.saveError, 'VERSION_CONFLICT');
  const problem = (field: 'name' | 'description' | 'body' | 'fileName') => problems[field] && revisionProblemMessage(field, problems[field]!, draft.kind);
  return <form className="resources-step revisions-step" data-step="edit" aria-busy={busy}
    onSubmit={event => { event.preventDefault(); dispatch({ type: 'saveRequested', key: newIdempotencyKey() }); }}>
    <div className="revisions-heading-row"><h3 className="resources-heading">{m.editTitle}</h3><span className="resources-note">{revisionBaseLabel(draft.baseNumber)}</span></div>
    <p className="resources-note">{m.saveNote}</p>
    <TextField ref={nameInput} label={m.name} value={draft.name} disabled={busy} error={problem('name')} autoComplete="off"
      onChange={event => dispatch({ type: 'fieldChanged', field: 'name', value: event.currentTarget.value })} />
    <TextField label={m.description} value={draft.description} disabled={busy} error={problem('description')} autoComplete="off"
      onChange={event => dispatch({ type: 'fieldChanged', field: 'description', value: event.currentTarget.value })} />
    {draft.kind === 'file' && <TextField label={m.fileName} value={draft.fileName} disabled={busy} error={problem('fileName')} hint={m.fileHint}
      onChange={event => dispatch({ type: 'fieldChanged', field: 'fileName', value: event.currentTarget.value })} />}
    <div className="resources-field">
      <Label htmlFor={bodyId}>{draft.kind === 'skill' ? m.instructions : m.content}</Label>
      <Textarea id={bodyId} className="resources-instructions" rows={10} value={draft.body} disabled={busy}
        aria-invalid={Boolean(problems.body)} aria-describedby={problems.body ? helpId : undefined}
        onChange={event => dispatch({ type: 'fieldChanged', field: 'body', value: event.currentTarget.value })} />
      {problems.body && <p id={helpId} className="h-error" role="alert">{problem('body')}</p>}
    </div>
    {state.fileReading && <p role="status" className="resources-status">{m.readingFile}</p>}
    {state.fileProblem && <Alert variant="destructive">{fileProblemMessage(state.fileProblem)}</Alert>}
    {conflict ? <Alert variant="destructive" className="resources-alert"><span>{m.conflict}</span><Button type="button" variant="link" size="sm" onClick={() => dispatch({ type: 'checkLatest' })}>{m.checkLatest}</Button></Alert>
      : state.saveError && <RevisionError error={state.saveError} />}
    <div className="revisions-actions">
      <Button type="button" variant="outline" disabled={state.saving} onClick={() => dispatch({ type: 'cancelEdit' })}>{m.cancel}</Button>
      <div className="revisions-actions-end">
        {draft.kind === 'file' && <>
          <input ref={fileInput} type="file" accept=".md,.txt,text/markdown,text/plain" hidden data-testid="revision-file-input" onChange={event => {
            const file = event.currentTarget.files?.[0]; event.currentTarget.value = '';
            if (file) dispatch({ type: 'fileChosen', file });
          }} />
          <Button type="button" variant="outline" disabled={busy} onClick={() => fileInput.current?.click()}>{m.replaceFile}</Button>
        </>}
        <Button type="submit" disabled={busy || state.fileProblem !== null}>{state.saving ? m.saving : m.save}</Button>
      </div>
    </div>
  </form>;
}
