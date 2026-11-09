import { next, type Next, type Reducer } from '../../lib/mvi';
import {
  emptySkillForm,
  type AppliedResource,
  type CreateResourceRequest,
  type ResourceSummary,
  type ResourcesEffect,
  type ResourcesIntent,
  type ResourcesState,
  type SelectedRevision,
  type SkillForm,
  type SkillFormProblems,
} from './model';
import { MAX_DESCRIPTION_LENGTH, MAX_INSTRUCTIONS_LENGTH, MAX_NAME_LENGTH } from './skillFile';

type Result = Next<ResourcesState, ResourcesEffect>;

// --- pure selectors ---------------------------------------------------------------------

export function validateSkillForm(form: Pick<SkillForm, 'name' | 'description' | 'instructions'>): SkillFormProblems {
  const problems: SkillFormProblems = {};
  const name = form.name.trim();
  const instructions = form.instructions.trim();
  if (name === '') problems.name = 'required';
  else if (name.length > MAX_NAME_LENGTH) problems.name = 'tooLong';
  if (form.description.trim().length > MAX_DESCRIPTION_LENGTH) problems.description = 'tooLong';
  if (instructions === '') problems.instructions = 'required';
  else if (instructions.length > MAX_INSTRUCTIONS_LENGTH) problems.instructions = 'tooLong';
  return problems;
}

export const hasProblems = (problems: SkillFormProblems): boolean => Object.keys(problems).length > 0;

const selectionFromApplied = (items: readonly AppliedResource[]): SelectedRevision[] =>
  items.map((item) => ({
    resourceId: item.resource_id,
    revisionId: item.revision_id,
    number: item.number,
    name: item.name,
    kind: item.kind,
  }));

const latestOf = (resource: ResourceSummary): SelectedRevision => ({
  resourceId: resource.id,
  revisionId: resource.latest.revision_id,
  number: resource.latest.number,
  name: resource.latest.name,
  kind: resource.kind,
});

const sameIds = (a: readonly string[], b: readonly string[]): boolean =>
  a.length === b.length && a.every((id, index) => id === b[index]);

const sortedRevisionIds = (revisions: readonly { readonly revisionId: string }[]): string[] =>
  revisions.map((revision) => revision.revisionId).sort();

/** True when applying would change what the conversation uses. Order does not matter. */
export function selectionChanged(state: ResourcesState): boolean {
  if (state.applied.status !== 'ready') return false;
  const applied = sortedRevisionIds(selectionFromApplied(state.applied.data));
  return !sameIds(applied, sortedRevisionIds(state.selection));
}

/** WF-10: no apply without a selection, without an open conversation, or while saving. */
export function canApply(state: ResourcesState): boolean {
  return (
    state.conversationId !== null &&
    state.step === 'list' &&
    state.selection.length > 0 &&
    state.apply.status === 'idle' &&
    selectionChanged(state)
  );
}

export function canRegister(state: ResourcesState): boolean {
  return state.form.status === 'editing' && !hasProblems(validateSkillForm(state.form));
}

// --- reducer ----------------------------------------------------------------------------

function startSearch(state: ResourcesState, debounce: boolean): Result {
  const seq = state.searchSeq + 1;
  return next<ResourcesState, ResourcesEffect>(
    { ...state, searchSeq: seq, search: { status: 'loading' } },
    {
      type: 'search',
      projectId: state.projectId,
      conversationId: state.conversationId,
      query: state.query.trim(),
      seq,
      debounce,
    },
  );
}

function loadApplied(state: ResourcesState): Result {
  if (state.conversationId === null) return next(state);
  return next<ResourcesState, ResourcesEffect>(
    { ...state, applied: { status: 'loading' } },
    { type: 'loadApplied', conversationId: state.conversationId },
  );
}

function reloadAll(state: ResourcesState): Result {
  const searched = startSearch(state, false);
  const loaded = loadApplied(searched.state);
  return next(loaded.state, ...searched.effects, ...loaded.effects);
}

