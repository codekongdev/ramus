import { useEffect, useId, useRef, useState } from 'react';
import { api as appApi, errorMessage, newIdempotencyKey, type ApiError, type AppApi } from '../../lib/api';
import { useStore, type Dispatch } from '../../lib/mvi';
import { useProjectEventListener, useResyncListener } from '../../lib/realtime';
import { Alert, Badge, Button, Checkbox, Chip, Dialog, EmptyState, Input, Label, Spinner, Textarea, TextField } from '../../ui';
import { makeResourcesEffectHandler, type ResourcesEffectDeps } from './effects';
import {
  chipLabel,
  fieldProblemMessage,
  fileProblemMessage,
  kindLabel,
  resourcesMessages as m,
  selectedVersionNote,
  selectLabel,
  useLatestLabel,
  versionSummary,
} from './messages';
import { initialResourcesState, type ResourcesIntent, type ResourcesState, type ResourceSummary } from './model';
import { canApply, canRegister, resourcesReducer, validateSkillForm } from './reducer';
import './resources.css';

export type ResourcesModalProps = {
  readonly projectId: string;
  /** The conversation the selection is applied to; null when none is open. */
  readonly conversationId: string | null;
  readonly onClose: () => void;
  /** Test seam; production uses the app client. */
  readonly api?: AppApi;
  readonly readBytes?: ResourcesEffectDeps['readBytes'];
  readonly delay?: ResourcesEffectDeps['delay'];
};

/**
 * WF-10 (검색·선택·적용) and WF-14 (스킬 등록) in one modal. Steps switch the body of the same
 * Dialog; no modal is stacked on top (roadmap 4.2).
 */
export function ResourcesModal(props: ResourcesModalProps) {
  const { projectId, conversationId, onClose } = props;
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  });
  const [handler] = useState(() =>
    makeResourcesEffectHandler({
      api: props.api ?? appApi,
      close: () => closeRef.current(),
      readBytes: props.readBytes,
      delay: props.delay,
    }),
  );
  const [state, dispatch] = useStore(resourcesReducer, () => initialResourcesState(projectId, conversationId), handler);

  useEffect(() => {
    dispatch({ type: 'opened' });
  }, [dispatch]);
  useProjectEventListener(event => dispatch({ type: 'serverEvent', event }));
  useResyncListener(() => dispatch({ type: 'resynced' }));

  const register = state.step === 'register';
  return (
    <Dialog
      open
      title={m.modalTitle}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      className="resources-modal"
      footer={register ? <RegisterFooter state={state} dispatch={dispatch} /> : <ListFooter state={state} dispatch={dispatch} />}
    >
      {register ? <RegisterStep state={state} dispatch={dispatch} /> : <ListStep state={state} dispatch={dispatch} />}
    </Dialog>
  );
}

type StepProps = { readonly state: ResourcesState; readonly dispatch: Dispatch<ResourcesIntent> };

function ErrorAlert({ error, onRetry }: { readonly error: ApiError; readonly onRetry?: () => void }) {
  const text = errorMessage(error);
  if (text === null) return null;
  return (
    <Alert variant="destructive" className="resources-alert">
      <span>{text}</span>
      {onRetry && (
        <Button variant="link" size="sm" onClick={onRetry}>
          {m.retry}
        </Button>
      )}
    </Alert>
  );
}

// --- WF-10 list -------------------------------------------------------------------------

