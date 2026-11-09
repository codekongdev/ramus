import { SYSTEM_ERROR_MESSAGE, toResult, type AppApi } from '../../lib/api';
import { parseConversation } from '../../lib/api/task-contract';
import type { EffectHandler } from '../../lib/mvi';
import { isProjects, validated } from '../auth/api';
import type { Conversation, Effect, Intent } from './model';

export function makeEffects(client: AppApi, onCreated: (conversation: Conversation) => void): EffectHandler<Effect, Intent> {
  return async (effect, dispatch, signal) => {
    if (signal.aborted) return;
    if (effect.type === 'navigate') {
      onCreated(effect.conversation);
    } else if (effect.type === 'search') {
      const result = validated(await toResult(client.GET('/api/projects/search', {
        params: { query: { q: effect.query } }, signal,
      })), isProjects);
      if (!signal.aborted) dispatch(result.ok
        ? { type: 'loaded', request: effect.request, projects: result.data.items }
        : { type: 'searchFailed', request: effect.request, error: result.error });
    } else {
      const { operation } = effect;
      const result = await toResult(client.POST('/api/projects/{project_id}/conversations/from-result', {
        params: { path: { project_id: operation.projectId } },
        body: { result_revision_id: operation.revisionId, title: operation.title },
        headers: { 'Idempotency-Key': operation.key }, signal,
      }));
      if (signal.aborted) return;
      if (!result.ok) {
        dispatch({ type: 'createFailed', key: operation.key, error: result.error });
        return;
      }
      try {
        const conversation = parseConversation(result.data);
        if (conversation.project_id !== operation.projectId || conversation.parent_id !== null
          || conversation.task_id !== null || conversation.title !== operation.title) throw new Error(SYSTEM_ERROR_MESSAGE);
        dispatch({ type: 'created', key: operation.key, conversation });
      } catch {
        dispatch({ type: 'createFailed', key: operation.key,
          error: { kind: 'system', status: 502, code: null, message: null, details: null } });
      }
    }
  };
}
