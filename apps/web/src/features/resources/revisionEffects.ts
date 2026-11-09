import { IDEMPOTENCY_HEADER, toResult, type ApiResult, type AppApi } from '../../lib/api';
import type { EffectHandler } from '../../lib/mvi';
import { isParticipants } from '../auth/api';
import { parseRevisionDetail, parseSavedRevision } from './revisionContract';
import type { RevisionEffect, RevisionIntent } from './revisionModel';
import { decodeText, hasAllowedExtension, MAX_INSTRUCTIONS_LENGTH, MAX_SKILL_FILE_BYTES } from './skillFile';

export type RevisionEffectDeps = {
  readonly api: AppApi;
  readonly readBytes?: (file: File) => Promise<Uint8Array>;
};

function validated<T>(result: ApiResult<unknown>, parse: (value: unknown) => T): ApiResult<T> {
  if (!result.ok) return result;
  try { return { ...result, data: parse(result.data) }; }
  catch { return { ok: false, error: { kind: 'system', status: 502, code: null, message: null, details: null } }; }
}

export function makeRevisionEffects({ api, readBytes = async file => new Uint8Array(await file.arrayBuffer()) }: RevisionEffectDeps): EffectHandler<RevisionEffect, RevisionIntent> {
  let reading: AbortController | null = null;
  return async (effect, dispatch, signal) => {
    if (signal.aborted) return;
    switch (effect.type) {
      case 'load': {
        reading?.abort();
        const controller = new AbortController();
        const abort = () => controller.abort();
        signal.addEventListener('abort', abort, { once: true });
        reading = controller;
        try {
          const response = await toResult(api.GET('/api/resources/{resource_id}', {
            params: {
              path: { resource_id: effect.resourceId },
              query: effect.load.revisionId ? { revision_id: effect.load.revisionId } : {},
            }, signal: controller.signal,
          }));
          if (controller.signal.aborted || signal.aborted) return;
          const result = validated(response, value => parseRevisionDetail(value, effect.resourceId, effect.load.revisionId));
          dispatch(result.ok ? { type: 'loaded', seq: effect.load.seq, detail: result.data }
            : { type: 'loadFailed', seq: effect.load.seq, error: result.error });
        } finally {
          signal.removeEventListener('abort', abort);
          if (reading === controller) reading = null;
        }
        return;
      }
      case 'authors': {
        const result = await toResult(api.GET('/api/projects/{project_id}/participants', {
          params: { path: { project_id: effect.projectId } }, signal,
        }));
        if (!signal.aborted && result.ok && isParticipants(result.data)) {
          dispatch({ type: 'authorsLoaded', authors: Object.fromEntries(result.data.items.map(person => [person.id, person.display_name])) });
        }
        // Account ids remain visible when the optional display-name lookup is unavailable.
        return;
      }
      case 'save': {
        const response = await toResult(api.POST('/api/resources/{resource_id}/revisions', {
          params: { path: { resource_id: effect.resourceId } }, body: effect.attempt.body,
          headers: { [IDEMPOTENCY_HEADER]: effect.attempt.key }, signal,
        }));
        if (signal.aborted) return;
        const result = validated(response, value => parseSavedRevision(value, effect.resourceId, effect.kind, effect.baseNumber, effect.attempt));
        dispatch(result.ok ? { type: 'saved', key: effect.attempt.key, result: result.data }
          : { type: 'saveFailed', key: effect.attempt.key, error: result.error });
        return;
      }
      case 'readFile': {
        if (!hasAllowedExtension(effect.file.name)) {
          dispatch({ type: 'fileRejected', seq: effect.seq, problem: 'extension' }); return;
        }
        if (effect.file.size > MAX_SKILL_FILE_BYTES) {
          dispatch({ type: 'fileRejected', seq: effect.seq, problem: 'tooLarge' }); return;
        }
        let bytes: Uint8Array;
        try { bytes = await readBytes(effect.file); }
        catch {
          if (!signal.aborted) dispatch({ type: 'fileRejected', seq: effect.seq, problem: 'unreadable' });
          return;
        }
        if (signal.aborted) return;
        const text = decodeText(bytes);
        const problem = bytes.byteLength > MAX_SKILL_FILE_BYTES ? 'tooLarge' : text === null ? 'encoding'
          : !text.trim() ? 'empty' : Array.from(text.trim()).length > MAX_INSTRUCTIONS_LENGTH ? 'tooLarge' : null;
        if (problem) dispatch({ type: 'fileRejected', seq: effect.seq, problem });
        else dispatch({ type: 'fileLoaded', seq: effect.seq, name: effect.file.name, content: text! });
        return;
      }
    }
  };
}