function editSelection(state: ResourcesState, selection: readonly SelectedRevision[]): Result {
  if (state.conversationId === null || state.applied.status !== 'ready' || state.apply.status === 'saving') return next(state);
  return next({ ...state, selection, selectionTouched: true, apply: { ...state.apply, error: null } });
}

function createBody(form: SkillForm): CreateResourceRequest {
  return {
    kind: 'skill',
    name: form.name.trim(),
    description: form.description.trim(),
    instructions: form.instructions.trim(),
    content: null,
    file_name: null,
  };
}

const sameBody = (a: CreateResourceRequest, b: CreateResourceRequest): boolean =>
  a.kind === b.kind &&
  a.name === b.name &&
  a.description === b.description &&
  a.instructions === b.instructions &&
  a.content === b.content &&
  a.file_name === b.file_name;

const withForm = (state: ResourcesState, form: Partial<SkillForm>): ResourcesState => ({
  ...state,
  form: { ...state.form, ...form },
});

export const resourcesReducer: Reducer<ResourcesState, ResourcesIntent, ResourcesEffect> = (state, intent) => {
  switch (intent.type) {
    case 'opened':
    case 'resynced':
      return reloadAll(state);

    case 'queryChanged':
      if (intent.query === state.query) return next(state);
      return startSearch({ ...state, query: intent.query }, true);

    case 'retrySearch':
      return startSearch(state, false);

    case 'searchLoaded':
      if (intent.seq !== state.searchSeq) return next(state);
      return next({ ...state, search: { status: 'ready', data: intent.items } });

    case 'searchFailed':
      if (intent.seq !== state.searchSeq) return next(state);
      if (intent.error.kind === 'aborted') return next(state);
      return next({ ...state, search: { status: 'failed', error: intent.error } });

    case 'retryApplied':
      return loadApplied(state);

    case 'appliedLoaded':
      return next({
        ...state,
        applied: { status: 'ready', data: intent.items },
        appliedInitialized: true,
        // Registration may finish before the first applied read. Preserve that new chip
        // while bringing in every pre-existing pinned version before editing is enabled.
        selection: !state.appliedInitialized
          ? [...selectionFromApplied(intent.items).filter(item => !state.selection.some(selected => selected.resourceId === item.resourceId)), ...state.selection]
          : state.selectionTouched ? state.selection : selectionFromApplied(intent.items),
      });

    case 'appliedFailed':
      if (intent.error.kind === 'aborted') return next(state);
      return next({ ...state, applied: { status: 'failed', error: intent.error } });

    case 'toggled': {
      const selected = state.selection.some((item) => item.resourceId === intent.resource.id);
      return editSelection(
        state,
        selected
          ? state.selection.filter((item) => item.resourceId !== intent.resource.id)
          : [...state.selection, latestOf(intent.resource)],
      );
    }

    case 'latestChosen': {
      const latest = latestOf(intent.resource);
      if (!state.selection.some((item) => item.resourceId === latest.resourceId)) return next(state);
      return editSelection(
        state,
        state.selection.map((item) => (item.resourceId === latest.resourceId ? latest : item)),
      );
    }

    case 'deselected':
      return editSelection(
        state,
        state.selection.filter((item) => item.resourceId !== intent.resourceId),
      );

    case 'applyRequested': {
      if (!canApply(state) || state.conversationId === null) return next(state);
      const revisionIds = state.selection.map((item) => item.revisionId);
      const previous = state.apply.lastAttempt;
      // Retrying the same selection reuses the key, so a lost response is not applied twice.
      const key = previous && sameIds(previous.revisionIds, revisionIds) ? previous.key : intent.key;
      return next<ResourcesState, ResourcesEffect>(
        { ...state, apply: { status: 'saving', error: null, lastAttempt: { key, revisionIds } } },
        { type: 'apply', conversationId: state.conversationId, revisionIds, key },
      );
    }

    case 'applySucceeded':
      return next<ResourcesState, ResourcesEffect>(
        {
          ...state,
          applied: { status: 'ready', data: intent.items },
          selection: selectionFromApplied(intent.items),
          selectionTouched: false,
          apply: { status: 'idle', error: null, lastAttempt: null },
        },
        { type: 'close' },
      );

    case 'applyFailed':
      // WF-10: keep the query and the selection so the user can retry.
      return next({ ...state, apply: { ...state.apply, status: 'idle', error: intent.error } });

    case 'registerOpened':
      if (state.apply.status === 'saving') return next(state);
      return next({ ...state, step: 'register', form: emptySkillForm, fileSeq: state.fileSeq + 1 });

    case 'backToList':
      if (state.form.status === 'saving') return next(state);
      // WF-14: cancel and back discard the input without registering.
      return next({ ...state, step: 'list', form: emptySkillForm, fileSeq: state.fileSeq + 1 });

    case 'fieldChanged':
      if (state.form.status !== 'editing') return next(state);
      return next(withForm(state, { [intent.field]: intent.value, error: null }));

    case 'fileChosen': {
      if (state.form.status === 'saving') return next(state);
      const seq = state.fileSeq + 1;
      return next<ResourcesState, ResourcesEffect>(withForm({ ...state, fileSeq: seq }, { status: 'reading', fileProblem: null }), {
        type: 'readFile',
        file: intent.file,
        seq,
      });
    }

    case 'fileLoaded': {
      if (state.step !== 'register' || state.form.status !== 'reading' || intent.seq !== state.fileSeq) return next(state);
      const { skill } = intent;
      return next(
        withForm(state, {
          name: skill.name ?? state.form.name,
          description: skill.description ?? state.form.description,
          instructions: skill.instructions,
          fileProblem: null,
          error: null,
          status: 'editing',
        }),
      );
    }

    case 'fileRejected':
      if (state.step !== 'register' || state.form.status !== 'reading' || intent.seq !== state.fileSeq) return next(state);
      return next(withForm(state, { status: 'editing', fileProblem: intent.problem }));

    case 'registerRequested': {
      if (state.step !== 'register' || state.form.status !== 'editing') return next(state);
      if (hasProblems(validateSkillForm(state.form))) return next(withForm(state, { showProblems: true }));
      const body = createBody(state.form);
      const previous = state.form.lastAttempt;
      const key = previous && sameBody(previous.body, body) ? previous.key : intent.key;
      return next<ResourcesState, ResourcesEffect>(
        withForm(state, { status: 'saving', error: null, showProblems: true, lastAttempt: { key, body } }),
        { type: 'create', projectId: state.projectId, body, key },
      );
    }

    case 'registerSucceeded': {
      const { detail } = intent;
      const created: SelectedRevision = {
        resourceId: detail.id,
        revisionId: detail.revision.id,
        number: detail.revision.number,
        name: detail.revision.name,
        kind: detail.kind,
      };
      // WF-14: back to the list of the same modal with the new skill selected, ready to apply.
      const listed: ResourcesState = { ...state, step: 'list', query: '', form: emptySkillForm };
      const selected =
        state.conversationId === null
          ? listed
          : { ...listed, selection: [...state.selection, created], selectionTouched: true };
      return startSearch(selected, false);
    }

    case 'registerFailed':
      return next(withForm(state, { status: 'editing', error: intent.error }));

    case 'serverEvent': {
      const { event } = intent;
      if (event.type === 'resource.updated' && event.data.project_id === state.projectId) {
        return startSearch(state, false);
      }
      if (
        event.type === 'conversation_resources.updated' &&
        event.data.conversation_id === state.conversationId &&
        state.apply.status === 'idle'
      ) {
        return reloadAll(state);
      }
      return next(state);
    }
  }
};
