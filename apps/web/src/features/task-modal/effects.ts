import type { components } from '../../api/schema';
import { errorMessage, toResult, SYSTEM_ERROR_MESSAGE, type AppApi } from '../../lib/api';
import { parseTask, parseMessageList, parseConversationDetail, parsePostMessageResponse, parseMe } from '../../lib/api/task-contract';
import type { EffectHandler } from '../../lib/mvi';
import { taskModalMessages as messages } from './messages';
import { mergeMessages, mentionsAi, type TaskModalEffect, type TaskModalIntent } from './model';

class TaskRequestError extends Error {}
async function read<T>(call: Promise<{ data?: T; error?: unknown; response: Response }>, parse: (value: unknown) => T): Promise<T> {
  const result = await toResult(call);
  if (!result.ok) throw new TaskRequestError(errorMessage(result.error) ?? SYSTEM_ERROR_MESSAGE);
  try { return parse(result.data); } catch { throw new TaskRequestError(SYSTEM_ERROR_MESSAGE); }
}
export function makeTaskModalEffectHandler(client: AppApi, ensureAiConnection?: () => Promise<boolean>): EffectHandler<TaskModalEffect, TaskModalIntent> {
  return async (effect, dispatch, signal) => {
    try {
      if (effect.type === 'load') {
        const [task, me] = await Promise.all([
          read(client.GET('/api/tasks/{task_id}', { params: { path: { task_id: effect.taskId } }, signal }), parseTask),
          read(client.GET('/api/me', { signal }), parseMe),
        ]);
        if (task.id !== effect.taskId) throw new TaskRequestError(SYSTEM_ERROR_MESSAGE);
        const conversationId = task.child_conversation_id;
        const loadConversation = () => read(client.GET('/api/conversations/{conversation_id}', { params: { path: { conversation_id: conversationId } }, signal }), parseConversationDetail);
        const loadMessages = async () => {
        const messages: components['schemas']['Message'][] = [];
        let afterSeq: number | undefined;
        const cursors = new Set<number>();
        do {
          const page = await read(client.GET('/api/conversations/{conversation_id}/messages', { params: { path: { conversation_id: conversationId }, query: { after_seq: afterSeq, limit: 200 } }, signal }), parseMessageList);
          if (page.items.some(message => message.conversation_id !== conversationId)) throw new TaskRequestError(SYSTEM_ERROR_MESSAGE);
          messages.push(...page.items);
          if (page.next_after_seq === null) break;
          if (cursors.has(page.next_after_seq) || (afterSeq !== undefined && page.next_after_seq <= afterSeq)) throw new TaskRequestError(SYSTEM_ERROR_MESSAGE);
          cursors.add(page.next_after_seq);
          afterSeq = page.next_after_seq;
        } while (!signal.aborted);
        return mergeMessages(messages);
        };
        const [conversation, messages] = await Promise.all([loadConversation(), loadMessages()]);
        if (conversation.id !== conversationId) throw new TaskRequestError(SYSTEM_ERROR_MESSAGE);
        dispatch({ type: 'loaded', taskId: effect.taskId, request: effect.request, task, me, conversation, messages: mergeMessages(messages) });
        return;
      }
      const { task, mutation } = effect;
      const headers = { 'Idempotency-Key': mutation.key };
      if (mutation.kind === 'send') {
        if (mentionsAi(mutation.body!)) {
          const connected = ensureAiConnection ? await ensureAiConnection() : (await read(client.GET('/api/me', { signal }), parseMe)).ai_connection.status === 'connected';
          if (!connected) throw new TaskRequestError(messages.aiConnection);
          if (signal.aborted) return;
        }
        const posted = await read(client.POST('/api/conversations/{conversation_id}/messages', { params: { path: { conversation_id: task.child_conversation_id } }, body: { body: mutation.body! }, headers, signal }), parsePostMessageResponse);
        if (posted.message.conversation_id !== task.child_conversation_id || (posted.run && posted.run.conversation_id !== task.child_conversation_id)) throw new TaskRequestError(SYSTEM_ERROR_MESSAGE);
        dispatch({ type: 'mutationSucceeded', taskId: task.id, key: mutation.key, message: posted.message, run: posted.run });
      } else {
        if (mutation.kind === 'retry') {
          const connected = ensureAiConnection ? await ensureAiConnection() : (await read(client.GET('/api/me', { signal }), parseMe)).ai_connection.status === 'connected';
          if (!connected) throw new TaskRequestError(messages.retryConnection);
          if (signal.aborted) return;
        }
        const result = mutation.kind === 'cancel'
          ? await read(client.POST('/api/tasks/{task_id}/cancel', { params: { path: { task_id: task.id } }, body: {}, headers, signal }), parseTask)
          : await read(client.POST('/api/tasks/{task_id}/retry', { params: { path: { task_id: task.id } }, body: {}, headers, signal }), parseTask);
        if (result.id !== task.id) throw new TaskRequestError(SYSTEM_ERROR_MESSAGE);
        dispatch({ type: 'mutationSucceeded', taskId: task.id, key: mutation.key, task: result });
      }
    } catch (error) {
      if (signal.aborted) return;
      const message = error instanceof TaskRequestError ? error.message : SYSTEM_ERROR_MESSAGE;
      if (effect.type === 'load') dispatch({ type: 'loadFailed', taskId: effect.taskId, request: effect.request, message });
      else dispatch({ type: 'mutationFailed', taskId: effect.task.id, key: effect.mutation.key, message });
    }
  };
}
