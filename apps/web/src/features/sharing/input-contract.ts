import type { components } from '../../api/schema';

type Schemas = components['schemas'];
export type Input = Schemas['ConversationInput'];
export type InputDetail = Schemas['ConversationInputDetail'];
type Parser<T> = (value: unknown) => T;
type Shape<T> = { [K in keyof T]-?: Parser<T[K]> };
const invalid = (): never => { throw new Error('Invalid conversation input response'); };
const string: Parser<string> = value => typeof value === 'string' ? value : invalid();
const integer: Parser<number> = value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : invalid();
const version: Parser<number> = value => Number.isSafeInteger(value) && Number(value) > 0 ? Number(value) : invalid();
const strings: Parser<string[]> = value => Array.isArray(value) ? value.map(string) : invalid();
function object<T>(shape: Shape<T>): Parser<T> {
  return value => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid();
    const source = value as Record<string, unknown>;
    const result = {} as T;
    for (const key of Object.keys(shape) as (keyof T)[]) result[key] = shape[key](source[key as string]);
    return result;
  };
}
const inputShape: Shape<Input> = {
  id: string, conversation_id: string, result_id: string, result_revision_id: string,
  version, latest_version: version, title: string, created_by: string, created_at: string,
  origin: value => value === 'share' || value === 'new_conversation' ? value : invalid(),
};
const input = object<Input>(inputShape);
function check<T extends Input>(value: T, conversationId: string): T {
  return value.conversation_id === conversationId && value.latest_version >= value.version ? value : invalid();
}
const list = object<Schemas['ConversationInputList']>({ items: value => Array.isArray(value) ? value.map(input) : invalid() });
export const parseInputs = (value: unknown, conversationId: string): Input[] => list(value).items.map(item => check(item, conversationId));
const detail = object<InputDetail>({
  ...inputShape, conclusion: string,
  source: object<Schemas['ResultRevisionSource']>({ conversation_id: string, message_from_seq: integer, message_to_seq: integer,
    resource_revision_ids: strings, input_result_revision_ids: strings, run_id: string }),
});
export function parseInputDetail(value: unknown, conversationId: string, inputId: string): InputDetail {
  const result = check(detail(value), conversationId);
  return result.id === inputId ? result : invalid();
}
