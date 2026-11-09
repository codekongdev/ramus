import { describe, expect, it, vi } from 'vitest';
import type { ApiError, AppApi } from '../../../src/lib/api';
import type { ResourceDetail, ResourceKind } from '../../../src/features/resources/model';
import { parseRevisionDetail, parseSavedRevision } from '../../../src/features/resources/revisionContract';
import { makeRevisionEffects } from '../../../src/features/resources/revisionEffects';
import { initialRevisionState, type ResourceRevision, type RevisionEffect, type RevisionIntent, type RevisionState } from '../../../src/features/resources/revisionModel';
import { revisionBody, revisionReducer as reduce, validateRevisionDraft } from '../../../src/features/resources/revisionReducer';

const networkError: ApiError = { kind: 'network', cause: new Error('response lost') };
const conflict: ApiError = { kind: 'business', status: 409, code: 'VERSION_CONFLICT', message: 'conflict', details: null };
const revision = (number: number, kind: ResourceKind = 'skill'): ResourceRevision => ({
  id: `r-v${number}`, resource_id: 'r', number, name: `공통 기준 ${number}`, description: '출처를 확인한다.',
  instructions: kind === 'skill' ? `지침 ${number}` : null,
  content: kind === 'skill' ? null : `자료 내용 ${number}`, file_name: kind === 'file' ? `reference-${number}.md` : null,
  created_by: `author-${number}`, created_at: `2026-11-09T00:0${number}:00Z`,
});
function detail(latest = 1, selected = latest, kind: ResourceKind = 'skill'): ResourceDetail {
  return { id: 'r', kind, latest_revision_id: `r-v${latest}`, revision: revision(selected, kind),
    revisions: Array.from({ length: latest }, (_, index) => {
      const { id, number, name, created_by, created_at } = revision(index + 1, kind);
      return { id, number, name, created_by, created_at };
    }) };
}
function ready(kind: ResourceKind = 'skill'): RevisionState {
  const opened = reduce(initialRevisionState('r', 'p'), { type: 'opened' });
  return reduce(opened.state, { type: 'loaded', seq: opened.state.seq, detail: detail(1, 1, kind) }).state;
}
function editing(kind: ResourceKind = 'skill'): RevisionState {
  const requested = reduce(ready(kind), { type: 'editRequested' }).state;
  return reduce(requested, { type: 'loaded', seq: requested.seq, detail: detail(1, 1, kind) }).state;
}

