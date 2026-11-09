import { api, type AppApi } from '../../lib/api/app';
import { toResult } from '../../lib/api/client';
import { errorMessage, SYSTEM_ERROR_MESSAGE } from '../../lib/api/result';
import { parseConversationList } from '../../lib/api/task-contract';
import type { EffectHandler } from '../../lib/mvi';
import type { Effect, Intent } from './model';
export function makeEffects(client: AppApi = api): EffectHandler<Effect, Intent> {
  return async (effect, dispatch, signal) => {
    const result = await toResult(client.GET('/api/projects/{project_id}/conversations', {
      params: { path: { project_id: effect.projectId } }, signal,
    }));
    if (!result.ok) {
      const error = errorMessage(result.error);
      if (error) dispatch({ type: 'failed', request: effect.request, error });
      return;
    }
    try {
      const items = parseConversationList(result.data).items;
      if (items.some((item) => item.project_id !== effect.projectId)) throw new Error('Wrong project');
      dispatch({ type: 'loaded', request: effect.request, items });
    } catch {
      dispatch({ type: 'failed', request: effect.request, error: SYSTEM_ERROR_MESSAGE });
    }
  };
}
