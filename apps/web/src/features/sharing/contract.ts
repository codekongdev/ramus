import type { components } from '../../api/schema';

export type Conversation = components['schemas']['Conversation'];
export type ConversationInput = components['schemas']['ConversationInput'];
export type ShareOutcomes = components['schemas']['ShareOutcomeList'];
type Parser<T> = (value: unknown) => T;
type Shape<T> = { [K in keyof T]-?: Parser<T[K]> };
const invalid = (): never => { throw new Error('Invalid sharing API response'); };
const string: Parser<string> = value => typeof value === 'string' ? value : invalid();
const integer: Parser<number> = value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 1 ? value : invalid();
const array = <T>(parse: Parser<T>): Parser<T[]> => value => Array.isArray(value) ? value.map(parse) : invalid();
const oneOf = <T extends string>(...values: T[]): Parser<T> => value => typeof value === 'string' && values.includes(value as T) ? value as T : invalid();
function object<T>(shape: Shape<T>): Parser<T> {
  return value => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid();
    const source = value as Record<string, unknown>;
    const result = {} as T;
    for (const key of Object.keys(shape) as (keyof T)[]) result[key] = shape[key](source[key as string]);
    return result;
  };
}
export const parseInputs = object<components['schemas']['ConversationInputList']>({ items: array(object<ConversationInput>({
  id: string, conversation_id: string, result_id: string, result_revision_id: string, version: integer,
  title: string, latest_version: integer, origin: oneOf('share', 'new_conversation'), created_by: string, created_at: string,
})) });
export const parseOutcomes = object<ShareOutcomes>({ items: array(object<components['schemas']['ShareTargetOutcome']>({
  conversation_id: string, outcome: oneOf('linked', 'replaced', 'unchanged', 'kept_newer'),
})) });
