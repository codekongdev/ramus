import type { components } from '../../api/schema';
import type { ApiError } from '../../lib/api';
import type { ResourceDetail, ResourceKind } from './model';
import type { SkillFileProblem } from './skillFile';

export type ResourceRevision = components['schemas']['ResourceRevision'];
export type RevisionRequest = components['schemas']['CreateResourceRevisionRequest'];
export type SavedResourceRevision = components['schemas']['CreateResourceRevisionResponse'];
export type RevisionField = 'name' | 'description' | 'body' | 'fileName';
export type RevisionProblem = 'required' | 'tooLong' | 'invalidText' | 'extension';
export type RevisionProblems = Partial<Record<RevisionField, RevisionProblem>>;
export type RevisionDraft = {
  readonly kind: ResourceKind;
  readonly baseId: string;
  readonly baseNumber: number;
  readonly name: string;
  readonly description: string;
  readonly body: string;
  readonly fileName: string;
};
export type RevisionLoad = {
  readonly seq: number;
  readonly revisionId: string | null;
  readonly purpose: 'view' | 'edit';
};
export type RevisionAttempt = {
  readonly key: string;
  readonly body: RevisionRequest;
};
export type RevisionState = {
  readonly resourceId: string;
  readonly projectId: string;
  readonly phase: 'detail' | 'edit';
  readonly detail: ResourceDetail | null;
  readonly authors: Readonly<Record<string, string>>;
  readonly seq: number;
  readonly pending: RevisionLoad | null;
  readonly loadError: ApiError | null;
  readonly lastLoad: RevisionLoad;
  /** Kept while checking the latest version after a conflict. */
  readonly draft: RevisionDraft | null;
  readonly saving: boolean;
  readonly saveError: ApiError | null;
  readonly lastAttempt: RevisionAttempt | null;
  readonly showProblems: boolean;
  readonly notice: 'saved' | 'unchanged' | null;
  readonly fileSeq: number;
  readonly fileReading: boolean;
  readonly fileProblem: SkillFileProblem | null;
};

export type RevisionIntent =
  | { readonly type: 'opened' | 'refresh' | 'retryLoad' | 'editRequested' | 'cancelEdit' | 'resumeDraft' | 'checkLatest' }
  | { readonly type: 'viewRequested'; readonly revisionId: string }
  | { readonly type: 'loaded'; readonly seq: number; readonly detail: ResourceDetail }
  | { readonly type: 'loadFailed'; readonly seq: number; readonly error: ApiError }
  | { readonly type: 'authorsLoaded'; readonly authors: Readonly<Record<string, string>> }
  | { readonly type: 'fieldChanged'; readonly field: RevisionField; readonly value: string }
  | { readonly type: 'saveRequested'; readonly key: string }
  | { readonly type: 'saved'; readonly key: string; readonly result: SavedResourceRevision }
  | { readonly type: 'saveFailed'; readonly key: string; readonly error: ApiError }
  | { readonly type: 'fileChosen'; readonly file: File }
  | { readonly type: 'fileLoaded'; readonly seq: number; readonly name: string; readonly content: string }
  | { readonly type: 'fileRejected'; readonly seq: number; readonly problem: SkillFileProblem };

export type RevisionEffect =
  | { readonly type: 'load'; readonly resourceId: string; readonly load: RevisionLoad }
  | { readonly type: 'authors'; readonly projectId: string }
  | { readonly type: 'save'; readonly resourceId: string; readonly kind: ResourceKind; readonly baseNumber: number; readonly attempt: RevisionAttempt }
  | { readonly type: 'readFile'; readonly file: File; readonly seq: number };

export function initialRevisionState(resourceId: string, projectId: string): RevisionState {
  return {
    resourceId, projectId, phase: 'detail', detail: null, authors: {}, seq: 0,
    pending: null, loadError: null, lastLoad: { seq: 0, revisionId: null, purpose: 'view' },
    draft: null, saving: false, saveError: null, lastAttempt: null, showProblems: false,
    notice: null, fileSeq: 0, fileReading: false, fileProblem: null,
  };
}
