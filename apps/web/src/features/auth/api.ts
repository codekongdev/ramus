import type { components } from '../../api/schema';
import { toResult, type ApiResult, type AppApi } from '../../lib/api';
import type { EffectHandler } from '../../lib/mvi';
import type { Account, AuthEffect, AuthIntent, Me } from './model';

type Project = components['schemas']['Project'];
const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
export const isAccount = (value: unknown): value is Account => record(value) && typeof value.id === 'string' && typeof value.email === 'string' && typeof value.display_name === 'string';
const isMe = (value: unknown): value is Me => record(value) && isAccount(value.account) && typeof value.default_project_id === 'string' && record(value.ai_connection) && ['none', 'connected', 'invalid'].includes(String(value.ai_connection.status));
export const isProject = (value: unknown): value is Project => record(value) && typeof value.id === 'string' && typeof value.name === 'string' && typeof value.is_shared_sample === 'boolean';
export const isParticipants = (value: unknown): value is components['schemas']['ProjectParticipants'] => record(value) && Array.isArray(value.items) && value.items.every(isAccount);
export const isProjects = (value: unknown): value is components['schemas']['ProjectList'] => record(value) && Array.isArray(value.items) && value.items.every(isProject);
export function validated<T>(result: ApiResult<T>, check: (value: unknown) => value is T): ApiResult<T> {
  if (!result.ok || check(result.data)) return result;
  return { ok: false, error: { kind: 'system', status: 502, code: null, message: null, details: null } };
}
export function makeAuthEffects(client: AppApi): EffectHandler<AuthEffect, AuthIntent> {
  return async (effect, dispatch, signal) => {
    if (effect.type === 'loadSession') {
      const result = validated(await toResult(client.GET('/api/me', { signal })), isMe);
      dispatch(result.ok ? { type: 'sessionLoaded', me: result.data } : { type: 'sessionFailed', error: result.error });
      return;
    }
    const operation = effect.operation;
    const headers = { 'Idempotency-Key': operation.key };
    if (operation.kind === 'register') {
      const result = validated(await toResult(client.POST('/api/auth/register', { body: operation.body, headers, signal })), isMe);
      dispatch(result.ok ? { type: 'authenticated', key: operation.key, me: result.data } : { type: 'failed', key: operation.key, error: result.error });
    } else if (operation.kind === 'login') {
      const result = validated(await toResult(client.POST('/api/auth/login', { body: operation.body, headers, signal })), isMe);
      dispatch(result.ok ? { type: 'authenticated', key: operation.key, me: result.data } : { type: 'failed', key: operation.key, error: result.error });
    } else {
      const result = validated(await toResult(client.POST('/api/auth/logout', { body: {}, headers, signal })), (value): value is components['schemas']['EmptyResponse'] => record(value) && Object.keys(value).length === 0);
      dispatch(result.ok ? { type: 'loggedOut', key: operation.key } : { type: 'failed', key: operation.key, error: result.error });
    }
  };
}
