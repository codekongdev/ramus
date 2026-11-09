import { api, errorMessage, SYSTEM_ERROR_MESSAGE, toResult, type AppApi } from '../../lib/api';
import type { EffectHandler } from '../../lib/mvi';
import { parseProjectResults } from './contract';
import type { ResultsLibraryEffect, ResultsLibraryIntent } from './model';

export function makeResultsLibraryEffects(client: AppApi = api): EffectHandler<ResultsLibraryEffect, ResultsLibraryIntent> {
  let pending: AbortController | null = null;
  return async (effect, dispatch, signal) => {
    pending?.abort();
    const controller = new AbortController();
    pending = controller;
    const abort = () => controller.abort();
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) controller.abort();
    try {
      const result = await toResult(client.GET('/api/projects/{project_id}/results', {
        params: { path: { project_id: effect.projectId } }, signal: controller.signal,
      }));
      if (controller.signal.aborted) return;
      if (!result.ok) {
        const error = errorMessage(result.error);
        if (error) dispatch({ type: 'failed', request: effect.request, error });
        return;
      }
      try {
        const { items } = parseProjectResults(result.data);
        dispatch({ type: 'loaded', request: effect.request, items });
      } catch {
        dispatch({ type: 'failed', request: effect.request, error: SYSTEM_ERROR_MESSAGE });
      }
    } finally {
      signal.removeEventListener('abort', abort);
      if (pending === controller) pending = null;
    }
  };
}
