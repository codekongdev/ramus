import type { components } from '../../api/schema';
import { errorMessage, isUnauthorized, type ApiError } from '../../lib/api';
import { next, type Reducer } from '../../lib/mvi';
import { projectMessages as m } from './messages';

export type Project = components['schemas']['Project'];
export type Creation = { readonly key: string; readonly name: string };
export interface ProjectsState {
  readonly open: boolean;
  readonly mode: 'list' | 'create';
  readonly items: readonly Project[];
  readonly loading: boolean;
  readonly generation: number;
  readonly listError: string | null;
  readonly query: string;
  readonly name: string;
  readonly createError: string | null;
  readonly nameError: string | null;
  readonly operation: Creation | null;
  readonly creating: boolean;
  readonly unauthorized: boolean;
}
export const initialProjectsState: ProjectsState = {
  open: false, mode: 'list', items: [], loading: false, generation: 0,
  listError: null, query: '', name: '', createError: null, nameError: null,
  operation: null, creating: false, unauthorized: false,
};
export type ProjectsIntent =
  | { readonly type: 'open' | 'reload' | 'close' | 'showCreate' | 'showList' }
  | { readonly type: 'queryChanged' | 'nameChanged'; readonly value: string }
  | { readonly type: 'loaded'; readonly generation: number; readonly items: readonly Project[] }
  | { readonly type: 'loadFailed'; readonly generation: number; readonly error: ApiError }
  | { readonly type: 'select'; readonly projectId: string }
  | { readonly type: 'submit'; readonly key: string }
  | { readonly type: 'created'; readonly key: string; readonly project: Project }
  | { readonly type: 'createFailed'; readonly key: string; readonly error: ApiError };
export type ProjectsEffect =
  | { readonly type: 'load'; readonly generation: number }
  | { readonly type: 'create'; readonly operation: Creation }
  | { readonly type: 'navigate'; readonly projectId: string };

export const projectsReducer: Reducer<ProjectsState, ProjectsIntent, ProjectsEffect> = (state, intent) => {
  switch (intent.type) {
    case 'open':
    case 'reload': {
      if (state.loading) return next({ ...state, open: true });
      const generation = state.generation + 1;
      return next({ ...state, open: true, mode: 'list', loading: true, listError: null, generation }, { type: 'load', generation });
    }
    case 'close':
      return state.creating ? next(state) : next({ ...state, open: false });
    case 'showCreate':
    case 'showList':
      return state.creating ? next(state) : next({ ...state, mode: intent.type === 'showCreate' ? 'create' : 'list' });
    case 'queryChanged':
      return next({ ...state, query: intent.value });
    case 'nameChanged':
      return state.creating ? next(state) : next({ ...state, name: intent.value, nameError: null, createError: null });
    case 'loaded':
      if (intent.generation !== state.generation) return next(state);
      return next({ ...state, loading: false, listError: null, items: intent.items });
    case 'loadFailed':
      if (intent.generation !== state.generation) return next(state);
      return next({ ...state, loading: false, listError: errorMessage(intent.error), unauthorized: isUnauthorized(intent.error) });
    case 'select':
      if (!state.open || state.creating || !state.items.some(item => item.id === intent.projectId)) return next(state);
      return next({ ...state, open: false }, { type: 'navigate', projectId: intent.projectId });
    case 'submit': {
      if (!state.open || state.mode !== 'create' || state.creating) return next(state);
      const name = state.name.trim();
      if (!name || Array.from(name).length > 100) return next({ ...state, nameError: m.invalidName });
      // A retry of the same creation must reuse its key after a lost response.
      const operation = state.operation?.name === name ? state.operation : { key: intent.key, name };
      return next({ ...state, creating: true, operation, createError: null, nameError: null }, { type: 'create', operation });
    }
    case 'created':
      if (!state.creating || intent.key !== state.operation?.key) return next(state);
      return next({ ...initialProjectsState, items: [...state.items, intent.project], generation: state.generation }, { type: 'navigate', projectId: intent.project.id });
    case 'createFailed':
      if (!state.creating || intent.key !== state.operation?.key) return next(state);
      return next({ ...state, creating: false, createError: errorMessage(intent.error), unauthorized: isUnauthorized(intent.error) });
  }
};
