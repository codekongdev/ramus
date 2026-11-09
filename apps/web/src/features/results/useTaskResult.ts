import { useCallback, useMemo } from 'react';
import { api, newIdempotencyKey, type AppApi } from '../../lib/api';
import type { Task } from '../../lib/api/task-contract';
import { useStore } from '../../lib/mvi';
import { useProjectEventListener, useResyncListener } from '../../lib/realtime';
import { makeResultEffectHandler } from './effects';
import { initialResultState, resultReducer } from './model';

/** The app owns this controller so header actions and the result tab share one state. */
export function useTaskResult(taskId: string, ensureAiConnection?: () => Promise<boolean>, client: AppApi = api) {
  const handle = useMemo(() => makeResultEffectHandler(client, ensureAiConnection), [client, ensureAiConnection]);
  const [state, dispatch] = useStore(resultReducer, () => initialResultState(taskId), handle);
  useProjectEventListener(event => dispatch({ type: 'serverEvent', event }));
  useResyncListener(() => dispatch({ type: 'refresh' }));
  const taskChanged = useCallback((task: Task) => dispatch({ type: 'taskChanged', task }), [dispatch]);
  const summarize = useCallback(() => dispatch({ type: 'summarize', key: newIdempotencyKey() }), [dispatch]);
  const save = useCallback(() => dispatch({ type: 'save', key: newIdempotencyKey() }), [dispatch]);
  return { state, dispatch, taskChanged, summarize, save };
}
export type TaskResultController = ReturnType<typeof useTaskResult>;
