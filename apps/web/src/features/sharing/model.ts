import type { components } from '../../api/schema';
import { errorMessage, hasErrorCode, type ApiError } from '../../lib/api';
import { next, type Reducer } from '../../lib/mvi';
import { sharingMessages as m } from './conversationMessages';

export type Project = components['schemas']['Project'];
export type Conversation = components['schemas']['Conversation'];
export type Creation = {
  readonly key: string;
  readonly projectId: string;
  readonly revisionId: string;
  readonly title: string;
};
export type State = {
  readonly revisionId: string;
  readonly query: string;
  readonly request: number;
  readonly loading: boolean;
  readonly projects: readonly Project[];
  readonly selected: Project | null;
  readonly title: string;
  readonly searchError: string | null;
  readonly createError: string | null;
  readonly operation: Creation | null;
  readonly creating: boolean;
  readonly completed: boolean;
};
export type Intent =
  | { readonly type: 'search' }
  | { readonly type: 'queryChanged' | 'titleChanged'; readonly value: string }
  | { readonly type: 'loaded'; readonly request: number; readonly projects: readonly Project[] }
  | { readonly type: 'searchFailed'; readonly request: number; readonly error: ApiError }
  | { readonly type: 'select'; readonly projectId: string }
  | { readonly type: 'submit'; readonly key: string }
  | { readonly type: 'created'; readonly key: string; readonly conversation: Conversation }
  | { readonly type: 'createFailed'; readonly key: string; readonly error: ApiError };
export type Effect =
  | { readonly type: 'search'; readonly query: string; readonly request: number }
  | { readonly type: 'create'; readonly operation: Creation }
  | { readonly type: 'navigate'; readonly conversation: Conversation };

export const initialState = (revisionId: string): State => ({
  revisionId, query: '', request: 0, loading: false, projects: [], selected: null,
  title: '', searchError: null, createError: null, operation: null, creating: false, completed: false,
});
export const MAX_TITLE_LENGTH = 100;
export const canCreate = (state: State): boolean => Boolean(state.selected && state.title.trim()
  && Array.from(state.title.trim()).length <= MAX_TITLE_LENGTH && !state.creating && !state.completed);

export const reducer: Reducer<State, Intent, Effect> = (state, intent) => {
  switch (intent.type) {
    case 'search':
    case 'queryChanged': {
      if (state.creating || state.completed) return next(state);
      const query = intent.type === 'queryChanged' ? intent.value : state.query;
      const request = state.request + 1;
      return next({ ...state, query, request, loading: true, projects: [], searchError: null },
        { type: 'search', query: query.trim(), request });
    }
    case 'loaded':
      return intent.request === state.request
        ? next({ ...state, projects: intent.projects, loading: false, searchError: null }) : next(state);
    case 'searchFailed':
      return intent.request === state.request
        ? next({ ...state, loading: false, searchError: errorMessage(intent.error) }) : next(state);
    case 'select': {
      const selected = state.projects.find(project => project.id === intent.projectId);
      return selected && !state.creating && !state.completed
        ? next({ ...state, selected, createError: null }) : next(state);
    }
    case 'titleChanged':
      return state.creating || state.completed ? next(state) : next({ ...state, title: intent.value, createError: null });
    case 'submit': {
      if (!canCreate(state) || !state.selected) return next(state);
      const title = state.title.trim();
      const prior = state.operation;
      const operation = prior && prior.title === title && prior.projectId === state.selected.id
        ? prior : { key: intent.key, projectId: state.selected.id, revisionId: state.revisionId, title };
      return next({ ...state, operation, creating: true, createError: null }, { type: 'create', operation });
    }
    case 'created':
      if (!state.creating || intent.key !== state.operation?.key) return next(state);
      return next({ ...state, creating: false, completed: true }, { type: 'navigate', conversation: intent.conversation });
    case 'createFailed': {
      if (!state.creating || intent.key !== state.operation?.key) return next(state);
      const forbidden = hasErrorCode(intent.error, 'PROJECT_CREATE_FORBIDDEN');
      return next({ ...state, creating: false, selected: forbidden ? null : state.selected,
        createError: forbidden ? m.permission : errorMessage(intent.error) });
    }
  }
};
