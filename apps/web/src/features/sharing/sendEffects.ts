import { errorMessage, SYSTEM_ERROR_MESSAGE, toResult, type AppApi } from '../../lib/api';
import { parseConversationList } from '../../lib/api/task-contract';
import type { EffectHandler } from '../../lib/mvi';
import { parseOutcomes } from './contract';
import type { SendEffect, SendIntent } from './sendModel';

class SharingRequestError extends Error {}
export function makeSendEffectHandler(client: AppApi): EffectHandler<SendEffect, SendIntent> {
  return async (effect, dispatch, signal) => {
    if (effect.type === 'expireNotice') {
      const timer = setTimeout(() => { if (!signal.aborted) dispatch({ type: 'dismissNotice', id: effect.id }); }, 4500);
      signal.addEventListener('abort', () => clearTimeout(timer), { once: true });
      return;
    }
    try {
      if (effect.type === 'search') {
        const result = await toResult(client.GET('/api/projects/{project_id}/conversations/search', { params: { path: { project_id: effect.target.projectId },
          query: { q: effect.query.trim(), exclude_id: effect.target.revision.source.conversation_id } }, signal }));
        if (!result.ok) throw new SharingRequestError(errorMessage(result.error) ?? SYSTEM_ERROR_MESSAGE);
        const matches = parseConversationList(result.data).items;
        if (!signal.aborted) dispatch({ type: 'matches', request: effect.request, matches });
      } else {
        const { mutation } = effect;
        const result = await toResult(client.POST('/api/result-revisions/{result_revision_id}/shares', { params: { path: { result_revision_id: mutation.revisionId } },
          body: { conversation_ids: mutation.conversationIds }, headers: { 'Idempotency-Key': mutation.key }, signal }));
        if (!result.ok) throw new SharingRequestError(errorMessage(result.error) ?? SYSTEM_ERROR_MESSAGE);
        const outcomes = parseOutcomes(result.data);
        if (outcomes.items.length !== mutation.conversationIds.length || new Set(outcomes.items.map(item => item.conversation_id)).size !== outcomes.items.length
          || outcomes.items.some(item => !mutation.conversationIds.includes(item.conversation_id))) throw new Error(SYSTEM_ERROR_MESSAGE);
        if (!signal.aborted) dispatch({ type: 'sent', key: mutation.key, outcomes });
      }
    } catch (error) {
      if (signal.aborted) return;
      const message = error instanceof SharingRequestError ? error.message : SYSTEM_ERROR_MESSAGE;
      if (effect.type === 'search') dispatch({ type: 'searchFailed', request: effect.request, message });
      else dispatch({ type: 'sendFailed', key: effect.mutation.key, message });
    }
  };
}
