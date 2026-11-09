import { errorMessage, SYSTEM_ERROR_MESSAGE, toResult, type AppApi } from '../../lib/api';
import { parseConversationDetail, parseMe, parseMessageList, parsePostMessageResponse } from '../../lib/api/task-contract';
import type { EffectHandler } from '../../lib/mvi';
import { conversationMessages as messages } from './messages';
import { mergeMessages, mentionsAi, type Effect, type Intent, type Message } from './model';

class ConversationRequestError extends Error {}
async function read<T>(call: Promise<{ data?: T; error?: unknown; response: Response }>, parse: (value: unknown) => T): Promise<T> {
  const result = await toResult(call);
  if (!result.ok) throw new ConversationRequestError(errorMessage(result.error) ?? SYSTEM_ERROR_MESSAGE);
  try { return parse(result.data); } catch { throw new ConversationRequestError(SYSTEM_ERROR_MESSAGE); }
}
const invalid = (): never => { throw new ConversationRequestError(SYSTEM_ERROR_MESSAGE); };
const validDate = (value: string): boolean => !Number.isNaN(Date.parse(value));
function checkMessage(message: Message, conversationId: string): void {
  if (message.conversation_id !== conversationId || message.seq < 1 || !validDate(message.created_at)) invalid();
}

export function makeConversationEffectHandler(client: AppApi, ensureAiConnection?: () => Promise<boolean>): EffectHandler<Effect, Intent> {
  return async (effect, dispatch, signal) => {
    if (signal.aborted) return;
    try {
      const conversationId = effect.conversationId;
      if (effect.type === 'load') {
        const loadMessages = async () => {
          const items: Message[] = [];
          let afterSeq = 0;
          while (!signal.aborted) {
            const page = await read(client.GET('/api/conversations/{conversation_id}/messages', {
              params: { path: { conversation_id: conversationId }, query: { after_seq: afterSeq, limit: 200 } }, signal,
            }), parseMessageList);
            for (const item of page.items) checkMessage(item, conversationId);
            items.push(...page.items);
            if (page.next_after_seq === null) break;
            if (page.next_after_seq <= afterSeq || !page.items.some(item => item.seq === page.next_after_seq)) invalid();
            afterSeq = page.next_after_seq;
          }
          return mergeMessages(items);
        };
        const [conversation, items] = await Promise.all([
          read(client.GET('/api/conversations/{conversation_id}', { params: { path: { conversation_id: conversationId } }, signal }), parseConversationDetail),
          loadMessages(),
        ]);
        if (conversation.id !== conversationId || conversation.project_id !== effect.projectId || !validDate(conversation.created_at)
          || (conversation.active_run && conversation.active_run.conversation_id !== conversationId)) invalid();
        if (!signal.aborted) dispatch({ type: 'loaded', conversationId, request: effect.request, conversation, messages: items });
        return;
      }
      const { mutation } = effect;
      if (mentionsAi(mutation.body)) {
        const connected = ensureAiConnection
          ? await ensureAiConnection()
          : (await read(client.GET('/api/me', { signal }), parseMe)).ai_connection.status === 'connected';
        if (!connected) throw new ConversationRequestError(messages.aiConnection);
        if (signal.aborted) return;
      }
      const posted = await read(client.POST('/api/conversations/{conversation_id}/messages', {
        params: { path: { conversation_id: conversationId } }, body: { body: mutation.body },
        headers: { 'Idempotency-Key': mutation.key }, signal,
      }), parsePostMessageResponse);
      checkMessage(posted.message, conversationId);
      if (posted.run && posted.run.conversation_id !== conversationId) invalid();
      if (!signal.aborted) dispatch({ type: 'mutationSucceeded', conversationId, key: mutation.key, message: posted.message, run: posted.run });
    } catch (error) {
      if (signal.aborted) return;
      const message = error instanceof ConversationRequestError ? error.message : SYSTEM_ERROR_MESSAGE;
      if (effect.type === 'load') dispatch({ type: 'loadFailed', conversationId: effect.conversationId, request: effect.request, message });
      else dispatch({ type: 'mutationFailed', conversationId: effect.conversationId, key: effect.mutation.key, message });
    }
  };
}
