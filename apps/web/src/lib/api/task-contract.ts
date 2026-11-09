import type { components } from '../../api/schema';

// Runtime boundary schemas are checked against the generated OpenAPI types.
type Schemas = components['schemas'];
export type Task = Schemas['Task'];
export type Message = Schemas['Message'];
type Parser<T> = (value: unknown) => T;
type Shape<T> = { [K in keyof T]-?: Parser<T[K]> };

export class TaskDecodeError extends Error {
  constructor() {
    super('Invalid task API response');
    this.name = 'TaskDecodeError';
  }
}
const invalid = (): never => { throw new TaskDecodeError(); };
const string: Parser<string> = (value) => typeof value === 'string' ? value : invalid();
const boolean: Parser<boolean> = (value) => typeof value === 'boolean' ? value : invalid();
const integer: Parser<number> = (value) =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : invalid();
const nullable = <T>(parse: Parser<T>): Parser<T | null> => (value) => value === null ? null : parse(value);
const array = <T>(parse: Parser<T>): Parser<T[]> => (value) => Array.isArray(value) ? value.map(parse) : invalid();
const oneOf = <T extends string>(...values: T[]): Parser<T> => (value) =>
  typeof value === 'string' && values.includes(value as T) ? value as T : invalid();
function object<T>(shape: Shape<T>): Parser<T> {
  return (value) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid();
    const source = value as Record<string, unknown>;
    const result = {} as T;
    for (const key of Object.keys(shape) as (keyof T)[]) result[key] = shape[key](source[key as string]);
    return result;
  };
}
const error = object<Schemas['ErrorSummary']>({ code: string, message: string });
export const parseTask: Parser<Task> = object<Task>({
  id: string, title: string, goal: string, source_conversation_id: string,
  child_conversation_id: string, requested_by: string,
  status: oneOf('pending', 'running', 'ready', 'failed', 'cancelled'),
  result_id: nullable(string), error: nullable(error), created_at: string,
  started_at: nullable(string), finished_at: nullable(string),
});
const taskList = object<Schemas['TaskList']>({ items: array(parseTask) });
export const parseTaskList = (value: unknown): Task[] => taskList(value).items;
export const parseRun: Parser<Schemas['Run']> = object<Schemas['Run']>({
  id: string, conversation_id: string, task_id: nullable(string),
  purpose: oneOf('work', 'summary'), status: oneOf('pending', 'running', 'succeeded', 'failed', 'cancelled'),
  requested_by: string, error: nullable(error), created_at: string,
  started_at: nullable(string), finished_at: nullable(string),
});
export const parseMessage: Parser<Message> = object<Message>({
  id: string, conversation_id: string, seq: integer,
  author: object<Schemas['MessageAuthor']>({
    kind: oneOf('human', 'ai', 'system'), account_id: nullable(string), display_name: string,
  }),
  body: string, requested_by: nullable(string), run_id: nullable(string), is_example: boolean, created_at: string,
});
export const parseMessageList: Parser<Schemas['MessageList']> = object<Schemas['MessageList']>({
  items: array(parseMessage), next_after_seq: nullable(integer),
});
const conversationShape: Shape<Schemas['Conversation']> = {
  id: string, project_id: string, parent_id: nullable(string), task_id: nullable(string),
  title: string, path: array(string), created_by: string, created_at: string,
};
export const parseConversation = object<Schemas['Conversation']>(conversationShape);
export const parseConversationList = object<Schemas['ConversationList']>({ items: array(parseConversation) });
export const parseConversationDetail: Parser<Schemas['ConversationDetail']> = object<Schemas['ConversationDetail']>({
  ...conversationShape, active_run: nullable(parseRun),
});
export const parsePostMessageResponse: Parser<Schemas['PostMessageResponse']> = object<Schemas['PostMessageResponse']>({
  message: parseMessage, run: nullable(parseRun),
});
export const parseMe: Parser<Schemas['Me']> = object<Schemas['Me']>({
  account: object<Schemas['Account']>({ id: string, email: string, display_name: string }),
  ai_connection: object<Schemas['AiConnectionState']>({ status: oneOf('none', 'connected', 'invalid') }),
  default_project_id: string,
});
