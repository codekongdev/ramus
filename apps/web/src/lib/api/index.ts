export {
  IDEMPOTENCY_HEADER,
  createApiClient,
  idempotencyMiddleware,
  newIdempotencyKey,
  toResult,
} from './client';
export type { ApiClientOptions } from './client';
export {
  NETWORK_ERROR_MESSAGE,
  SYSTEM_ERROR_MESSAGE,
  errorMessage,
  hasErrorCode,
  isConflict,
  isNotFound,
  isUnauthorized,
  readErrorBody,
  toHttpError,
  toThrownError,
} from './result';
export type { ApiError, ApiResult, KnownErrorCode } from './result';
