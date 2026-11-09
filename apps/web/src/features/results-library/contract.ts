import type { components } from '../../api/schema';

type Schemas = components['schemas'];
export type ProjectResultSummary = Schemas['ProjectResultSummary'];
type Parser<T> = (value: unknown) => T;
type Shape<T> = { [K in keyof T]-?: Parser<T[K]> };
const invalid = (): never => { throw new Error('Invalid project results response'); };
const text: Parser<string> = value => typeof value === 'string' && value.trim() !== '' ? value : invalid();
const version: Parser<number> = value =>
  typeof value === 'number' && Number.isSafeInteger(value) && value > 0 ? value : invalid();
const timestamp: Parser<string> = value => {
  const parsed = text(value);
  return /^\d{4}-\d{2}-\d{2}T/.test(parsed) && Number.isFinite(Date.parse(parsed)) ? parsed : invalid();
};
function object<T>(shape: Shape<T>): Parser<T> {
  return value => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid();
    const source = value as Record<string, unknown>;
    const result = {} as T;
    for (const key of Object.keys(shape) as (keyof T)[]) result[key] = shape[key](source[key as string]);
    return result;
  };
}
const summary = object<ProjectResultSummary>({
  result_id: text, title: text, latest_version: version, latest_revision_id: text,
  source_conversation_title: text, updated_at: timestamp,
});
export const parseProjectResults = object<Schemas['ProjectResultList']>({
  items: value => {
    if (!Array.isArray(value)) return invalid();
    const items = value.map(summary);
    if (new Set(items.map(item => item.result_id)).size !== items.length) return invalid();
    return items;
  },
});
