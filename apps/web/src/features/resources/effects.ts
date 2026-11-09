import { IDEMPOTENCY_HEADER, toResult, type ApiResult, type AppApi } from '../../lib/api';
import type { EffectHandler } from '../../lib/mvi';
import { parseAppliedResourceList, parseResourceDetail, parseResourceSummaryList } from './contract';
import type { ResourcesEffect, ResourcesIntent } from './model';
import { hasAllowedExtension, MAX_SKILL_FILE_BYTES, readSkillFile } from './skillFile';

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

function validateResult<T>(result: ApiResult<unknown>, parse: (value: unknown) => T): ApiResult<T> {
  if (!result.ok) return result;
  try {
    return { ...result, data: parse(result.data) };
  } catch {
    return { ok: false, error: { kind: 'system', status: 502, code: null, message: null, details: null } };
  }
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
  let appliedRead: AbortController | null = null;

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
        const validated = validateResult(result, parseResourceSummaryList);
        dispatch(
          validated.ok
            ? { type: 'searchLoaded', seq: effect.seq, items: validated.data.items }
            : { type: 'searchFailed', seq: effect.seq, error: validated.error },
        );
        return;
      }

      case 'loadApplied': {
        appliedRead?.abort();
        const controller = linkedController(signal);
        appliedRead = controller;
        const result = await toResult(
          api.GET('/api/conversations/{conversation_id}/resources', {
            params: { path: { conversation_id: effect.conversationId } },
            signal: controller.signal,
          }),
        );
        if (controller.signal.aborted) return;
        const validated = validateResult(result, parseAppliedResourceList);
        dispatch(
          validated.ok
            ? { type: 'appliedLoaded', items: validated.data.items }
            : { type: 'appliedFailed', error: validated.error },
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
        const validated = validateResult(result, parseAppliedResourceList);
        dispatch(
          validated.ok
            ? { type: 'applySucceeded', items: validated.data.items }
            : { type: 'applyFailed', error: validated.error },
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
        const validated = validateResult(result, parseResourceDetail);
        dispatch(
          validated.ok
            ? { type: 'registerSucceeded', detail: validated.data }
            : { type: 'registerFailed', error: validated.error },
        );
        return;
      }

      case 'readFile': {
        if (!hasAllowedExtension(effect.file.name) || effect.file.size > MAX_SKILL_FILE_BYTES) {
          dispatch({ type: 'fileRejected', seq: effect.seq, problem: hasAllowedExtension(effect.file.name) ? 'tooLarge' : 'extension' });
          return;
        }
        let bytes: Uint8Array;
        try {
          bytes = await readBytes(effect.file);
        } catch {
          if (!signal.aborted) dispatch({ type: 'fileRejected', seq: effect.seq, problem: 'unreadable' });
          return;
        }
        if (signal.aborted) return;
        const read = readSkillFile(effect.file.name, bytes);
        dispatch(read.ok ? { type: 'fileLoaded', seq: effect.seq, skill: read.skill } : { type: 'fileRejected', seq: effect.seq, problem: read.problem });
        return;
      }

      case 'close':
        close();
        return;
    }
  };
}
