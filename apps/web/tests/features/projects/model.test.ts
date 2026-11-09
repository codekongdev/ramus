import { describe, expect, it } from 'vitest';
import { initialProjectsState, projectsReducer, type ProjectsState } from '../../../src/features/projects/model';
import type { ApiError } from '../../../src/lib/api';

const project = { id: 'p1', name: 'Research', is_shared_sample: false };
const network: ApiError = { kind: 'network', cause: new TypeError('offline') };
const form: ProjectsState = { ...initialProjectsState, open: true, mode: 'create', name: '  Research  ' };

describe('project navigation and creation', () => {
  it('refreshes accessible projects on open and ignores old list responses', () => {
    const first = projectsReducer(initialProjectsState, { type: 'open' });
    expect(first.effects).toEqual([{ type: 'load', generation: 1 }]);
    expect(projectsReducer(first.state, { type: 'open' }).effects).toEqual([]);
    const loaded = projectsReducer(first.state, { type: 'loaded', generation: 1, items: [project] }).state;
    const reopened = projectsReducer(projectsReducer(loaded, { type: 'close' }).state, { type: 'open' });
    expect(reopened.effects).toEqual([{ type: 'load', generation: 2 }]);
    expect(projectsReducer(reopened.state, { type: 'loaded', generation: 1, items: [] }).state).toBe(reopened.state);
  });

  it('only navigates to an accessible project while the selector is open', () => {
    const state = { ...initialProjectsState, open: true, items: [project] };
    expect(projectsReducer(state, { type: 'select', projectId: 'unknown' }).effects).toEqual([]);
    expect(projectsReducer(state, { type: 'select', projectId: project.id })).toMatchObject({
      state: { open: false }, effects: [{ type: 'navigate', projectId: project.id }],
    });
    expect(projectsReducer({ ...state, open: false }, { type: 'select', projectId: project.id }).effects).toEqual([]);
  });

  it.each(['', ' \n\t ', 'a'.repeat(101)])('rejects an invalid name without issuing a mutation: %j', name => {
    const result = projectsReducer({ ...form, name }, { type: 'submit', key: 'invalid' });
    expect(result.effects).toEqual([]);
    expect(result.state.nameError).toBeTruthy();
    expect(result.state.name).toBe(name);
  });

  it('counts Unicode characters and trims names before creating', () => {
    const result = projectsReducer({ ...form, name: ` ${'🌳'.repeat(100)} ` }, { type: 'submit', key: 'unicode' });
    expect(result.effects).toEqual([{ type: 'create', operation: { key: 'unicode', name: '🌳'.repeat(100) } }]);
  });

  it('blocks duplicate submissions and switching or closing during creation', () => {
    const pending = projectsReducer(form, { type: 'submit', key: 'first' });
    expect(pending.effects).toEqual([{ type: 'create', operation: { name: 'Research', key: 'first' } }]);
    for (const intent of [{ type: 'submit', key: 'duplicate' }, { type: 'close' }, { type: 'nameChanged', value: 'Changed' }, { type: 'showList' }, { type: 'select', projectId: project.id }] as const) {
      expect(projectsReducer(pending.state, intent).state).toBe(pending.state);
    }
  });

  it('keeps the name and same operation key when retrying an uncertain creation', () => {
    const pending = projectsReducer(form, { type: 'submit', key: 'first' });
    const failed = projectsReducer(pending.state, { type: 'createFailed', key: 'first', error: network }).state;
    expect(failed).toMatchObject({ creating: false, name: form.name });
    expect(projectsReducer(failed, { type: 'submit', key: 'ignored' }).effects).toEqual(pending.effects);
    const renamed = projectsReducer(failed, { type: 'nameChanged', value: 'Other project' }).state;
    expect(projectsReducer(renamed, { type: 'submit', key: 'new-action' }).effects).toEqual([
      { type: 'create', operation: { key: 'new-action', name: 'Other project' } },
    ]);
  });

  it('ignores stale mutation results and navigates once after success', () => {
    const pending = projectsReducer(form, { type: 'submit', key: 'first' }).state;
    expect(projectsReducer(pending, { type: 'created', key: 'old', project }).state).toBe(pending);
    const created = projectsReducer(pending, { type: 'created', key: 'first', project });
    expect(created).toMatchObject({ state: { open: false, creating: false, name: '' }, effects: [{ type: 'navigate', projectId: project.id }] });
    expect(projectsReducer(created.state, { type: 'created', key: 'first', project }).effects).toEqual([]);
  });

  it('expires the session when project requests are unauthorized', () => {
    const pending = projectsReducer(form, { type: 'submit', key: 'first' }).state;
    const error: ApiError = { kind: 'business', status: 401, code: 'UNAUTHORIZED', message: 'login', details: null };
    expect(projectsReducer(pending, { type: 'createFailed', key: 'first', error }).state.unauthorized).toBe(true);
    expect(projectsReducer(initialProjectsState, { type: 'loadFailed', generation: 0, error }).state.unauthorized).toBe(true);
  });
});