describe('resource revision reducer', () => {
  it('drops an old history response when a newer version was requested', () => {
    const first = reduce(ready(), { type: 'viewRequested', revisionId: 'r-v1' }).state;
    const second = reduce(first, { type: 'viewRequested', revisionId: 'r-v2' }).state;
    expect(reduce(second, { type: 'loaded', seq: first.seq, detail: detail(2, 1) }).state).toBe(second);
    expect(reduce(second, { type: 'loaded', seq: second.seq, detail: detail(2) }).state.detail?.revision.number).toBe(2);
  });

  it('reads the latest version before editing and ignores refreshes that could replace its base or draft', () => {
    const request = reduce(ready(), { type: 'editRequested' });
    expect(request.effects).toEqual([{ type: 'load', resourceId: 'r', load: { seq: request.state.seq, revisionId: null, purpose: 'edit' } }]);
    expect(reduce(request.state, { type: 'refresh' }).effects).toEqual([]);
    const loaded = reduce(request.state, { type: 'loaded', seq: request.state.seq, detail: detail(2) }).state;
    const edited = reduce(loaded, { type: 'fieldChanged', field: 'body', value: '내 초안' }).state;
    expect(edited.draft?.baseId).toBe('r-v2');
    expect(reduce(edited, { type: 'refresh' }).state).toBe(edited);
    expect(reduce(edited, { type: 'loaded', seq: request.state.seq, detail: detail(1) }).state).toBe(edited);
  });

  it('keeps the original base and draft across a conflict, latest-version inspection, and return', () => {
    let state = reduce(editing(), { type: 'fieldChanged', field: 'body', value: '진행 중인 초안' }).state;
    state = reduce(state, { type: 'saveRequested', key: 'save-1' }).state;
    state = reduce(state, { type: 'saveFailed', key: 'save-1', error: conflict }).state;
    const checking = reduce(state, { type: 'checkLatest' });
    const inspected = reduce(checking.state, { type: 'loaded', seq: checking.state.seq, detail: detail(2) }).state;
    expect(inspected.phase).toBe('detail');
    expect(inspected.detail?.revision.number).toBe(2);
    const resumed = reduce(inspected, { type: 'resumeDraft' }).state;
    expect(resumed.draft).toMatchObject({ body: '진행 중인 초안', baseId: 'r-v1', baseNumber: 1 });
    const request = reduce(resumed, { type: 'saveRequested', key: 'new-key' });
    expect(request.effects[0]).toMatchObject({ type: 'save', attempt: { key: 'save-1', body: { base_revision_id: 'r-v1' } } });
  });

  it('reuses a failed request key only for the same normalized body', () => {
    const first = reduce(editing(), { type: 'saveRequested', key: 'first' });
    const failed = reduce(first.state, { type: 'saveFailed', key: 'first', error: networkError }).state;
    const retried = reduce(failed, { type: 'saveRequested', key: 'second' });
    expect(retried.effects[0]).toMatchObject({ attempt: { key: 'first' } });
    const changed = reduce(failed, { type: 'fieldChanged', field: 'name', value: '새 이름' }).state;
    expect(reduce(changed, { type: 'saveRequested', key: 'third' }).effects[0]).toMatchObject({ attempt: { key: 'third' } });
    expect(reduce(first.state, { type: 'saveRequested', key: 'duplicate' }).effects).toEqual([]);
  });

  it('shows the saved revision and reloads its history without emitting an apply operation', () => {
    const saving = reduce(editing(), { type: 'saveRequested', key: 'save' }).state;
    const result = reduce(saving, { type: 'saved', key: 'save', result: { revision: revision(2), created: true } });
    expect(result.state).toMatchObject({ phase: 'detail', draft: null, saving: false, notice: 'saved' });
    expect(result.state.detail?.revision.number).toBe(2);
    expect(result.effects).toEqual([{ type: 'load', resourceId: 'r', load: { seq: result.state.seq, revisionId: 'r-v2', purpose: 'view' } }]);
    expect(reduce(saving, { type: 'saved', key: 'wrong-key', result: { revision: revision(2), created: true } }).state).toBe(saving);
  });

  it('preserves a valid file draft and blocks saving after a rejected replacement until a valid file is read', () => {
    const renamed = reduce(editing('file'), { type: 'fieldChanged', field: 'name', value: '다른 이름' }).state;
    const reading = reduce(renamed, { type: 'fileChosen', file: { name: 'bad.pdf' } as File }).state;
    const rejected = reduce(reading, { type: 'fileRejected', seq: reading.fileSeq, problem: 'extension' }).state;
    expect(rejected.draft).toEqual(renamed.draft);
    expect(reduce(rejected, { type: 'saveRequested', key: 'must-not-save' }).effects).toEqual([]);
    const retry = reduce(rejected, { type: 'fileChosen', file: { name: 'valid.txt' } as File }).state;
    const accepted = reduce(retry, { type: 'fileLoaded', seq: retry.fileSeq, name: 'valid.txt', content: '교체한 자료' }).state;
    expect(reduce(accepted, { type: 'saveRequested', key: 'save' }).effects[0]).toMatchObject({ attempt: { body: { content: '교체한 자료', file_name: 'valid.txt', instructions: null } } });
  });

  it('cancelling a file read prevents its late result from restoring a discarded draft', () => {
    const reading = reduce(editing('file'), { type: 'fileChosen', file: {} as File }).state;
    const cancelled = reduce(reading, { type: 'cancelEdit' }).state;
    expect(cancelled.draft).toBeNull();
    expect(reduce(cancelled, { type: 'fileLoaded', seq: reading.fileSeq, name: 'late.txt', content: 'late' }).state).toBe(cancelled);
  });

  it('validates required bodies, file extensions, code-point lengths, and unpersistable text', () => {
    const draft = editing('file').draft!;
    expect(validateRevisionDraft({ ...draft, body: ' ', fileName: 'bad.pdf' })).toEqual({ body: 'required', fileName: 'extension' });
    expect(validateRevisionDraft({ ...draft, name: '😀'.repeat(100) })).toEqual({});
    expect(validateRevisionDraft({ ...draft, name: '😀'.repeat(101) })).toEqual({ name: 'tooLong' });
    expect(validateRevisionDraft({ ...draft, name: 'bad\u0000name', body: '\ud800' })).toEqual({ name: 'invalidText', body: 'invalidText' });
  });
});

