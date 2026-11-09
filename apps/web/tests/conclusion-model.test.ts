import { describe, expect, it } from 'vitest';
import { conclusionReducer, initialConclusionState } from '../src/features/results/conclusionModel';
import { revision } from './results-fixtures';

describe('conclusion reader reducer', () => {
  it('loads only the selected immutable revision and retries after failure', () => {
    const opened = conclusionReducer(initialConclusionState(revision.id), { type: 'open', revisionId: revision.id });
    expect(opened.state.loading).toBe(true);
    expect(opened.effects).toEqual([{ type: 'load', revisionId: revision.id, request: opened.state.request }]);
    const failed = conclusionReducer(opened.state, {
      type: 'failed', revisionId: revision.id, request: opened.state.request, message: '다시 시도해 주세요.',
    }).state;
    expect(failed.loading).toBe(false);
    expect(failed.error).toBe('다시 시도해 주세요.');
    const retried = conclusionReducer(failed, { type: 'retry' });
    expect(retried.state.loading).toBe(true);
    expect(retried.state.error).toBeNull();
    expect(retried.state.request).toBeGreaterThan(opened.state.request);
    expect(retried.effects).toEqual([{ type: 'load', revisionId: revision.id, request: retried.state.request }]);
    const loaded = conclusionReducer(retried.state, {
      type: 'loaded', revisionId: revision.id, request: retried.state.request, revision,
    });
    expect(loaded.state.revision).toEqual(revision);
    expect(loaded.state.loading).toBe(false);
    expect(loaded.effects).toEqual([]);
  });

  it('clears the previous body when the target changes and ignores late responses', () => {
    const opened = conclusionReducer(initialConclusionState(revision.id), { type: 'open', revisionId: revision.id }).state;
    const loaded = conclusionReducer(opened, {
      type: 'loaded', revisionId: revision.id, request: opened.request, revision,
    }).state;
    const switched = conclusionReducer(loaded, { type: 'open', revisionId: 'revision2' }).state;
    expect(switched.revisionId).toBe('revision2');
    expect(switched.revision).toBeNull();
    expect(switched.loading).toBe(true);
    expect(conclusionReducer(switched, {
      type: 'loaded', revisionId: revision.id, request: opened.request, revision,
    }).state).toBe(switched);
    expect(conclusionReducer(switched, {
      type: 'failed', revisionId: revision.id, request: opened.request, message: '늦은 오류',
    }).state).toBe(switched);
  });

  it('ignores an older request even when its revision id is the same', () => {
    const first = conclusionReducer(initialConclusionState(revision.id), { type: 'open', revisionId: revision.id }).state;
    expect(conclusionReducer(first, { type: 'retry' }).effects).toEqual([]);
    const failed = conclusionReducer(first, {
      type: 'failed', revisionId: revision.id, request: first.request, message: '다시 시도해 주세요.',
    }).state;
    const retried = conclusionReducer(failed, { type: 'retry' }).state;
    expect(conclusionReducer(retried, {
      type: 'loaded', revisionId: revision.id, request: first.request, revision,
    }).state).toBe(retried);
    expect(conclusionReducer(retried, {
      type: 'failed', revisionId: revision.id, request: first.request, message: '늦은 오류',
    }).state).toBe(retried);
  });
});