function ListStep({ state, dispatch }: StepProps) {
  const searchId = useId();
  const canSelect = state.conversationId !== null;
  return (
    <div className="resources-step" data-step="list">
      <div className="resources-toolbar">
        <Button variant="outline" disabled={state.apply.status === 'saving'} onClick={() => dispatch({ type: 'registerOpened' })}>
          {m.registerSkill}
        </Button>
      </div>

      <div className="resources-field">
        <Label htmlFor={searchId}>{m.searchLabel}</Label>
        <Input
          id={searchId}
          type="search"
          value={state.query}
          placeholder={m.searchPlaceholder}
          autoComplete="off"
          onChange={(event) => dispatch({ type: 'queryChanged', query: event.currentTarget.value })}
        />
      </div>

      {canSelect ? <SelectionChips state={state} dispatch={dispatch} /> : <p className="resources-note">{m.noConversation}</p>}

      {state.applied.status === 'failed' && (
        <Alert variant="destructive" className="resources-alert">
          <span>{m.appliedLoadFailed}</span>
          <Button variant="link" size="sm" onClick={() => dispatch({ type: 'retryApplied' })}>
            {m.retry}
          </Button>
        </Alert>
      )}

      <SearchResults state={state} dispatch={dispatch} />
    </div>
  );
}

function SelectionChips({ state, dispatch }: StepProps) {
  if (state.selection.length === 0) return null;
  const locked = state.apply.status === 'saving' || state.applied.status !== 'ready';
  return (
    <ul className="resources-chips" aria-label={m.selectionLabel}>
      {state.selection.map((item) => (
        <li key={item.resourceId}>
          <Chip
            label={chipLabel(item.name, item.number)}
            disabled={locked}
            onRemove={() => dispatch({ type: 'deselected', resourceId: item.resourceId })}
          >
            {chipLabel(item.name, item.number)}
          </Chip>
        </li>
      ))}
    </ul>
  );
}

function SearchResults({ state, dispatch }: StepProps) {
  const { search } = state;
  if (search.status === 'loading') {
    return (
      <div className="resources-status" role="status">
        <Spinner />
        <span>{m.loading}</span>
      </div>
    );
  }
  if (search.status === 'failed') {
    return <ErrorAlert error={search.error} onRetry={() => dispatch({ type: 'retrySearch' })} />;
  }
  if (search.data.length === 0) {
    const searching = state.query.trim() !== '';
    return (
      <EmptyState
        className="resources-empty"
        title={searching ? m.emptySearch : m.emptyAll}
        description={searching ? m.emptySearchHint : undefined}
        action={
          <Button variant="outline" onClick={() => dispatch({ type: 'registerOpened' })}>
            {m.registerSkill}
          </Button>
        }
      />
    );
  }
  return (
    <ul className="resources-results" aria-label={m.resultsLabel}>
      {search.data.map((resource) => (
        <ResultRow key={resource.id} resource={resource} state={state} dispatch={dispatch} />
      ))}
    </ul>
  );
}

function ResultRow({ resource, state, dispatch }: StepProps & { readonly resource: ResourceSummary }) {
  const checkboxId = useId();
  const selected = state.selection.find((item) => item.resourceId === resource.id);
  const canSelect = state.conversationId !== null;
  const locked = state.apply.status === 'saving' || state.applied.status !== 'ready';
  const name = resource.latest.name;
  return (
    <li className="resources-row" data-resource-id={resource.id}>
      <div className="resources-row__main">
        {canSelect && (
          <Checkbox
            id={checkboxId}
            checked={selected !== undefined}
            disabled={locked}
            aria-label={selectLabel(name)}
            onCheckedChange={() => dispatch({ type: 'toggled', resource })}
          />
        )}
        <div className="resources-row__text">
          <div className="resources-row__title">
            {canSelect ? <label htmlFor={checkboxId}>{name}</label> : <span>{name}</span>}
            {resource.kind !== 'skill' && <Badge variant="secondary">{kindLabel(resource.kind)}</Badge>}
          </div>
          {resource.latest.description && <p className="resources-row__description">{resource.latest.description}</p>}
          <p className="resources-row__versions">{versionSummary(resource.latest.number, resource.applied?.number ?? null)}</p>
        </div>
      </div>
      {selected && selected.revisionId !== resource.latest.revision_id && (
        <div className="resources-row__aside">
          <span className="resources-row__selected">{selectedVersionNote(selected.number)}</span>
          <Button variant="link" size="sm" disabled={locked} onClick={() => dispatch({ type: 'latestChosen', resource })}>
            {useLatestLabel(resource.latest.number)}
          </Button>
        </div>
      )}
    </li>
  );
}

