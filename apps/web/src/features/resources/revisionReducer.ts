import { next, type Next, type Reducer } from '../../lib/mvi';
import type { ResourceDetail } from './model';
import type {
  ResourceRevision, RevisionDraft, RevisionEffect, RevisionIntent, RevisionProblems,
  RevisionRequest, RevisionState,
} from './revisionModel';
import { hasAllowedExtension, MAX_DESCRIPTION_LENGTH, MAX_INSTRUCTIONS_LENGTH, MAX_NAME_LENGTH } from './skillFile';

type Result = Next<RevisionState, RevisionEffect>;
const length = (value: string) => Array.from(value).length;
const invalidText = (value: string) => value.includes('\u0000') || Array.from(value).some(character => {
  const code = character.codePointAt(0)!;
  return code >= 0xd800 && code <= 0xdfff;
});

export function validateRevisionDraft(draft: RevisionDraft): RevisionProblems {
  const problems: RevisionProblems = {};
  for (const [field, limit] of [['name', MAX_NAME_LENGTH], ['description', MAX_DESCRIPTION_LENGTH], ['body', MAX_INSTRUCTIONS_LENGTH]] as const) {
    const value = draft[field].trim();
    if (!value && field !== 'description') problems[field] = 'required';
    else if (length(value) > limit) problems[field] = 'tooLong';
    else if (invalidText(value)) problems[field] = 'invalidText';
  }
  if (draft.kind === 'file') {
    const name = draft.fileName.trim();
    if (!name) problems.fileName = 'required';
    else if (length(name) > 255) problems.fileName = 'tooLong';
    else if (invalidText(name)) problems.fileName = 'invalidText';
    else if (!hasAllowedExtension(name)) problems.fileName = 'extension';
  }
  return problems;
}

export const revisionHasProblems = (draft: RevisionDraft) => Object.keys(validateRevisionDraft(draft)).length !== 0;

export function revisionBody(draft: RevisionDraft): RevisionRequest {
  return {
    base_revision_id: draft.baseId,
    name: draft.name.trim(), description: draft.description.trim(),
    instructions: draft.kind === 'skill' ? draft.body.trim() : null,
    content: draft.kind === 'skill' ? null : draft.body.trim(),
    file_name: draft.kind === 'file' ? draft.fileName.trim() : null,
  };
}

function makeDraft(detail: ResourceDetail): RevisionDraft {
  const { revision } = detail;
  return {
    kind: detail.kind, baseId: revision.id, baseNumber: revision.number,
    name: revision.name, description: revision.description,
    body: (detail.kind === 'skill' ? revision.instructions : revision.content) ?? '',
    fileName: revision.file_name ?? '',
  };
}

function load(state: RevisionState, revisionId: string | null, purpose: 'view' | 'edit'): Result {
  const pending = { seq: state.seq + 1, revisionId, purpose };
  return next<RevisionState, RevisionEffect>(
    { ...state, seq: pending.seq, pending, lastLoad: pending, loadError: null },
    { type: 'load', resourceId: state.resourceId, load: pending },
  );
}

const sameBody = (a: RevisionRequest, b: RevisionRequest) =>
  a.base_revision_id === b.base_revision_id && a.name === b.name && a.description === b.description &&
  a.instructions === b.instructions && a.content === b.content && a.file_name === b.file_name;

