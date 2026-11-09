import type { components } from '../../api/schema';

/** Shared result API boundary used by result reading and conversation sharing. */

type Schemas = components['schemas'];
export type Result = Schemas['Result'];
export type ResultRevision = Schemas['ResultRevision'];
type Parser<T> = (value: unknown) => T;
type Shape<T> = { [K in keyof T]-?: Parser<T[K]> };
const invalid = (): never => { throw new Error('Invalid result API response'); };
const string: Parser<string> = value => typeof value === 'string' ? value : invalid();
const integer: Parser<number> = value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : invalid();
const nullable = <T>(parse: Parser<T>): Parser<T | null> => value => value === null ? null : parse(value);
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
export const parseResult = object<Result>({
  id: string, project_id: string, title: string, source_conversation_id: string, source_task_id: string,
  latest_version: nullable(integer), latest_revision_id: nullable(string),
  revisions: array(object<Schemas['ResultRevisionEntry']>({ id: string, version: integer, saved_by: string, created_at: string })),
  draft: nullable(object<Schemas['ResultDraft']>({ status: oneOf('generating', 'ready', 'failed'), conclusion: nullable(string), base_version: integer,
    run_id: string, error: nullable(object<Schemas['ErrorSummary']>({ code: string, message: string })), updated_at: string })),
});
export const parseResultRevision = object<ResultRevision>({
  id: string, result_id: string, version: integer, title: string, conclusion: string, saved_by: string, created_at: string,
  source: object<Schemas['ResultRevisionSource']>({ conversation_id: string, message_from_seq: integer, message_to_seq: integer,
    resource_revision_ids: array(string), input_result_revision_ids: array(string), run_id: string }),
});
