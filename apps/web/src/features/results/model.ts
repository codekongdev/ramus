import type { components } from '../../api/schema';
import type { ProjectEvent } from '../../lib/events';
import { next, type Next } from '../../lib/mvi';
import type { Result, ResultRevision } from './contract';
import { resultMessages as messages } from './messages';

type Task = components['schemas']['Task'];
export type Editor = { readonly text: string; readonly baseVersion: number; readonly dirty: boolean; readonly sourceRunId: string };
export type Mutation = { readonly kind: 'summary'; readonly key: string }
  | { readonly kind: 'save'; readonly key: string; readonly conclusion: string; readonly baseVersion: number; readonly sourceRunId: string };
export type ResultState = {
  readonly taskId: string;
  readonly taskStatus: Task['status'] | null;
  readonly resultId: string | null;
  readonly result: Result | null;
  readonly approved: ResultRevision | null;
  readonly viewed: ResultRevision | null;
  readonly editor: Editor | null;
  readonly loading: boolean;
  readonly request: number;
  readonly revisionRequest: number;
  readonly error: string | null;
  readonly conflict: boolean;
  readonly notice: string | null;
  readonly mutation: Mutation | null;
  readonly failedMutation: Mutation | null;
};
export type ResultEffect =
  | { readonly type: 'load'; readonly taskId: string; readonly resultId: string; readonly request: number }
  | { readonly type: 'revision'; readonly taskId: string; readonly resultId: string; readonly revisionId: string; readonly request: number }
  | { readonly type: 'mutate'; readonly taskId: string; readonly resultId: string | null; readonly mutation: Mutation };
export type ResultIntent =
  | { readonly type: 'taskChanged'; readonly task: Task }
  | { readonly type: 'refresh' }
  | { readonly type: 'loaded'; readonly taskId: string; readonly request: number; readonly result: Result; readonly approved: ResultRevision | null }
  | { readonly type: 'loadFailed'; readonly taskId: string; readonly request: number; readonly message: string }
  | { readonly type: 'summarize'; readonly key: string }
  | { readonly type: 'summarySucceeded'; readonly taskId: string; readonly key: string; readonly result: Result }
  | { readonly type: 'save'; readonly key: string }
  | { readonly type: 'saved'; readonly taskId: string; readonly key: string; readonly revision: ResultRevision }
  | { readonly type: 'mutationFailed'; readonly taskId: string; readonly key: string; readonly message: string; readonly conflict: boolean }
  | { readonly type: 'mutationCancelled'; readonly taskId: string; readonly key: string }
  | { readonly type: 'editChanged'; readonly text: string }
  | { readonly type: 'editApproved' }
  | { readonly type: 'cancelEdit' }
  | { readonly type: 'rebase' }
  | { readonly type: 'selectRevision'; readonly revisionId: string }
  | { readonly type: 'revisionLoaded'; readonly taskId: string; readonly request: number; readonly revision: ResultRevision }
  | { readonly type: 'revisionFailed'; readonly taskId: string; readonly request: number; readonly message: string }
  | { readonly type: 'serverEvent'; readonly event: ProjectEvent };

export const initialResultState = (taskId: string): ResultState => ({
  taskId, taskStatus: null, resultId: null, result: null, approved: null, viewed: null, editor: null,
  loading: false, request: 0, revisionRequest: 0, error: null, conflict: false, notice: null, mutation: null, failedMutation: null,
});
export const generating = (state: ResultState) => state.result?.draft?.status === 'generating' || state.mutation?.kind === 'summary';
export const latestSourceRunId = (state: ResultState) => state.result?.draft?.status === 'ready'
  ? state.result.draft.run_id : state.approved?.source.run_id ?? null;
