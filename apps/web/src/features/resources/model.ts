import type { components } from '../../api/schema';
import type { ApiError } from '../../lib/api';
import type { ProjectEvent } from '../../lib/events';
import type { ParsedSkill, SkillFileProblem } from './skillFile';

export type ResourceSummary = components['schemas']['ResourceSummary'];
export type AppliedResource = components['schemas']['AppliedResource'];
export type ResourceDetail = components['schemas']['ResourceDetail'];
export type CreateResourceRequest = components['schemas']['CreateResourceRequest'];
export type ResourceKind = ResourceSummary['kind'];

/** One chip: the exact revision this conversation will use (F-09 — never "latest"). */
export type SelectedRevision = {
  readonly resourceId: string;
  readonly revisionId: string;
  readonly number: number;
  readonly name: string;
  readonly kind: ResourceKind;
};

export type Loadable<T> =
  | { readonly status: 'loading' }
  | { readonly status: 'ready'; readonly data: T }
  | { readonly status: 'failed'; readonly error: ApiError };

export type SkillField = 'name' | 'description' | 'instructions';
export type FieldProblem = 'required' | 'tooLong';
export type SkillFormProblems = Partial<Record<SkillField, FieldProblem>>;

export type SkillForm = {
  readonly name: string;
  readonly description: string;
  readonly instructions: string;
  /** Validation messages show only after the first submit attempt. */
  readonly showProblems: boolean;
  readonly fileProblem: SkillFileProblem | null;
  readonly status: 'editing' | 'reading' | 'saving';
  readonly error: ApiError | null;
  /** Key of the last failed submit, reused when the same content is sent again. */
  readonly lastAttempt: { readonly key: string; readonly body: CreateResourceRequest } | null;
};

export type ApplyState = {
  readonly status: 'idle' | 'saving';
  readonly error: ApiError | null;
  readonly lastAttempt: { readonly key: string; readonly revisionIds: readonly string[] } | null;
};

export type ResourcesState = {
  readonly projectId: string;
  /** Null when no conversation is open: search and register work, applying does not. */
  readonly conversationId: string | null;
  readonly step: 'list' | 'register';
  readonly query: string;
  /** Incremented per search; late results with an older sequence are dropped. */
  readonly searchSeq: number;
  readonly search: Loadable<readonly ResourceSummary[]>;
  readonly applied: Loadable<readonly AppliedResource[]>;
  readonly appliedInitialized: boolean;
  readonly selection: readonly SelectedRevision[];
  /** True once the user changed the selection, so reloading `applied` no longer resets it. */
  readonly selectionTouched: boolean;
  readonly apply: ApplyState;
  readonly form: SkillForm;
  readonly fileSeq: number;
};

export type ResourcesIntent =
  | { readonly type: 'opened' }
  | { readonly type: 'queryChanged'; readonly query: string }
  | { readonly type: 'retrySearch' }
  | { readonly type: 'searchLoaded'; readonly seq: number; readonly items: readonly ResourceSummary[] }
  | { readonly type: 'searchFailed'; readonly seq: number; readonly error: ApiError }
  | { readonly type: 'retryApplied' }
  | { readonly type: 'appliedLoaded'; readonly items: readonly AppliedResource[] }
  | { readonly type: 'appliedFailed'; readonly error: ApiError }
  | { readonly type: 'toggled'; readonly resource: ResourceSummary }
  | { readonly type: 'latestChosen'; readonly resource: ResourceSummary }
  | { readonly type: 'deselected'; readonly resourceId: string }
  | { readonly type: 'applyRequested'; readonly key: string }
  | { readonly type: 'applySucceeded'; readonly items: readonly AppliedResource[] }
  | { readonly type: 'applyFailed'; readonly error: ApiError }
  | { readonly type: 'registerOpened' }
  | { readonly type: 'backToList' }
  | { readonly type: 'fieldChanged'; readonly field: SkillField; readonly value: string }
  | { readonly type: 'fileChosen'; readonly file: File }
  | { readonly type: 'fileLoaded'; readonly seq: number; readonly skill: ParsedSkill }
  | { readonly type: 'fileRejected'; readonly seq: number; readonly problem: SkillFileProblem }
  | { readonly type: 'registerRequested'; readonly key: string }
  | { readonly type: 'registerSucceeded'; readonly detail: ResourceDetail }
  | { readonly type: 'registerFailed'; readonly error: ApiError }
  | { readonly type: 'serverEvent'; readonly event: ProjectEvent }
  | { readonly type: 'resynced' };

export type ResourcesEffect =
  | {
      readonly type: 'search';
      readonly projectId: string;
      readonly conversationId: string | null;
      readonly query: string;
      readonly seq: number;
      /** Wait before requesting so typing does not fire a request per keystroke. */
      readonly debounce: boolean;
    }
  | { readonly type: 'loadApplied'; readonly conversationId: string }
  | {
      readonly type: 'apply';
      readonly conversationId: string;
      readonly revisionIds: readonly string[];
      readonly key: string;
    }
  | { readonly type: 'readFile'; readonly file: File; readonly seq: number }
  | {
      readonly type: 'create';
      readonly projectId: string;
      readonly body: CreateResourceRequest;
      readonly key: string;
    }
  | { readonly type: 'close' };

export const emptySkillForm: SkillForm = {
  name: '',
  description: '',
  instructions: '',
  showProblems: false,
  fileProblem: null,
  status: 'editing',
  error: null,
  lastAttempt: null,
};

export function initialResourcesState(projectId: string, conversationId: string | null): ResourcesState {
  return {
    projectId,
    conversationId,
    step: 'list',
    query: '',
    searchSeq: 0,
    search: { status: 'loading' },
    applied: { status: 'loading' },
    appliedInitialized: false,
    selection: [],
    selectionTouched: false,
    apply: { status: 'idle', error: null, lastAttempt: null },
    form: emptySkillForm,
    fileSeq: 0,
  };
}
