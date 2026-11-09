export { api } from './app';
export type { AppApi } from './app';
export { apiMessages } from './messages';
export {
  IDEMPOTENCY_HEADER,
  acceptLanguageMiddleware,
  createApiClient,
  idempotencyMiddleware,
  jsonContentTypeMiddleware,
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
