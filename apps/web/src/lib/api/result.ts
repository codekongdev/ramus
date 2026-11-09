/**
 * API call outcome. Business errors (4xx) and system errors (5xx, network) are kept apart
 * (CONVENTIONS.md 오류 규칙). Per contracts.md 7장, business errors show the server's
 * `message` and branch on `code`; system and network errors use a common message.
 */

/** Feature error codes from contracts.md 1.2, plus the P0-A1 defaults used for branching. */
export type KnownErrorCode =
  | 'BAD_REQUEST'
  | 'UNAUTHORIZED'
  | 'FORBIDDEN'
  | 'NOT_FOUND'
  | 'CONFLICT'
  | 'INTERNAL_ERROR'
  | 'INVALID_INPUT'
  | 'IDEMPOTENCY_KEY_INVALID'
  | 'IDEMPOTENCY_CONFLICT'
  | 'AUTH_CODE_INVALID'
  | 'AUTH_CODE_EXPIRED'
  | 'AUTH_RATE_LIMITED'
  | 'AI_CONNECTION_REQUIRED'
  | 'AI_KEY_INVALID'
  | 'ACTIVE_RUN_EXISTS'
  | 'RUN_NOT_CANCELLABLE'
  | 'RUN_NOT_RETRYABLE'
  | 'TASK_NOT_READY'
  | 'VERSION_CONFLICT'
  | 'FILE_TYPE_UNSUPPORTED'
  | 'SHARE_TARGET_INVALID'
  | 'PROJECT_CREATE_FORBIDDEN';

/** `code`/`message` are null only when the body is not the contract envelope (e.g. a proxy page). */
interface HttpErrorFields {
  readonly status: number;
  readonly code: string | null;
  readonly message: string | null;
  readonly details: unknown;
}

export type ApiError =
  | ({ readonly kind: 'business' } & HttpErrorFields)
  | ({ readonly kind: 'system' } & HttpErrorFields)
  | { readonly kind: 'network'; readonly cause: unknown }
  | { readonly kind: 'aborted' };

export type ApiResult<T> =
  | { readonly ok: true; readonly data: T; readonly status: number }
  | { readonly ok: false; readonly error: ApiError };

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

/**
 * Validates the error envelope `{ error: { code, message, details } }` (contracts.md 0장).
 * Anything else yields nulls so the caller falls back to the common message.
 */
export function readErrorBody(body: unknown): {
  code: string | null;
  message: string | null;
  details: unknown;
} {
  const error = isRecord(body) && isRecord(body.error) ? body.error : null;
  if (!error || typeof error.code !== 'string' || typeof error.message !== 'string') {
    return { code: null, message: null, details: null };
  }
  return { code: error.code, message: error.message, details: error.details ?? null };
}

export function toHttpError(status: number, body: unknown): ApiError {
  return { kind: status >= 500 ? 'system' : 'business', status, ...readErrorBody(body) };
}

export function toThrownError(cause: unknown): ApiError {
  if (cause instanceof DOMException && cause.name === 'AbortError') return { kind: 'aborted' };
  return { kind: 'network', cause };
}

export const hasErrorCode = (error: ApiError, code: KnownErrorCode): boolean =>
  (error.kind === 'business' || error.kind === 'system') && error.code === code;

export const isConflict = (error: ApiError) => error.kind === 'business' && error.status === 409;
export const isUnauthorized = (error: ApiError) => error.kind === 'business' && error.status === 401;
export const isNotFound = (error: ApiError) => error.kind === 'business' && error.status === 404;

export const SYSTEM_ERROR_MESSAGE = '요청을 처리하는 중에 문제가 생겼습니다. 잠시 후 다시 시도해 주세요.';
export const NETWORK_ERROR_MESSAGE = '서버에 연결할 수 없습니다. 네트워크 연결을 확인해 주세요.';

/**
 * Text to show the user. Returns null for `aborted`, which is not a failure the user caused
 * or needs to see.
 */
export function errorMessage(error: ApiError): string | null {
  switch (error.kind) {
    case 'business':
      return error.message ?? SYSTEM_ERROR_MESSAGE;
    case 'system':
      return SYSTEM_ERROR_MESSAGE;
    case 'network':
      return NETWORK_ERROR_MESSAGE;
    case 'aborted':
      return null;
  }
}
