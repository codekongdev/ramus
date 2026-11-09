import type { components } from '../../api/schema';

// Mapped shapes keep runtime validation aligned with the generated OpenAPI contract.
type Schemas = components['schemas'];
type Parser<T> = (value: unknown) => T;
type Shape<T> = { [K in keyof T]-?: Parser<T[K]> };

export class ResourceDecodeError extends Error {
  constructor() {
    super('Invalid resource API response');
    this.name = 'ResourceDecodeError';
  }
}

const invalid = (): never => { throw new ResourceDecodeError(); };
const string: Parser<string> = value => typeof value === 'string' ? value : invalid();
const version: Parser<number> = value =>
  typeof value === 'number' && Number.isSafeInteger(value) && value > 0 ? value : invalid();
const nullable = <T>(parse: Parser<T>): Parser<T | null> => value => value === null ? null : parse(value);
const array = <T>(parse: Parser<T>): Parser<T[]> => value => Array.isArray(value) ? value.map(parse) : invalid();
const oneOf = <T extends string>(...values: T[]): Parser<T> => value =>
  typeof value === 'string' && values.includes(value as T) ? value as T : invalid();

function object<T>(shape: Shape<T>): Parser<T> {
  return value => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid();
    const source = value as Record<string, unknown>;
    const result = {} as T;
    for (const key of Object.keys(shape) as (keyof T)[]) result[key] = shape[key](source[key as string]);
    return result;
  };
}

const kind = oneOf('skill', 'text', 'file');
const appliedRevision = object<Schemas['AppliedRevisionRef']>({ revision_id: string, number: version });
const latest = object<Schemas['ResourceLatest']>({
  revision_id: string, number: version, name: string, description: string,
});
const summary = object<Schemas['ResourceSummary']>({
  id: string, kind, latest, applied: nullable(appliedRevision),
});
const applied = object<Schemas['AppliedResource']>({
  resource_id: string, revision_id: string, number: version, name: string, kind,
});
const revision = object<Schemas['ResourceRevision']>({
  id: string, resource_id: string, number: version, name: string, description: string,
  instructions: nullable(string), content: nullable(string), file_name: nullable(string),
  created_by: string, created_at: string,
});
const revisionEntry = object<Schemas['ResourceRevisionEntry']>({
  id: string, number: version, name: string, created_by: string, created_at: string,
});

export const parseResourceSummaryList = object<Schemas['ResourceSummaryList']>({ items: array(summary) });
export const parseAppliedResourceList = object<Schemas['AppliedResourceList']>({ items: array(applied) });
export const parseResourceDetail = object<Schemas['ResourceDetail']>({
  id: string, kind, latest_revision_id: string, revision, revisions: array(revisionEntry),
});
