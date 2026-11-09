import { next, type Next } from '../../lib/mvi';
import type { ResultRevision } from './contract';

export type ConclusionState = {
  readonly revisionId: string;
  readonly revision: ResultRevision | null;
  readonly loading: boolean;
  readonly request: number;
  readonly error: string | null;
};
export type ConclusionEffect = { readonly type: 'load'; readonly revisionId: string; readonly request: number };
export type ConclusionIntent =
  | { readonly type: 'open'; readonly revisionId: string }
  | { readonly type: 'retry' }
  | { readonly type: 'loaded'; readonly revisionId: string; readonly request: number; readonly revision: ResultRevision }
  | { readonly type: 'failed'; readonly revisionId: string; readonly request: number; readonly message: string };

export const initialConclusionState = (revisionId: string): ConclusionState => ({
  revisionId, revision: null, loading: false, request: 0, error: null,
});

function load(state: ConclusionState): Next<ConclusionState, ConclusionEffect> {
  const request = state.request + 1;
  return next({ ...state, loading: true, request, error: null }, { type: 'load', revisionId: state.revisionId, request });
}

export function conclusionReducer(state: ConclusionState, intent: ConclusionIntent): Next<ConclusionState, ConclusionEffect> {
  switch (intent.type) {
    case 'open': return load({ ...initialConclusionState(intent.revisionId), request: state.request });
    case 'retry': return state.loading ? next(state) : load(state);
    case 'loaded':
      return intent.revisionId === state.revisionId && intent.revision.id === state.revisionId && intent.request === state.request
        ? next({ ...state, loading: false, revision: intent.revision, error: null }) : next(state);
    case 'failed':
      return intent.revisionId === state.revisionId && intent.request === state.request
        ? next({ ...state, loading: false, error: intent.message }) : next(state);
  }
}
