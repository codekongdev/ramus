import { errorMessage, SYSTEM_ERROR_MESSAGE, toResult, type AppApi } from '../../lib/api';
import { parseTaskList } from '../../lib/api/task-contract';
import type { EffectHandler } from '../../lib/mvi';
import type { TaskQueueEffect, TaskQueueIntent } from './model';

export function makeTaskQueueEffectHandler(client: AppApi): EffectHandler<TaskQueueEffect, TaskQueueIntent> {
  return async (effect, dispatch, signal) => {
    const result = await toResult(client.GET('/api/conversations/{conversation_id}/tasks', {
      params: { path: { conversation_id: effect.conversationId } }, signal,
    }));
    if (!result.ok) {
      const message = errorMessage(result.error);
      if (message) dispatch({ ...effect, type: 'failed', message });
      return;
    }
    try {
      const items = parseTaskList(result.data);
      dispatch({ ...effect, type: 'loaded', items });
    } catch {
      dispatch({ ...effect, type: 'failed', message: SYSTEM_ERROR_MESSAGE });
    }
  };
}
