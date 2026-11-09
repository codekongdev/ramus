import { errorMessage, hasErrorCode, SYSTEM_ERROR_MESSAGE, toResult, type AppApi } from '../../lib/api';
import { parseMe } from '../../lib/api/task-contract';
import type { EffectHandler } from '../../lib/mvi';
import { parseResult, parseResultRevision, type Result, type ResultRevision } from './contract';
import { resultMessages as messages } from './messages';
import type { ResultEffect, ResultIntent } from './model';

class ResultRequestError extends Error {
  constructor(message: string, readonly conflict = false) { super(message); }
}
async function read<T>(call: Promise<{ data?: T; error?: unknown; response: Response }>, parse: (value: unknown) => T): Promise<T> {
  const result = await toResult(call);
  if (!result.ok) throw new ResultRequestError(errorMessage(result.error) ?? SYSTEM_ERROR_MESSAGE, hasErrorCode(result.error, 'VERSION_CONFLICT'));
  try { return parse(result.data); } catch { throw new ResultRequestError(SYSTEM_ERROR_MESSAGE); }
}
function checkResult(result: Result, taskId: string, resultId?: string | null) {
  if (result.source_task_id !== taskId || (resultId && result.id !== resultId)) throw new ResultRequestError(SYSTEM_ERROR_MESSAGE);
}
function checkRevision(revision: ResultRevision, resultId: string, revisionId?: string) {
  if (revision.result_id !== resultId || (revisionId && revision.id !== revisionId)) throw new ResultRequestError(SYSTEM_ERROR_MESSAGE);
}
export function makeResultEffectHandler(client: AppApi, ensureAiConnection?: () => Promise<boolean>): EffectHandler<ResultEffect, ResultIntent> {
  return async (effect, dispatch, signal) => {
    try {
      const revision = async (resultId: string, revisionId: string) => {
        const value = await read(client.GET('/api/result-revisions/{result_revision_id}', { params: { path: { result_revision_id: revisionId } }, signal }), parseResultRevision);
        checkRevision(value, resultId, revisionId);
        return value;
      };
      if (effect.type === 'load') {
        const result = await read(client.GET('/api/results/{result_id}', { params: { path: { result_id: effect.resultId } }, signal }), parseResult);
        checkResult(result, effect.taskId, effect.resultId);
        const approved = result.latest_revision_id ? await revision(result.id, result.latest_revision_id) : null;
        if (approved && approved.version !== result.latest_version) throw new ResultRequestError(SYSTEM_ERROR_MESSAGE);
        if (!signal.aborted) dispatch({ type: 'loaded', taskId: effect.taskId, request: effect.request, result, approved });
      } else if (effect.type === 'revision') {
        const value = await revision(effect.resultId, effect.revisionId);
        if (!signal.aborted) dispatch({ type: 'revisionLoaded', taskId: effect.taskId, request: effect.request, revision: value });
      } else {
        const mutation = effect.mutation;
        const headers = { 'Idempotency-Key': mutation.key };
        if (mutation.kind === 'summary') {
          const connected = ensureAiConnection ? await ensureAiConnection()
            : (await read(client.GET('/api/me', { signal }), parseMe)).ai_connection.status === 'connected';
          if (signal.aborted) return;
          if (!connected) {
            if (!ensureAiConnection) throw new ResultRequestError(messages.connection);
            dispatch({ type: 'mutationCancelled', taskId: effect.taskId, key: mutation.key }); return;
          }
          const result = await read(client.POST('/api/tasks/{task_id}/summaries', { params: { path: { task_id: effect.taskId } }, body: {}, headers, signal }), parseResult);
          checkResult(result, effect.taskId, effect.resultId);
          if (!signal.aborted) dispatch({ type: 'summarySucceeded', taskId: effect.taskId, key: mutation.key, result });
        } else {
          if (!effect.resultId) throw new ResultRequestError(SYSTEM_ERROR_MESSAGE);
          const saved = await read(client.POST('/api/results/{result_id}/revisions', { params: { path: { result_id: effect.resultId } },
            body: { base_version: mutation.baseVersion, source_run_id: mutation.sourceRunId, conclusion: mutation.conclusion }, headers, signal }), parseResultRevision);
          checkRevision(saved, effect.resultId);
          if (saved.version !== mutation.baseVersion + 1) throw new ResultRequestError(SYSTEM_ERROR_MESSAGE);
          if (!signal.aborted) dispatch({ type: 'saved', taskId: effect.taskId, key: mutation.key, revision: saved });
        }
      }
    } catch (error) {
      if (signal.aborted) return;
      const message = error instanceof ResultRequestError ? error.message : SYSTEM_ERROR_MESSAGE;
      if (effect.type === 'load') dispatch({ type: 'loadFailed', taskId: effect.taskId, request: effect.request, message });
      else if (effect.type === 'revision') dispatch({ type: 'revisionFailed', taskId: effect.taskId, request: effect.request, message });
      else dispatch({ type: 'mutationFailed', taskId: effect.taskId, key: effect.mutation.key, message, conflict: error instanceof ResultRequestError && error.conflict });
    }
  };
}
