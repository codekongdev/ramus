import { IDEMPOTENCY_HEADER, toResult, type AppApi } from '../../lib/api';
import type { EffectHandler } from '../../lib/mvi';
import type { ResourcesEffect, ResourcesIntent } from './model';
import { readSkillFile } from './skillFile';

export const SEARCH_DEBOUNCE_MS = 250;

export type ResourcesEffectDeps = {
  readonly api: AppApi;
  /** Closes the modal after a successful apply (WF-10 완료 → 원래 대화로 복귀). */
  readonly close: () => void;
  readonly readBytes?: (file: File) => Promise<Uint8Array>;
  readonly delay?: (ms: number, signal: AbortSignal) => Promise<void>;
};

const defaultReadBytes = async (file: File) => new Uint8Array(await file.arrayBuffer());

function defaultDelay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) return resolve();
    const timer = setTimeout(resolve, ms);
    signal.addEventListener('abort', () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
  });
}

/** Aborts when either the store goes away or a newer request replaces this one. */
function linkedController(parent: AbortSignal): AbortController {
  const controller = new AbortController();
  if (parent.aborted) controller.abort();
  else parent.addEventListener('abort', () => controller.abort(), { once: true });
  return controller;
}

/**
 * One handler per modal instance: it keeps the in-flight search so a newer query cancels the
 * older request (the reducer's sequence check still guards against any late result).
 */
export function makeResourcesEffectHandler(deps: ResourcesEffectDeps): EffectHandler<ResourcesEffect, ResourcesIntent> {
  const { api, close } = deps;
  const readBytes = deps.readBytes ?? defaultReadBytes;
  const delay = deps.delay ?? defaultDelay;
  let searching: AbortController | null = null;

  return async (effect, dispatch, signal) => {
    switch (effect.type) {
      case 'search': {
        searching?.abort();
        const controller = linkedController(signal);
        searching = controller;
        if (effect.debounce) await delay(SEARCH_DEBOUNCE_MS, controller.signal);
        if (controller.signal.aborted) return;
        const result = await toResult(
          api.GET('/api/projects/{project_id}/resources', {
            params: {
              path: { project_id: effect.projectId },
              query: {
                ...(effect.query ? { q: effect.query } : {}),
                ...(effect.conversationId ? { conversation_id: effect.conversationId } : {}),
              },
            },
            signal: controller.signal,
          }),
        );
        if (searching === controller) searching = null;
        if (controller.signal.aborted) return;
        dispatch(
          result.ok
            ? { type: 'searchLoaded', seq: effect.seq, items: result.data.items }
            : { type: 'searchFailed', seq: effect.seq, error: result.error },
        );
        return;
      }

      case 'loadApplied': {
        const result = await toResult(
          api.GET('/api/conversations/{conversation_id}/resources', {
            params: { path: { conversation_id: effect.conversationId } },
            signal,
          }),
        );
        dispatch(
          result.ok
            ? { type: 'appliedLoaded', items: result.data.items }
            : { type: 'appliedFailed', error: result.error },
        );
        return;
      }

      case 'apply': {
        const result = await toResult(
          api.PUT('/api/conversations/{conversation_id}/resources', {
            params: { path: { conversation_id: effect.conversationId } },
            body: { revision_ids: [...effect.revisionIds] },
            headers: { [IDEMPOTENCY_HEADER]: effect.key },
            signal,
          }),
        );
        dispatch(
          result.ok
            ? { type: 'applySucceeded', items: result.data.items }
            : { type: 'applyFailed', error: result.error },
        );
        return;
      }

      case 'create': {
        const result = await toResult(
          api.POST('/api/projects/{project_id}/resources', {
            params: { path: { project_id: effect.projectId } },
            body: effect.body,
            headers: { [IDEMPOTENCY_HEADER]: effect.key },
            signal,
          }),
        );
        dispatch(
          result.ok
            ? { type: 'registerSucceeded', detail: result.data }
            : { type: 'registerFailed', error: result.error },
        );
        return;
      }

      case 'readFile': {
        let bytes: Uint8Array;
        try {
          bytes = await readBytes(effect.file);
        } catch {
          dispatch({ type: 'fileRejected', problem: 'unreadable' });
          return;
        }
        const read = readSkillFile(effect.file.name, bytes);
        dispatch(read.ok ? { type: 'fileLoaded', skill: read.skill } : { type: 'fileRejected', problem: read.problem });
        return;
      }

      case 'close':
        close();
        return;
    }
  };
}