function refresh(state: ResultState): Next<ResultState, ResultEffect> {
  if (!state.resultId) return next(state);
  const request = state.request + 1;
  return next({ ...state, request, loading: true }, { type: 'load', taskId: state.taskId, resultId: state.resultId, request });
}
function editorFor(result: Result): Editor | null {
  const draft = result.draft;
  return draft?.status === 'ready' && draft.conclusion !== null && draft.base_version === (result.latest_version ?? 0)
    ? { text: draft.conclusion, baseVersion: draft.base_version, sourceRunId: draft.run_id, dirty: false } : null;
}
export function resultReducer(state: ResultState, intent: ResultIntent): Next<ResultState, ResultEffect> {
  switch (intent.type) {
    case 'taskChanged': {
      if (intent.task.id !== state.taskId) return refresh({ ...initialResultState(intent.task.id), taskStatus: intent.task.status, resultId: intent.task.result_id, request: state.request });
      const changed = intent.task.result_id !== null && intent.task.result_id !== state.resultId;
      const updated = { ...state, taskStatus: intent.task.status, resultId: intent.task.result_id ?? state.resultId };
      return changed ? refresh(updated) : next(updated);
    }
    case 'refresh': return refresh(state);
    case 'loaded': {
      if (intent.taskId !== state.taskId || intent.request !== state.request) return next(state);
      const retain = state.editor && (state.editor.dirty || state.conflict);
      return next({ ...state, result: intent.result, approved: intent.approved, viewed: intent.approved,
        editor: retain ? state.editor : editorFor(intent.result), loading: false,
        error: state.conflict ? messages.conflict : null });
    }
    case 'loadFailed':
      if (intent.taskId !== state.taskId || intent.request !== state.request) return next(state);
      return next({ ...state, loading: false, error: intent.message });
    case 'summarize': {
      if (state.taskStatus !== 'ready' || state.mutation || generating(state) || state.editor?.dirty) return next(state);
      const mutation: Mutation = state.failedMutation?.kind === 'summary' ? state.failedMutation : { kind: 'summary', key: intent.key };
      return next({ ...state, mutation, error: null, notice: null }, { type: 'mutate', taskId: state.taskId, resultId: state.resultId, mutation });
    }
    case 'summarySucceeded':
      if (intent.taskId !== state.taskId || state.mutation?.key !== intent.key) return next(state);
      return refresh({ ...state, resultId: intent.result.id, result: intent.result, editor: state.editor?.dirty ? state.editor : editorFor(intent.result), mutation: null, failedMutation: null, conflict: false });
    case 'save': {
      const editor = state.editor;
      if (!editor?.text.trim() || !state.resultId || state.mutation || generating(state) || state.conflict) return next(state);
      const mutation: Mutation = state.failedMutation?.kind === 'save' && state.failedMutation.conclusion === editor.text.trim() && state.failedMutation.baseVersion === editor.baseVersion && state.failedMutation.sourceRunId === editor.sourceRunId
        ? state.failedMutation : { kind: 'save', key: intent.key, conclusion: editor.text.trim(), baseVersion: editor.baseVersion, sourceRunId: editor.sourceRunId };
      return next({ ...state, mutation, error: null, notice: null }, { type: 'mutate', taskId: state.taskId, resultId: state.resultId, mutation });
    }
    case 'saved': {
      if (intent.taskId !== state.taskId || state.mutation?.kind !== 'save' || state.mutation.key !== intent.key) return next(state);
      const editor = state.editor && state.editor.text.trim() !== state.mutation.conclusion
        ? { ...state.editor, baseVersion: intent.revision.version } : null;
      const result = state.result && { ...state.result, latest_version: intent.revision.version, latest_revision_id: intent.revision.id,
        revisions: [...state.result.revisions.filter(revision => revision.id !== intent.revision.id), { id: intent.revision.id, version: intent.revision.version, saved_by: intent.revision.saved_by, created_at: intent.revision.created_at }] };
      return refresh({ ...state, result, approved: intent.revision, viewed: intent.revision, editor, mutation: null, failedMutation: null, conflict: false, notice: messages.saved(intent.revision.version) });
    }
    case 'mutationCancelled':
      return intent.taskId === state.taskId && state.mutation?.key === intent.key ? next({ ...state, mutation: null }) : next(state);
    case 'mutationFailed': {
      if (intent.taskId !== state.taskId || state.mutation?.key !== intent.key) return next(state);
      const updated = { ...state, failedMutation: intent.conflict ? null : state.mutation, mutation: null, conflict: intent.conflict, error: intent.conflict ? messages.conflict : intent.message };
      return intent.conflict ? refresh(updated) : next(updated);
    }
    case 'editChanged':
      return state.editor ? next({ ...state, editor: { ...state.editor, text: intent.text, dirty: true }, failedMutation: null, notice: null }) : next(state);
    case 'editApproved':
      return state.approved && !state.mutation && !generating(state) ? next({ ...state, editor: { text: state.approved.conclusion, baseVersion: state.approved.version, sourceRunId: state.approved.source.run_id, dirty: true }, conflict: false, error: null, notice: null, failedMutation: null }) : next(state);
    case 'cancelEdit': return state.mutation ? next(state) : next({ ...state, editor: state.result ? editorFor(state.result) : null, conflict: false, error: null, failedMutation: null });
    case 'rebase': {
      const sourceRunId = latestSourceRunId(state);
      return state.conflict && !state.loading && !generating(state) && state.result && state.editor && sourceRunId
        ? next({ ...state, editor: { ...state.editor, baseVersion: state.result.latest_version ?? 0, sourceRunId }, conflict: false, error: null, failedMutation: null }) : next(state);
    }
    case 'selectRevision': {
      if (!state.resultId || !state.result?.revisions.some(revision => revision.id === intent.revisionId)) return next(state);
      const request = state.revisionRequest + 1;
      return next({ ...state, revisionRequest: request }, { type: 'revision', taskId: state.taskId, resultId: state.resultId, revisionId: intent.revisionId, request });
    }
    case 'revisionLoaded':
      return intent.taskId === state.taskId && intent.request === state.revisionRequest ? next({ ...state, viewed: intent.revision }) : next(state);
    case 'revisionFailed':
      return intent.taskId === state.taskId && intent.request === state.revisionRequest ? next({ ...state, error: intent.message }) : next(state);
    case 'serverEvent': {
      const event = intent.event;
      if (event.type !== 'result.updated' || event.data.task_id !== state.taskId) return next(state);
      return refresh({ ...state, resultId: event.data.result_id });
    }
  }
}
