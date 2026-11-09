/**
 * API call outcome. Business errors (4xx) and system errors (5xx, network) are kept apart
 * (CONVENTIONS.md 오류 규칙) so reducers can show a recoverable message for the former.
 */

export type ApiError =
  | {
      readonly kind: 'business';
      readonly status: number;
      readonly code: string | null;
      readonly message: string | null;
      readonly body: unknown;
    }
  | {
      readonly kind: 'system';
      readonly status: number;
      readonly code: string | null;
      readonly message: string | null;
      readonly body: unknown;
    }
  | { readonly kind: 'network'; readonly cause: unknown }
  | { readonly kind: 'aborted' };

export type ApiResult<T> =
  | { readonly ok: true; readonly data: T; readonly status: number }
  | { readonly ok: false; readonly error: ApiError };

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const stringOrNull = (value: unknown): string | null => (typeof value === 'string' ? value : null);

/**
 * Pulls `code`/`message` out of an error body. The server's error format is fixed in P0-A1;
 * until then this accepts `{ error: { code, message } }`, `{ code, message }` and FastAPI's
 * default `{ detail: string }`. Anything else keeps only the raw body.
 */
export function readErrorBody(body: unknown): { code: string | null; message: string | null } {
  if (!isRecord(body)) return { code: null, message: null };
  const source = isRecord(body.error) ? body.error : body;
  return {
    code: stringOrNull(source.code),
    message: stringOrNull(source.message) ?? stringOrNull(body.detail),
  };
}

export function toHttpError(status: number, body: unknown): ApiError {
  const { code, message } = readErrorBody(body);
  return { kind: status >= 500 ? 'system' : 'business', status, code, message, body };
}

export function toThrownError(cause: unknown): ApiError {
  if (cause instanceof DOMException && cause.name === 'AbortError') return { kind: 'aborted' };
  return { kind: 'network', cause };
}

export const isConflict = (error: ApiError) => error.kind === 'business' && error.status === 409;
export const isUnauthorized = (error: ApiError) => error.kind === 'business' && error.status === 401;
export const isNotFound = (error: ApiError) => error.kind === 'business' && error.status === 404;
