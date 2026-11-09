import { describe, expect, it } from 'vitest';
import { generating, initialResultState, resultReducer, type ResultState } from '../src/features/results/model';
import { result, revision } from './results-fixtures';
import { task, createdAt } from './fixtures/tasks';

const ready = (): ResultState => ({ ...initialResultState(task.id), taskStatus: 'ready', resultId: result.id, result,
  editor: { text: '검토한 결론', baseVersion: 0, sourceRunId: 'summary1', dirty: true } });
const approved = { ...result, latest_version: 1, latest_revision_id: revision.id, draft: null,
  revisions: [{ id: revision.id, version: 1, saved_by: revision.saved_by, created_at: createdAt }] };

describe('result reducer', () => {
  it('starts one summary for a ready task and blocks work before ready', () => {
    const state = { ...initialResultState(task.id), taskStatus: 'ready' as const };
    const requested = resultReducer(state, { type: 'summarize', key: 'request1' });
    expect(requested.effects).toMatchObject([{ type: 'mutate', taskId: task.id, mutation: { kind: 'summary', key: 'request1' } }]);
    expect(generating(requested.state)).toBe(true);
    expect(resultReducer(requested.state, { type: 'summarize', key: 'duplicate' }).effects).toEqual([]);
    expect(resultReducer({ ...state, taskStatus: 'running' }, { type: 'summarize', key: 'blocked' }).effects).toEqual([]);
  });
  it('keeps edits while server events and reconnection refresh the result', () => {
    const loading = resultReducer(ready(), { type: 'refresh' }).state;
    const updated = resultReducer(loading, { type: 'loaded', taskId: task.id, request: loading.request, result: { ...result, draft: { ...result.draft!, conclusion: '서버 초안' } }, approved: null }).state;
    expect(updated.editor).toEqual(ready().editor);
    expect(resultReducer(updated, { type: 'summarize', key: 'discard' }).effects).toEqual([]);
  });
  it('restores the generated draft when cancelling edits before the first approval', () => {
    const cancelled = resultReducer({ ...ready(), conflict: true, error: '충돌' }, { type: 'cancelEdit' }).state;
    expect(cancelled.approved).toBeNull();
    expect(cancelled.editor).toEqual({ text: result.draft!.conclusion, baseVersion: 0, sourceRunId: 'summary1', dirty: false });
    expect(cancelled.conflict).toBe(false);
    expect(cancelled.error).toBeNull();
    expect(resultReducer(cancelled, { type: 'save', key: 'save-restored' }).effects).toHaveLength(1);
  });
  it('ends editing and retains the approved conclusion when cancelling an approved edit', () => {
    const editing = resultReducer({ ...ready(), result: approved, approved: revision, viewed: revision }, { type: 'editApproved' }).state;
    expect(editing.editor?.text).toBe(revision.conclusion);
    const changed = resultReducer(editing, { type: 'editChanged', text: '취소할 수정' }).state;
    const cancelled = resultReducer(changed, { type: 'cancelEdit' }).state;
    expect(cancelled.editor).toBeNull();
    expect(cancelled.approved).toEqual(revision);
    expect(cancelled.viewed).toEqual(revision);
  });
  it('uses new generated drafts only when there are no local edits', () => {
    const state = resultReducer(initialResultState(task.id), { type: 'taskChanged', task: { ...task, status: 'ready', result_id: result.id } }).state;
    const loaded = resultReducer(state, { type: 'loaded', taskId: task.id, request: state.request, result, approved: null }).state;
    expect(loaded.editor).toEqual({ text: '생성된 결론', baseVersion: 0, sourceRunId: 'summary1', dirty: false });
    const refreshed = resultReducer(loaded, { type: 'refresh' }).state;
    expect(resultReducer(refreshed, { type: 'loaded', taskId: task.id, request: refreshed.request, result: { ...result, latest_version: 1 }, approved: revision }).state.editor).toBeNull();
  });
  it('stores base version and retries an uncertain save with the original idempotency key', () => {
    const saving = resultReducer(ready(), { type: 'save', key: 'original' }).state;
    expect(saving.mutation).toEqual({ kind: 'save', key: 'original', conclusion: '검토한 결론', baseVersion: 0, sourceRunId: 'summary1' });
    expect(resultReducer(saving, { type: 'save', key: 'repeat' }).effects).toEqual([]);
    const failed = resultReducer(saving, { type: 'mutationFailed', taskId: task.id, key: 'original', message: '네트워크 오류', conflict: false }).state;
    expect(resultReducer(failed, { type: 'save', key: 'different' }).state.mutation?.key).toBe('original');
    const edited = resultReducer(failed, { type: 'editChanged', text: '변경한 결론' }).state;
    expect(resultReducer(edited, { type: 'save', key: 'changed' }).state.mutation?.key).toBe('changed');
  });
  it('keeps a conflicting draft until the user explicitly reviews the latest base', () => {
    const saving = resultReducer(ready(), { type: 'save', key: 'save1' }).state;
    const conflict = resultReducer(saving, { type: 'mutationFailed', taskId: task.id, key: 'save1', message: '충돌', conflict: true }).state;
    expect(conflict.editor).toEqual(ready().editor);
    expect(resultReducer(conflict, { type: 'save', key: 'blocked' }).effects).toEqual([]);
    const loaded = resultReducer(conflict, { type: 'loaded', taskId: task.id, request: conflict.request, result: approved, approved: revision }).state;
    expect(loaded.editor?.baseVersion).toBe(0);
    const rebased = resultReducer(loaded, { type: 'rebase' }).state;
    expect(rebased.editor).toEqual({ text: '검토한 결론', baseVersion: 1, sourceRunId: 'summary1', dirty: true });
    expect(rebased.conflict).toBe(false);
    expect(resultReducer(rebased, { type: 'save', key: 'save2' }).state.mutation).toMatchObject({ baseVersion: 1, conclusion: '검토한 결론' });
  });
  it('retains approved content when regeneration fails', () => {
    const state = { ...ready(), editor: null, approved: revision, viewed: revision, result: approved };
    const loading = resultReducer(state, { type: 'refresh' }).state;
    const failed = resultReducer(loading, { type: 'loaded', taskId: task.id, request: loading.request,
      result: { ...approved, draft: { ...result.draft!, status: 'failed', conclusion: null, base_version: 1, error: { code: 'RUN_MODEL_ERROR', message: '정리 실패' } } }, approved: revision }).state;
    expect(failed.approved).toEqual(revision);
    expect(failed.viewed).toEqual(revision);
    expect(failed.editor).toBeNull();
  });
  it('keeps the original source while a different generated draft arrives, then explicitly adopts its source', () => {
    const original = ready();
    const loading = resultReducer(original, { type: 'refresh' }).state;
    const changed = { ...result, draft: { ...result.draft!, run_id: 'summary2', conclusion: '새 정리 초안' } };
    const loaded = resultReducer(loading, { type: 'loaded', taskId: task.id, request: loading.request, result: changed, approved: null }).state;
    expect(loaded.editor).toEqual(original.editor);
    const saving = resultReducer(loaded, { type: 'save', key: 'old-source' }).state;
    expect(saving.mutation).toMatchObject({ sourceRunId: 'summary1' });
    const conflict = resultReducer(saving, { type: 'mutationFailed', taskId: task.id, key: 'old-source', message: '충돌', conflict: true }).state;
    const reviewed = resultReducer(conflict, { type: 'loaded', taskId: task.id, request: conflict.request, result: changed, approved: null }).state;
    const rebased = resultReducer(reviewed, { type: 'rebase' }).state;
    expect(rebased.editor).toEqual({ text: '검토한 결론', dirty: true, baseVersion: 0, sourceRunId: 'summary2' });
    expect(resultReducer(rebased, { type: 'save', key: 'new-source' }).state.mutation).toMatchObject({ sourceRunId: 'summary2', conclusion: '검토한 결론' });
  });
  it('uses the explicitly reviewed latest approved source after a version conflict', () => {
    const latest = { ...revision, id: 'revision2', version: 2, source: { ...revision.source, run_id: 'summary2' } };
    const original = { ...ready(), conflict: true, result: { ...approved, latest_version: 2, latest_revision_id: latest.id }, approved: latest };
    expect(resultReducer(original, { type: 'rebase' }).state.editor).toEqual({ text: '검토한 결론', dirty: true, baseVersion: 2, sourceRunId: 'summary2' });
  });
  it('keeps edits made while saving and advances their base to the saved version', () => {
    const saving = resultReducer(ready(), { type: 'save', key: 'save1' }).state;
    const editing = resultReducer(saving, { type: 'editChanged', text: '저장 중 추가한 내용' }).state;
    const saved = resultReducer(editing, { type: 'saved', taskId: task.id, key: 'save1', revision }).state;
    expect(saved.editor).toEqual({ text: '저장 중 추가한 내용', dirty: true, baseVersion: 1, sourceRunId: 'summary1' });
    expect(saved.approved).toEqual(revision);
  });
  it('keeps edits made while a summary registration is pending', () => {
    const state = { ...ready(), editor: { ...ready().editor!, dirty: false } };
    const pending = resultReducer(state, { type: 'summarize', key: 'summary-key' }).state;
    const edited = resultReducer(pending, { type: 'editChanged', text: '등록 도중 작성한 초안' }).state;
    const completed = resultReducer(edited, { type: 'summarySucceeded', taskId: task.id, key: 'summary-key',
      result: { ...result, draft: { ...result.draft!, status: 'generating', run_id: 'summary2', conclusion: null } } }).state;
    expect(completed.editor).toEqual({ text: '등록 도중 작성한 초안', dirty: true, baseVersion: 0, sourceRunId: 'summary1' });
  });
  it('drops old task responses, old refresh responses and history responses', () => {
    const previous = resultReducer(ready(), { type: 'refresh' }).state;
    const switched = resultReducer(previous, { type: 'taskChanged', task: { ...task, id: 't2', status: 'ready' } }).state;
    expect(switched.editor).toBeNull();
    expect(resultReducer(switched, { type: 'loaded', taskId: task.id, request: previous.request, result, approved: null }).state).toBe(switched);
    expect(resultReducer(switched, { type: 'saved', taskId: task.id, key: 'save1', revision }).state).toBe(switched);
    const latest = resultReducer(previous, { type: 'refresh' }).state;
    expect(resultReducer(latest, { type: 'loaded', taskId: task.id, request: previous.request, result, approved: null }).state).toBe(latest);
    expect(resultReducer(latest, { type: 'revisionLoaded', taskId: task.id, request: 999, revision }).state).toBe(latest);
  });
  it('subscribes only to result updates for this task', () => {
    const event = { type: 'result.updated' as const, data: { result_id: result.id, task_id: task.id, draft_status: 'ready' as const, latest_version: null, occurred_at: createdAt } };
    expect(resultReducer(initialResultState(task.id), { type: 'serverEvent', event }).effects).toMatchObject([{ type: 'load', resultId: result.id }]);
    expect(resultReducer(initialResultState('other'), { type: 'serverEvent', event }).effects).toEqual([]);
  });
  it('does not allow empty saves or saves while generating', () => {
    expect(resultReducer({ ...ready(), editor: { text: '  ', dirty: true, baseVersion: 0, sourceRunId: 'summary1' } }, { type: 'save', key: 'blank' }).effects).toEqual([]);
    expect(resultReducer({ ...ready(), result: { ...result, draft: { ...result.draft!, status: 'generating' } } }, { type: 'save', key: 'busy' }).effects).toEqual([]);
  });
  it('pins the explicitly viewed history revision while realtime refresh discovers newer approvals', () => {
    const original = { ...ready(), result: approved, approved: revision, viewed: revision, editor: null };
    const selected = resultReducer(original, { type: 'selectRevision', revisionId: revision.id }).state;
    expect(selected.viewed).toBeNull();
    const viewed = resultReducer(selected, { type: 'revisionLoaded', taskId: task.id, request: selected.revisionRequest, revision }).state;
    const latest = { ...revision, id: 'revision2', version: 2, conclusion: '새 승인 결론' };
    const refresh = resultReducer(viewed, { type: 'refresh' }).state;
    const updated = resultReducer(refresh, { type: 'loaded', taskId: task.id, request: refresh.request,
      result: { ...approved, latest_revision_id: latest.id, latest_version: 2 }, approved: latest }).state;
    expect(updated.approved).toEqual(latest);
    expect(updated.viewed).toEqual(revision);
  });
  it('invalidates a pending history request after a new version is saved', () => {
    const saving = resultReducer({ ...ready(), result: approved, approved: revision, viewed: revision }, { type: 'save', key: 'save2' }).state;
    const selecting = resultReducer(saving, { type: 'selectRevision', revisionId: revision.id }).state;
    const latest = { ...revision, id: 'revision2', version: 2 };
    const saved = resultReducer(selecting, { type: 'saved', taskId: task.id, key: 'save2', revision: latest }).state;
    expect(saved.viewed).toEqual(latest);
    expect(resultReducer(saved, { type: 'revisionLoaded', taskId: task.id, request: selecting.revisionRequest, revision }).state).toBe(saved);
  });
  it('retries the exact history revision after a failed read', () => {
    const selected = resultReducer({ ...ready(), result: approved, viewed: revision }, { type: 'selectRevision', revisionId: revision.id }).state;
    const failed = resultReducer(selected, { type: 'revisionFailed', taskId: task.id, request: selected.revisionRequest, message: '읽기 실패' }).state;
    const retried = resultReducer(failed, { type: 'retryRead' });
    expect(retried.effects).toEqual([{ type: 'revision', taskId: task.id, resultId: result.id, revisionId: revision.id, request: selected.revisionRequest + 1 }]);
    expect(resultReducer(retried.state, { type: 'revisionLoaded', taskId: task.id, request: retried.state.revisionRequest, revision }).state.viewed).toEqual(revision);
  });
  it('explicitly releases a history pin when reviewing the latest approval after conflict', () => {
    const selected = resultReducer({ ...ready(), result: approved, approved: revision, viewed: revision, conflict: true, error: '충돌 안내' }, { type: 'selectRevision', revisionId: revision.id }).state;
    expect(selected.error).toBe('충돌 안내');
    const reviewed = resultReducer(selected, { type: 'reviewLatest' }).state;
    expect(reviewed.viewedRevisionId).toBeNull();
    expect(reviewed.editor).toEqual(selected.editor);
    const latest = { ...revision, id: 'revision2', version: 2 };
    const loaded = resultReducer(reviewed, { type: 'loaded', taskId: task.id, request: reviewed.request,
      result: { ...approved, latest_revision_id: latest.id, latest_version: 2 }, approved: latest }).state;
    expect(loaded.viewed).toEqual(latest);
    expect(resultReducer(loaded, { type: 'revisionLoaded', taskId: task.id, request: selected.revisionRequest, revision }).state).toBe(loaded);
  });
});
