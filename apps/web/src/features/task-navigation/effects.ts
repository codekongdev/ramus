import { api, type AppApi } from '../../lib/api/app';
import { toResult } from '../../lib/api/client';
import { errorMessage, SYSTEM_ERROR_MESSAGE } from '../../lib/api/result';
import { parseConversation, parseConversationList } from '../../lib/api/task-contract';
import type { EffectHandler } from '../../lib/mvi';
import type { Effect, Intent } from './model';
export function makeEffects(client: AppApi = api): EffectHandler<Effect, Intent> {
  return async (effect, dispatch, signal) => {
    if (effect.type === 'create') {
      const result = await toResult(client.POST('/api/projects/{project_id}/conversations', {
        params: { path: { project_id: effect.projectId } }, body: { title: effect.title },
        headers: { 'Idempotency-Key': effect.key }, signal,
      }));
      if (signal.aborted) return;
      if (!result.ok) {
        dispatch({ type: 'createFailed', key: effect.key, error: errorMessage(result.error) ?? SYSTEM_ERROR_MESSAGE });
        return;
      }
      try {
        const conversation = parseConversation(result.data);
        if (conversation.project_id !== effect.projectId || conversation.parent_id !== null || conversation.task_id !== null) throw new Error('Wrong conversation');
        dispatch({ type: 'created', key: effect.key, conversation });
      } catch {
        dispatch({ type: 'createFailed', key: effect.key, error: SYSTEM_ERROR_MESSAGE });
      }
      return;
    }
    const result = await toResult(client.GET('/api/projects/{project_id}/conversations', {
      params: { path: { project_id: effect.projectId } }, signal,
    }));
    if (signal.aborted) return;
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