function ListFooter({ state, dispatch }: StepProps) {
  if (state.conversationId === null) return null;
  const saving = state.apply.status === 'saving';
  return (
    <div className="resources-footer">
      <div className="resources-footer__message">
        {state.apply.error && <ErrorAlert error={state.apply.error} />}
      </div>
      <Button disabled={!canApply(state)} onClick={() => dispatch({ type: 'applyRequested', key: newIdempotencyKey() })}>
        {saving ? m.applying : m.apply}
      </Button>
    </div>
  );
}

// --- WF-14 register ---------------------------------------------------------------------

function RegisterStep({ state, dispatch }: StepProps) {
  const instructionsId = useId();
  const instructionsHelpId = useId();
  const { form } = state;
  const problems = form.showProblems ? validateSkillForm(form) : {};
  const saving = form.status === 'saving';
  const busy = form.status !== 'editing';
  return (
    <div className="resources-step" data-step="register">
      <Button variant="link" size="sm" className="resources-back" disabled={saving} onClick={() => dispatch({ type: 'backToList' })}>
        {`← ${m.back}`}
      </Button>
      <h3 className="resources-heading">{m.registerTitle}</h3>

      <TextField
        label={m.nameLabel}
        value={form.name}
        disabled={busy}
        autoComplete="off"
        error={problems.name && fieldProblemMessage('name', problems.name)}
        onChange={(event) => dispatch({ type: 'fieldChanged', field: 'name', value: event.currentTarget.value })}
      />
      <TextField
        label={m.descriptionLabel}
        value={form.description}
        disabled={busy}
        autoComplete="off"
        error={problems.description && fieldProblemMessage('description', problems.description)}
        onChange={(event) => dispatch({ type: 'fieldChanged', field: 'description', value: event.currentTarget.value })}
      />
      <div className="resources-field">
        <Label htmlFor={instructionsId}>{m.instructionsLabel}</Label>
        <Textarea
          id={instructionsId}
          className="resources-instructions"
          value={form.instructions}
          disabled={busy}
          rows={8}
          aria-invalid={problems.instructions ? true : undefined}
          aria-describedby={instructionsHelpId}
          onChange={(event) => dispatch({ type: 'fieldChanged', field: 'instructions', value: event.currentTarget.value })}
        />
        <p id={instructionsHelpId} className={problems.instructions ? 'h-error' : 'h-hint'} role={problems.instructions ? 'alert' : undefined}>
          {problems.instructions ? fieldProblemMessage('instructions', problems.instructions) : m.instructionsHint}
        </p>
      </div>

      {form.fileProblem && (
        <Alert variant="destructive" className="resources-alert">
          {fileProblemMessage(form.fileProblem)}
        </Alert>
      )}
      {form.error && <ErrorAlert error={form.error} />}
    </div>
  );
}

function RegisterFooter({ state, dispatch }: StepProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const saving = state.form.status === 'saving';
  const blocked = state.form.showProblems && !canRegister(state);
  return (
    <div className="resources-footer">
      <input
        ref={fileRef}
        type="file"
        accept=".md,.txt,text/markdown,text/plain"
        hidden
        data-testid="skill-file-input"
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          // Reset so choosing the same file again still fires a change.
          event.currentTarget.value = '';
          if (file) dispatch({ type: 'fileChosen', file });
        }}
      />
      <Button variant="outline" disabled={saving} onClick={() => fileRef.current?.click()}>
        {m.loadSkillFile}
      </Button>
      <Button disabled={state.form.status !== 'editing' || blocked} onClick={() => dispatch({ type: 'registerRequested', key: newIdempotencyKey() })}>
        {saving ? m.registering : m.register}
      </Button>
    </div>
  );
}
