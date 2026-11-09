import { errorMessage, SYSTEM_ERROR_MESSAGE, toResult, type AppApi } from '../../lib/api';
import type { EffectHandler } from '../../lib/mvi';
import { parseResultRevision } from './contract';
import type { ConclusionEffect, ConclusionIntent } from './conclusionModel';

/** This reader has no access to mutation or AI connection handlers. */
export function makeConclusionEffectHandler(client: AppApi): EffectHandler<ConclusionEffect, ConclusionIntent> {
  return async (effect, dispatch, signal) => {
    try {
      const response = await toResult(client.GET('/api/result-revisions/{result_revision_id}', {
        params: { path: { result_revision_id: effect.revisionId } }, signal,
      }));
      if (signal.aborted) return;
      if (!response.ok) {
        dispatch({ type: 'failed', revisionId: effect.revisionId, request: effect.request,
          message: errorMessage(response.error) ?? SYSTEM_ERROR_MESSAGE });
        return;
      }
      const revision = parseResultRevision(response.data);
      if (revision.id !== effect.revisionId) throw new Error('Unexpected revision');
      dispatch({ type: 'loaded', revisionId: effect.revisionId, request: effect.request, revision });
    } catch {
      if (!signal.aborted) dispatch({ type: 'failed', revisionId: effect.revisionId, request: effect.request, message: SYSTEM_ERROR_MESSAGE });
    }
  };
}
