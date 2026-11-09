import { errorMessage, SYSTEM_ERROR_MESSAGE, toResult, type AppApi } from '../../lib/api';
import type { EffectHandler } from '../../lib/mvi';
import { parseResultRevision } from '../results/contract';
import { parseInputs } from './contract';
import type { ReceivedEffect, ReceivedIntent, RevisionEffect, RevisionIntent } from './receivedModel';

class SharingRequestError extends Error {}
export function makeReceivedEffectHandler(client: AppApi): EffectHandler<ReceivedEffect, ReceivedIntent> {
  return async (effect, dispatch, signal) => {
    try {
      const result = await toResult(client.GET('/api/conversations/{conversation_id}/inputs', { params: { path: { conversation_id: effect.conversationId } }, signal }));
      if (!result.ok) throw new SharingRequestError(errorMessage(result.error) ?? SYSTEM_ERROR_MESSAGE);
      const items = parseInputs(result.data).items;
      if (items.some(item => item.conversation_id !== effect.conversationId || item.latest_version < item.version)
        || new Set(items.map(item => item.result_id)).size !== items.length) throw new Error();
      if (!signal.aborted) dispatch({ type: 'loaded', conversationId: effect.conversationId, request: effect.request, items });
    } catch (error) {
      if (!signal.aborted) dispatch({ type: 'failed', conversationId: effect.conversationId, request: effect.request, message: error instanceof SharingRequestError ? error.message : SYSTEM_ERROR_MESSAGE });
    }
  };
}
export function makeRevisionEffectHandler(client: AppApi): EffectHandler<RevisionEffect, RevisionIntent> {
  return async (effect, dispatch, signal) => {
    try {
      const result = await toResult(client.GET('/api/result-revisions/{result_revision_id}', { params: { path: { result_revision_id: effect.input.result_revision_id } }, signal }));
      if (!result.ok) throw new SharingRequestError(errorMessage(result.error) ?? SYSTEM_ERROR_MESSAGE);
      const revision = parseResultRevision(result.data);
      if (revision.id !== effect.input.result_revision_id || revision.result_id !== effect.input.result_id || revision.version !== effect.input.version) throw new Error();
      if (!signal.aborted) dispatch({ type: 'loaded', request: effect.request, revision });
    } catch (error) {
      if (!signal.aborted) dispatch({ type: 'failed', request: effect.request, message: error instanceof SharingRequestError ? error.message : SYSTEM_ERROR_MESSAGE });
    }
  };
}