describe('resource revision boundary validation', () => {
  it('accepts a historical revision while retaining the actual latest id', () => {
    expect(parseRevisionDetail(detail(2, 1), 'r', 'r-v1').latest_revision_id).toBe('r-v2');
  });

  it.each([
    ['foreign resource', { ...detail(), id: 'other' }],
    ['foreign revision', { ...detail(), revision: { ...revision(1), resource_id: 'other' } }],
    ['missing latest', { ...detail(), latest_revision_id: 'missing' }],
    ['invalid timestamp', { ...detail(), revision: { ...revision(1), created_at: 'invalid' } }],
    ['inconsistent history', { ...detail(), revisions: [{ ...detail().revisions[0], number: 2 }] }],
    ['wrong kind body', { ...detail(), revision: { ...revision(1), instructions: null, content: 'wrong' } }],
  ])('rejects %s', (_label, value) => {
    expect(() => parseRevisionDetail(value, 'r', null)).toThrow('Invalid resource API response');
  });

  it('checks a saved revision against the original request, base, and reported created flag', () => {
    const draft = { ...editing().draft!, body: '새 지침' };
    const attempt = { key: 'save', body: revisionBody(draft) };
    const saved = { ...revision(2), name: draft.name, description: draft.description, instructions: draft.body };
    expect(parseSavedRevision({ revision: saved, created: true }, 'r', 'skill', 1, attempt).revision.number).toBe(2);
    expect(() => parseSavedRevision({ revision: { ...saved, instructions: '다른 지침' }, created: true }, 'r', 'skill', 1, attempt)).toThrow();
    expect(() => parseSavedRevision({ revision: saved, created: false }, 'r', 'skill', 1, attempt)).toThrow();
    expect(() => parseSavedRevision({ revision: { ...saved, number: 7 }, created: true }, 'r', 'skill', 1, attempt)).toThrow();
  });
});

describe('resource revision effects', () => {
  it('aborts replaced history reads and drops their late responses', async () => {
    const replies: ((value: unknown) => void)[] = [];
    const signals: AbortSignal[] = [];
    const api = { GET: vi.fn((_path, options) => {
      signals.push(options.signal);
      return new Promise(resolve => { replies.push(resolve); });
    }) } as unknown as AppApi;
    const handler = makeRevisionEffects({ api });
    const dispatched: RevisionIntent[] = [];
    const signal = new AbortController().signal;
    const request = (seq: number, revisionId: string): RevisionEffect => ({ type: 'load', resourceId: 'r', load: { seq, revisionId, purpose: 'view' } });
    const first = handler(request(1, 'r-v1'), value => dispatched.push(value), signal);
    const second = handler(request(2, 'r-v2'), value => dispatched.push(value), signal);
    expect(signals[0].aborted).toBe(true);
    replies[1]({ data: detail(2), response: new Response(null, { status: 200 }) });
    await second;
    replies[0]({ data: detail(2, 1), response: new Response(null, { status: 200 }) });
    await first;
    expect(dispatched).toEqual([{ type: 'loaded', seq: 2, detail: detail(2) }]);
  });

  it('sends the exact baseline and idempotency key and rejects an inconsistent success response', async () => {
    const api = { POST: vi.fn(async () => ({ data: { created: true, revision: revision(2) }, response: new Response(null, { status: 200 }) })) } as unknown as AppApi;
    const handler = makeRevisionEffects({ api });
    const dispatch = vi.fn();
    const body = revisionBody(editing().draft!);
    await handler({ type: 'save', resourceId: 'r', kind: 'skill', baseNumber: 1, attempt: { key: 'stable-key', body } }, dispatch, new AbortController().signal);
    expect(api.POST).toHaveBeenCalledWith('/api/resources/{resource_id}/revisions', expect.objectContaining({ body, headers: { 'Idempotency-Key': 'stable-key' } }));
    expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'saveFailed', key: 'stable-key', error: expect.objectContaining({ kind: 'system', status: 502 }) }));
  });
});