export const revisionReducer: Reducer<RevisionState, RevisionIntent, RevisionEffect> = (state, intent) => {
  switch (intent.type) {
    case 'opened': {
      if (state.seq !== 0) return next(state);
      const started = load(state, null, 'view');
      return next(started.state, ...started.effects, { type: 'authors', projectId: state.projectId });
    }
    case 'refresh':
      // Never replace a draft, or interrupt the latest-version read that establishes its base.
      if (state.draft || state.saving || state.pending?.purpose === 'edit') return next(state);
      return load(state, state.detail?.revision.id ?? null, 'view');
    case 'retryLoad':
      return state.saving ? next(state) : load(state, state.lastLoad.revisionId, state.lastLoad.purpose);
    case 'viewRequested':
      if (state.saving || state.phase !== 'detail') return next(state);
      return load(state, intent.revisionId, 'view');
    case 'editRequested':
      if (state.saving || state.pending || state.draft || !state.detail) return next(state);
      // Editing always begins with a fresh read of the latest version, even from history.
      return load({ ...state, notice: null }, null, 'edit');
    case 'checkLatest':
      if (state.saving || !state.draft) return next(state);
      return load({ ...state, phase: 'detail', fileReading: false, fileSeq: state.fileSeq + 1 }, null, 'view');
    case 'resumeDraft':
      return state.draft && !state.saving
        ? next({ ...state, phase: 'edit', pending: null, seq: state.seq + 1, loadError: null })
        : next(state);
    case 'cancelEdit':
      if (state.saving) return next(state);
      return next({ ...state, phase: 'detail', draft: null, saveError: null, lastAttempt: null, showProblems: false, fileReading: false, fileSeq: state.fileSeq + 1, fileProblem: null });
    case 'loaded': {
      if (intent.seq !== state.pending?.seq || intent.detail.id !== state.resourceId) return next(state);
      if (state.pending.purpose === 'edit') {
        return next({ ...state, phase: 'edit', pending: null, detail: intent.detail, loadError: null,
          draft: makeDraft(intent.detail), saveError: null, lastAttempt: null, showProblems: false, fileProblem: null });
      }
      return next({ ...state, detail: intent.detail, pending: null, loadError: null });
    }
    case 'loadFailed':
      if (intent.seq !== state.pending?.seq || intent.error.kind === 'aborted') return next(state);
      return next({ ...state, pending: null, loadError: intent.error });
    case 'authorsLoaded':
      return next({ ...state, authors: intent.authors });
    case 'fieldChanged':
      if (state.phase !== 'edit' || !state.draft || state.saving || state.fileReading) return next(state);
      return next({ ...state, draft: { ...state.draft, [intent.field]: intent.value }, saveError: null });
    case 'saveRequested': {
      if (state.phase !== 'edit' || !state.draft || state.saving || state.fileReading || state.fileProblem) return next(state);
      if (revisionHasProblems(state.draft)) return next({ ...state, showProblems: true });
      const body = revisionBody(state.draft);
      const attempt = state.lastAttempt && sameBody(state.lastAttempt.body, body)
        ? state.lastAttempt : { key: intent.key, body };
      return next<RevisionState, RevisionEffect>(
        { ...state, saving: true, lastAttempt: attempt, saveError: null, showProblems: true, notice: null },
        { type: 'save', resourceId: state.resourceId, kind: state.draft.kind, baseNumber: state.draft.baseNumber, attempt },
      );
    }
    case 'saved': {
      if (!state.saving || state.lastAttempt?.key !== intent.key || !state.detail) return next(state);
      const { revision, created } = intent.result;
      const entry = ({ id, number, name, created_by, created_at }: ResourceRevision) => ({ id, number, name, created_by, created_at });
      const revisions = state.detail.revisions.some(item => item.id === revision.id)
        ? state.detail.revisions : [...state.detail.revisions, entry(revision)];
      const saved: RevisionState = {
        ...state, phase: 'detail', saving: false, draft: null, saveError: null,
        lastAttempt: null, showProblems: false, fileProblem: null, notice: created ? 'saved' : 'unchanged',
        detail: { ...state.detail, revision, revisions, latest_revision_id: revision.id },
      };
      // The response is shown immediately; re-read the authoritative complete history separately.
      return load(saved, revision.id, 'view');
    }
    case 'saveFailed':
      if (!state.saving || state.lastAttempt?.key !== intent.key) return next(state);
      return next({ ...state, saving: false, saveError: intent.error });
    case 'fileChosen': {
      if (state.phase !== 'edit' || !state.draft || state.draft.kind !== 'file' || state.saving) return next(state);
      const seq = state.fileSeq + 1;
      return next<RevisionState, RevisionEffect>({ ...state, fileSeq: seq, fileReading: true, fileProblem: null }, { type: 'readFile', file: intent.file, seq });
    }
    case 'fileLoaded':
      if (state.phase !== 'edit' || !state.draft || !state.fileReading || intent.seq !== state.fileSeq) return next(state);
      return next({ ...state, fileReading: false, fileProblem: null, saveError: null,
        draft: { ...state.draft, fileName: intent.name, body: intent.content } });
    case 'fileRejected':
      if (!state.fileReading || intent.seq !== state.fileSeq) return next(state);
      return next({ ...state, fileReading: false, fileProblem: intent.problem });
  }
};
