import { api, errorMessage, SYSTEM_ERROR_MESSAGE, toResult, type AppApi } from '../../lib/api';
import { parseConversationList } from '../../lib/api/task-contract';
import type { EffectHandler } from '../../lib/mvi';
import { parseProjectGraph } from './contract';
import type { Effect, Intent } from './model';
export function makeEffects(client: AppApi = api): EffectHandler<Effect, Intent> {
  let pending: AbortController | null = null;
  return async (effect, dispatch, signal) => {
    pending?.abort(); const controller = new AbortController(); pending = controller;
    const abort = () => controller.abort(); signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) controller.abort();
    try {
      const params = { params: { path: { project_id: effect.projectId } }, signal: controller.signal };
      const [graph, list] = await Promise.all([
        toResult(client.GET('/api/projects/{project_id}/graph', params)),
        toResult(client.GET('/api/projects/{project_id}/conversations', params)),
      ]);
      if (controller.signal.aborted) return;
      if (!graph.ok || !list.ok) {
        const failure = !graph.ok ? graph.error : !list.ok ? list.error : null;
        dispatch({ type: 'failed', request: effect.request, error: failure ? errorMessage(failure) ?? SYSTEM_ERROR_MESSAGE : SYSTEM_ERROR_MESSAGE }); return;
      }
      try {
        const parsed = parseProjectGraph(graph.data), conversations = parseConversationList(list.data).items;
        if (conversations.some(item => item.project_id !== effect.projectId)) throw new Error('Wrong project');
        dispatch({ type: 'loaded', request: effect.request, graph: parsed, conversations });
      } catch { dispatch({ type: 'failed', request: effect.request, error: SYSTEM_ERROR_MESSAGE }); }
    } finally { signal.removeEventListener('abort', abort); if (pending === controller) pending = null; }
  };
}
