import type { components } from '../../api/schema';
import { toResult, type AppApi } from '../../lib/api';
import type { EffectHandler } from '../../lib/mvi';
import { validated } from './api';
import type { PasswordSetupEffect, PasswordSetupIntent } from './passwordSetupModel';

type PasswordState = components['schemas']['PasswordState'];
type PasswordConfigured = components['schemas']['PasswordConfigured'];
const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const isPasswordState = (value: unknown): value is PasswordState => record(value) && typeof value.configured === 'boolean';
const isConfigured = (value: unknown): value is PasswordConfigured => isPasswordState(value) && value.configured === true;

export function makePasswordSetupEffects(client: AppApi, expireSession: () => void): EffectHandler<PasswordSetupEffect, PasswordSetupIntent> {
  const pending = new Map<number, AbortController>();
  return async (effect, dispatch, signal) => {
    if (effect.type === 'expireSession') {
      expireSession();
      return;
    }
    if (effect.type === 'cancelSave') {
      pending.get(effect.request)?.abort();
      return;
    }
    if (effect.type === 'load') {
      const result = validated(await toResult(client.GET('/api/me/password', { signal })), isPasswordState);
      dispatch(result.ok ? { type: 'loaded', request: effect.request, configured: result.data.configured }
        : { type: 'loadFailed', request: effect.request, error: result.error });
      return;
    }
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal.aborted) return;
    signal.addEventListener('abort', abort, { once: true });
    pending.set(effect.request, controller);
    try {
      const result = validated(await toResult(client.PUT('/api/me/password', {
        body: { password: effect.password }, headers: { 'Idempotency-Key': effect.key }, signal: controller.signal,
      })), isConfigured);
      if (!controller.signal.aborted) dispatch(result.ok ? { type: 'saved', request: effect.request }
        : { type: 'saveFailed', request: effect.request, error: result.error });
    } finally {
      signal.removeEventListener('abort', abort);
      pending.delete(effect.request);
    }
  };
}
