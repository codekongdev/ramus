import { toResult, type AppApi } from '../../lib/api';
import type { EffectHandler } from '../../lib/mvi';
import { isProject, isProjects, validated } from '../auth/api';
import type { Project, ProjectsEffect, ProjectsIntent } from './model';

export function makeProjectsEffects(client: AppApi, selectProject: (projectId: string) => void): EffectHandler<ProjectsEffect, ProjectsIntent> {
  return async (effect, dispatch, signal) => {
    if (signal.aborted) return;
    if (effect.type === 'navigate') {
      selectProject(effect.projectId);
    } else if (effect.type === 'load') {
      const result = validated(await toResult(client.GET('/api/projects', { signal })), isProjects);
      dispatch(result.ok
        ? { type: 'loaded', generation: effect.generation, items: result.data.items }
        : { type: 'loadFailed', generation: effect.generation, error: result.error });
    } else {
      const { operation } = effect;
      const result = validated(await toResult(client.POST('/api/projects', {
        body: { name: operation.name }, headers: { 'Idempotency-Key': operation.key }, signal,
      })), (value): value is Project => isProject(value) && !value.is_shared_sample && value.name === operation.name);
      dispatch(result.ok
        ? { type: 'created', key: operation.key, project: result.data }
        : { type: 'createFailed', key: operation.key, error: result.error });
    }
  };
}
