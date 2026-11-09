import type { components } from '../../api/schema';
import { errorMessage, isUnauthorized, toResult, type ApiError, type AppApi } from '../../lib/api';
import { next, type EffectHandler, type Reducer } from '../../lib/mvi';
import { isParticipants, isProjects, validated } from './api';
import type { Account } from './model';

type Project = components['schemas']['Project'];
export interface ParticipantsState {
  readonly projectId: string | null;
  readonly generation: number;
  readonly loading: boolean;
  readonly items: readonly Account[];
  readonly project: Project | null;
  readonly error: string | null;
  readonly unauthorized: boolean;
}
export const initialParticipantsState: ParticipantsState = { projectId: null, generation: 0, loading: false, items: [], project: null, error: null, unauthorized: false };
export type ParticipantsIntent =
  | { readonly type: 'load'; readonly projectId: string }
  | { readonly type: 'loaded'; readonly generation: number; readonly items: readonly Account[]; readonly project: Project | null }
  | { readonly type: 'failed'; readonly generation: number; readonly error: ApiError };
export type ParticipantsEffect = { readonly type: 'fetch'; readonly projectId: string; readonly generation: number };
export const participantsReducer: Reducer<ParticipantsState, ParticipantsIntent, ParticipantsEffect> = (state, intent) => {
  switch (intent.type) {
    case 'load': {
      if (state.projectId === intent.projectId && state.loading) return next(state);
      const generation = state.generation + 1;
      return next({ ...(state.projectId === intent.projectId ? state : initialParticipantsState), projectId: intent.projectId, generation, loading: true, error: null }, { type: 'fetch', projectId: intent.projectId, generation });
    }
    case 'loaded':
      if (state.generation !== intent.generation) return next(state);
      return next({ ...state, loading: false, items: intent.items, project: intent.project, error: null, unauthorized: false });
    case 'failed':
      if (state.generation !== intent.generation) return next(state);
      return next({ ...state, loading: false, error: errorMessage(intent.error), unauthorized: isUnauthorized(intent.error) });
  }
};
export function makeParticipantsEffects(client: AppApi): EffectHandler<ParticipantsEffect, ParticipantsIntent> {
  return async (effect, dispatch, signal) => {
    const [participants, projects] = await Promise.all([
      toResult(client.GET('/api/projects/{project_id}/participants', { params: { path: { project_id: effect.projectId } }, signal })),
      toResult(client.GET('/api/projects', { signal })),
    ]);
    const members = validated(participants, isParticipants);
    const list = validated(projects, isProjects);
    if (!members.ok) dispatch({ type: 'failed', generation: effect.generation, error: members.error });
    else if (!list.ok) dispatch({ type: 'failed', generation: effect.generation, error: list.error });
    else dispatch({ type: 'loaded', generation: effect.generation, items: members.data.items, project: list.data.items.find(project => project.id === effect.projectId) ?? null });
  };
}
