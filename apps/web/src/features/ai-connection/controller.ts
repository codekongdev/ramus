import { errorMessage, newIdempotencyKey, type ApiResult } from '../../lib/api';
import { createStore, type EffectHandler } from '../../lib/mvi';
import type { AiConnectionApi, ConnectionState } from './api';
import { aiConnectionMessages as messages } from './messages';
import { aiConnectionReducer, initialAiConnectionState, type AiConnectionEffect, type AiConnectionIntent } from './model';

/** Promise continuations and cancellation are effects; no request drafts or keys live in shared state. */
export function createAiConnectionController(api: AiConnectionApi) {
  let pending: { promise: Promise<boolean>; resolve: (connected: boolean) => void } | null = null;
  let active = false;
  let dialogs = 0;
  let operation: AbortController | null = null;
  const finish = (connected: boolean) => {
    const previous = pending;
    pending = null;
    previous?.resolve(connected);
  };
  const handleEffect: EffectHandler<AiConnectionEffect, AiConnectionIntent> = async (effect, dispatch, signal) => {
    if (effect.type === 'finish') { finish(effect.connected); return; }
    if (effect.type === 'abort') { operation?.abort(); return; }
    operation?.abort();
    operation = new AbortController();
    const requestSignal = AbortSignal.any([signal, operation.signal]);
    let result: ApiResult<ConnectionState>;
    switch (effect.type) {
      case 'read': result = await api.read(requestSignal); break;
      case 'connect': result = await api.connect(effect.apiKey, newIdempotencyKey(), requestSignal); break;
      case 'disconnect': result = await api.disconnect(newIdempotencyKey(), requestSignal); break;
    }
    if (requestSignal.aborted) return;
    if (!result.ok) {
      dispatch({ type: 'failed', request: effect.request, message: errorMessage(result.error) ?? messages.invalidResponse });
    } else if (effect.type === 'read') {
      dispatch({ type: 'loaded', request: effect.request, status: result.data.status });
    } else {
      dispatch({ type: effect.type === 'connect' ? 'connected' : 'disconnected', request: effect.request });
    }
  };
  const store = createStore(aiConnectionReducer, initialAiConnectionState, handleEffect);
  return {
    store,
    ensure(): Promise<boolean> {
      if (pending) return pending.promise;
      let resolve!: (connected: boolean) => void;
      const promise = new Promise<boolean>((done) => { resolve = done; });
      pending = { promise, resolve };
      store.dispatch({ type: 'ensure' });
      return promise;
    },
    manage() { store.dispatch({ type: 'manage' }); },
    cancel() { store.dispatch({ type: 'cancel' }); },
    mountDialog() {
      dialogs += 1;
      return () => {
        dialogs -= 1;
        queueMicrotask(() => {
          if (dialogs === 0 && store.getState().open) store.dispatch({ type: 'cancel' });
        });
      };
    },
    activate() { active = true; store.activate(); },
    deactivate() {
      active = false;
      store.deactivate();
      queueMicrotask(() => { if (!active) { operation?.abort(); finish(false); } });
    },
  };
}

export type AiConnectionController = ReturnType<typeof createAiConnectionController>;
