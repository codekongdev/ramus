import type { ProjectEvent } from '../../lib/events';
import { next, type Next } from '../../lib/mvi';
import type { ProjectResultSummary } from './contract';

export type ResultsLibraryState = {
  readonly projectId: string;
  readonly request: number;
  readonly status: 'loading' | 'ready' | 'failed';
  readonly items: readonly ProjectResultSummary[];
  readonly error: string | null;
};
export type ResultsLibraryIntent =
  | { readonly type: 'refresh' }
  | { readonly type: 'serverEvent'; readonly event: ProjectEvent }
  | { readonly type: 'loaded'; readonly request: number; readonly items: readonly ProjectResultSummary[] }
  | { readonly type: 'failed'; readonly request: number; readonly error: string };
export type ResultsLibraryEffect = { readonly type: 'load'; readonly projectId: string; readonly request: number };
export const initialResultsLibraryState = (projectId: string): ResultsLibraryState => ({
  projectId, request: 0, status: 'loading', items: [], error: null,
});

export function resultsLibraryReducer(state: ResultsLibraryState, intent: ResultsLibraryIntent): Next<ResultsLibraryState, ResultsLibraryEffect> {
  switch (intent.type) {
    case 'serverEvent':
      if (intent.event.type !== 'result.updated') return next(state);
      // Event payloads are invalidations; only the authenticated query supplies list rows.
      return resultsLibraryReducer(state, { type: 'refresh' });
    case 'refresh': {
      const request = state.request + 1;
      return next({ ...state, request, status: 'loading', items: [], error: null },
        { type: 'load', projectId: state.projectId, request });
    }
    case 'loaded':
      return intent.request === state.request
        ? next({ ...state, status: 'ready', items: intent.items, error: null }) : next(state);
    case 'failed':
      return intent.request === state.request
        ? next({ ...state, status: 'failed', items: [], error: intent.error }) : next(state);
  }
}
