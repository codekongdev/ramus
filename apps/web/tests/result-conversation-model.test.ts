import { describe, expect, it } from 'vitest';
import { canCreate, initialState, reducer, type State } from '../src/features/sharing/model';
import { parent } from './fixtures/tasks';

const project = { id: 'p2', name: '후속 프로젝트', is_shared_sample: false };
function ready(): State {
  let state = reducer(initialState('revision-v1'), { type: 'search' }).state;
  state = reducer(state, { type: 'loaded', request: state.request, projects: [project] }).state;
  state = reducer(state, { type: 'select', projectId: project.id }).state;
  return reducer(state, { type: 'titleChanged', value: '  후속 기획  ' }).state;
}

describe('result conversation reducer', () => {
  it('requires an explicitly selected authorized project and a nonblank bounded title', () => {
    expect(canCreate(initialState('v1'))).toBe(false);
    const state = ready();
    expect(canCreate(state)).toBe(true);
    expect(canCreate({ ...state, selected: null })).toBe(false);
    expect(canCreate({ ...state, title: '   ' })).toBe(false);
    expect(canCreate({ ...state, title: 'a'.repeat(100) })).toBe(true);
    expect(canCreate({ ...state, title: 'a'.repeat(101) })).toBe(false);
    expect(reducer(initialState('v1'), { type: 'select', projectId: 'hidden' }).state.selected).toBeNull();
  });
  it('ignores stale searches, preserving the selected project across different queries', () => {
    let state = reducer(ready(), { type: 'queryChanged', value: '없는 검색어' }).state;
    expect(state.projects).toEqual([]);
    expect(state.selected).toEqual(project);
    expect(reducer(state, { type: 'loaded', request: state.request - 1, projects: [] }).state).toBe(state);
    state = reducer(state, { type: 'loaded', request: state.request, projects: [] }).state;
    expect(state.projects).toEqual([]);
    expect(state.selected).toEqual(project);
  });
  it('captures exactly the old revision and trims the title; blocks duplicate creates and changes while sending', () => {
    const result = reducer(ready(), { type: 'submit', key: 'one-action' });
    expect(result.effects).toEqual([{ type: 'create', operation: { key: 'one-action', projectId: 'p2', revisionId: 'revision-v1', title: '후속 기획' } }]);
    for (const intent of [
      { type: 'submit' as const, key: 'duplicate' }, { type: 'titleChanged' as const, value: 'changed' },
      { type: 'queryChanged' as const, value: 'changed' }, { type: 'select' as const, projectId: project.id },
    ]) expect(reducer(result.state, intent).state).toBe(result.state);
  });
  it('reuses the request key after a lost response and creates a new action if the payload changes', () => {
    const sending = reducer(ready(), { type: 'submit', key: 'original' }).state;
    const failed = reducer(sending, { type: 'createFailed', key: 'original', error: { kind: 'network', cause: null } }).state;
    expect(reducer(failed, { type: 'submit', key: 'new' }).state.operation?.key).toBe('original');
    const changed = reducer(failed, { type: 'titleChanged', value: '다른 제목' }).state;
    expect(reducer(changed, { type: 'submit', key: 'new' }).state.operation?.key).toBe('new');
  });
  it('preserves the title and conclusion on permission loss but requires choosing a project again', () => {
    const sending = reducer(ready(), { type: 'submit', key: 'one' }).state;
    const failed = reducer(sending, { type: 'createFailed', key: 'one', error: { kind: 'business', status: 403, code: 'PROJECT_CREATE_FORBIDDEN', message: 'forbidden', details: null } }).state;
    expect(failed.selected).toBeNull();
    expect(failed.title).toBe('  후속 기획  ');
    expect(failed.revisionId).toBe('revision-v1');
    expect(canCreate(failed)).toBe(false);
  });
  it('navigates once only after the matching creation succeeds', () => {
    const sending = reducer(ready(), { type: 'submit', key: 'one' }).state;
    const conversation = { ...parent, project_id: 'p2', title: '후속 기획' };
    expect(reducer(sending, { type: 'created', key: 'stale', conversation }).state).toBe(sending);
    const done = reducer(sending, { type: 'created', key: 'one', conversation });
    expect(done.effects).toEqual([{ type: 'navigate', conversation }]);
    expect(reducer(done.state, { type: 'submit', key: 'two' }).effects).toEqual([]);
    expect(reducer(done.state, { type: 'created', key: 'one', conversation }).effects).toEqual([]);
  });
});
