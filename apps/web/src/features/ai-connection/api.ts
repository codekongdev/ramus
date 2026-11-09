import type { components } from '../../api/schema';
import { SYSTEM_ERROR_MESSAGE, toResult, type ApiResult, type AppApi } from '../../lib/api';

export type ConnectionStatus = components['schemas']['AiConnectionState']['status'];
export type ConnectionState = components['schemas']['AiConnectionState'];

export interface AiConnectionApi {
  read(signal: AbortSignal): Promise<ApiResult<ConnectionState>>;
  connect(apiKey: string, requestId: string, signal: AbortSignal): Promise<ApiResult<ConnectionState>>;
  disconnect(requestId: string, signal: AbortSignal): Promise<ApiResult<ConnectionState>>;
}

/** Validate even successful responses at the HTTP boundary; never keep unknown response fields. */
function validate(result: ApiResult<unknown>, expected?: ConnectionStatus): ApiResult<ConnectionState> {
  if (!result.ok) return result;
  const value = result.data;
  if (typeof value === 'object' && value !== null && 'status' in value &&
    (value.status === 'none' || value.status === 'connected' || value.status === 'invalid') &&
    (expected === undefined || value.status === expected)) {
    return { ...result, data: { status: value.status } };
  }
  return { ok: false, error: { kind: 'system', status: 502, code: null, message: SYSTEM_ERROR_MESSAGE, details: null } };
}

export function createAiConnectionApi(client: AppApi): AiConnectionApi {
  return {
    async read(signal) {
      return validate(await toResult(client.GET('/api/me/ai-connection', { signal })));
    },
    async connect(apiKey, requestId, signal) {
      return validate(await toResult(client.PUT('/api/me/ai-connection', {
        body: { api_key: apiKey }, headers: { 'Idempotency-Key': requestId }, signal,
      })), 'connected');
    },
    async disconnect(requestId, signal) {
      return validate(await toResult(client.DELETE('/api/me/ai-connection', {
        headers: { 'Idempotency-Key': requestId }, signal,
      })), 'none');
    },
  };
}
