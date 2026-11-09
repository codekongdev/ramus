import { describe, expect, it } from 'vitest';
import type { ApiError } from '../../../src/lib/api';
import {
  initialResourcesState,
  type AppliedResource,
  type ResourceDetail,
  type ResourceSummary,
  type ResourcesIntent,
  type ResourcesState,
} from '../../../src/features/resources/model';
import { canApply, resourcesReducer, validateSkillForm } from '../../../src/features/resources/reducer';

const P = 'project-1';
const C = 'conversation-1';

const summary = (id: string, latest: number, applied: number | null = null): ResourceSummary => ({
  id,
  kind: 'skill',
  latest: { revision_id: `${id}-v${latest}`, number: latest, name: `name-${id}`, description: '' },
  applied: applied === null ? null : { revision_id: `${id}-v${applied}`, number: applied },
});

const appliedItem = (id: string, number: number): AppliedResource => ({
  resource_id: id,
  revision_id: `${id}-v${number}`,
  number,
  name: `name-${id}`,
  kind: 'skill',
});

const businessError: ApiError = { kind: 'business', status: 422, code: 'INVALID_INPUT', message: 'bad', details: null };

function run(state: ResourcesState, ...intents: ResourcesIntent[]) {
  let current = state;
  const effects = [];
  for (const intent of intents) {
    const result = resourcesReducer(current, intent);
    current = result.state;
    effects.push(...result.effects);
  }
  return { state: current, effects };
}

/** Opened, with search results and the conversation's applied list loaded. */
function ready(items: ResourceSummary[], applied: AppliedResource[] = [], conversationId: string | null = C) {
  const opened = run(initialResourcesState(P, conversationId), { type: 'opened' });
  return run(
    opened.state,
    { type: 'searchLoaded', seq: opened.state.searchSeq, items },
    ...(conversationId ? [{ type: 'appliedLoaded', items: applied } as const] : []),
  ).state;
}

describe('opening', () => {
  it('searches everything and loads the applied list', () => {
    const { state, effects } = run(initialResourcesState(P, C), { type: 'opened' });
    expect(state.search.status).toBe('loading');
    expect(effects).toEqual([
      { type: 'search', projectId: P, conversationId: C, query: '', seq: 1, debounce: false },
      { type: 'loadApplied', conversationId: C },
    ]);
  });

  it('does not load an applied list without a conversation', () => {
    const { state, effects } = run(initialResourcesState(P, null), { type: 'opened' });
    expect(effects.map((effect) => effect.type)).toEqual(['search']);
    expect(canApply(ready([summary('a', 1)], [], null))).toBe(false);
    expect(state.conversationId).toBeNull();
  });

  it('starts the selection from the applied versions (F-09: exact version, not latest)', () => {
    const state = ready([summary('a', 2, 1)], [appliedItem('a', 1)]);
    expect(state.selection).toEqual([
      { resourceId: 'a', revisionId: 'a-v1', number: 1, name: 'name-a', kind: 'skill' },
    ]);
    expect(canApply(state)).toBe(false);
  });
});

describe('search', () => {
  it('debounces typing and drops late results of older queries', () => {
    const start = ready([summary('a', 1)]);
    const typed = run(start, { type: 'queryChanged', query: '벤치' }, { type: 'queryChanged', query: '벤치마킹' });
    expect(typed.effects).toEqual([
      expect.objectContaining({ type: 'search', query: '벤치', debounce: true, seq: 2 }),
      expect.objectContaining({ type: 'search', query: '벤치마킹', debounce: true, seq: 3 }),
    ]);
    const late = run(typed.state, { type: 'searchLoaded', seq: 2, items: [summary('old', 1)] });
    expect(late.state.search.status).toBe('loading');
    const fresh = run(late.state, { type: 'searchLoaded', seq: 3, items: [summary('b', 1)] });
    expect(fresh.state.search).toEqual({ status: 'ready', data: [summary('b', 1)] });
  });

  it('keeps the selection across queries (WF-10)', () => {
    const start = ready([summary('a', 1)]);
    const selected = run(start, { type: 'toggled', resource: summary('a', 1) });
    const searched = run(selected.state, { type: 'queryChanged', query: 'zzz' }, { type: 'searchLoaded', seq: 2, items: [] });
    expect(searched.state.selection.map((item) => item.resourceId)).toEqual(['a']);
  });

  it('ignores aborted searches and shows other failures', () => {
    const start = run(initialResourcesState(P, C), { type: 'opened' }).state;
    expect(run(start, { type: 'searchFailed', seq: 1, error: { kind: 'aborted' } }).state.search.status).toBe('loading');
    expect(run(start, { type: 'searchFailed', seq: 1, error: businessError }).state.search).toEqual({
      status: 'failed',
      error: businessError,
    });
  });
});

describe('selection', () => {
  it('selects the latest version and shows it next to the applied one', () => {
    const state = ready([summary('a', 2, 1), summary('b', 1)], [appliedItem('a', 1)]);
    const { state: next } = run(state, { type: 'toggled', resource: summary('b', 1) });
    expect(next.selection.map((item) => item.revisionId)).toEqual(['a-v1', 'b-v1']);
    expect(canApply(next)).toBe(true);
  });

  it('switches a selected resource to its latest version only when asked', () => {
    const state = ready([summary('a', 2, 1)], [appliedItem('a', 1)]);
    const { state: next } = run(state, { type: 'latestChosen', resource: summary('a', 2, 1) });
    expect(next.selection.map((item) => item.revisionId)).toEqual(['a-v2']);
    expect(canApply(next)).toBe(true);
  });

  it('removes a chip', () => {
    const state = ready([summary('a', 1)], [appliedItem('a', 1)]);
    expect(run(state, { type: 'deselected', resourceId: 'a' }).state.selection).toEqual([]);
  });

  it('does not reset a touched selection when the applied list reloads', () => {
    const state = ready([summary('a', 1), summary('b', 1)]);
    const touched = run(state, { type: 'toggled', resource: summary('b', 1) }, { type: 'appliedLoaded', items: [appliedItem('a', 1)] });
    expect(touched.state.selection.map((item) => item.resourceId)).toEqual(['b']);
  });
});

describe('apply', () => {
  it('is disabled without a selection (WF-10: 선택 없이 적용하지 않는다)', () => {
    const state = ready([summary('a', 1)], [appliedItem('a', 1)]);
    const cleared = run(state, { type: 'deselected', resourceId: 'a' }).state;
    expect(canApply(cleared)).toBe(false);
    expect(run(cleared, { type: 'applyRequested', key: 'k1' }).effects).toEqual([]);
  });

  it('sends the exact revision ids and closes on success', () => {
    const state = run(ready([summary('a', 2, 1)], [appliedItem('a', 1)]), {
      type: 'latestChosen',
      resource: summary('a', 2, 1),
    }).state;
    const requested = run(state, { type: 'applyRequested', key: 'k1' });
    expect(requested.effects).toEqual([{ type: 'apply', conversationId: C, revisionIds: ['a-v2'], key: 'k1' }]);
    expect(canApply(requested.state)).toBe(false);

    const done = run(requested.state, { type: 'applySucceeded', items: [appliedItem('a', 2)] });
    expect(done.effects).toEqual([{ type: 'close' }]);
    expect(done.state.applied).toEqual({ status: 'ready', data: [appliedItem('a', 2)] });
  });

  it('keeps query and selection on failure and reuses the key for the same retry', () => {
    const start = run(ready([summary('a', 1)]), { type: 'queryChanged', query: 'a' }, { type: 'searchLoaded', seq: 2, items: [summary('a', 1)] });
    const selected = run(start.state, { type: 'toggled', resource: summary('a', 1) }).state;
    const failed = run(selected, { type: 'applyRequested', key: 'k1' }, { type: 'applyFailed', error: businessError });
    expect(failed.state.query).toBe('a');
    expect(failed.state.selection.map((item) => item.revisionId)).toEqual(['a-v1']);
    expect(failed.state.apply.error).toEqual(businessError);

    const retried = run(failed.state, { type: 'applyRequested', key: 'k2' });
    expect(retried.effects).toEqual([expect.objectContaining({ type: 'apply', key: 'k1' })]);
  });

  it('uses a new key when the selection changed after a failure', () => {
    const state = ready([summary('a', 1), summary('b', 1)]);
    const failed = run(
      state,
      { type: 'toggled', resource: summary('a', 1) },
      { type: 'applyRequested', key: 'k1' },
      { type: 'applyFailed', error: businessError },
      { type: 'toggled', resource: summary('b', 1) },
      { type: 'applyRequested', key: 'k2' },
    );
    expect(failed.effects.at(-1)).toEqual(expect.objectContaining({ type: 'apply', key: 'k2', revisionIds: ['a-v1', 'b-v1'] }));
  });

  it('locks the selection while saving', () => {
    const state = run(ready([summary('a', 1), summary('b', 1)]), { type: 'toggled', resource: summary('a', 1) }).state;
    const saving = run(state, { type: 'applyRequested', key: 'k1' }).state;
    expect(run(saving, { type: 'toggled', resource: summary('b', 1) }).state.selection).toBe(saving.selection);
    expect(run(saving, { type: 'registerOpened' }).state.step).toBe('list');
  });
});

describe('register (WF-14)', () => {
  const filled = (state: ResourcesState) =>
    run(
      state,
      { type: 'registerOpened' },
      { type: 'fieldChanged', field: 'name', value: ' 타사 벤치마킹 ' },
      { type: 'fieldChanged', field: 'description', value: '공통 기준' },
      { type: 'fieldChanged', field: 'instructions', value: '근거를 남깁니다.\n' },
    ).state;

  it('blocks an empty name or instructions and shows the problems', () => {
    const opened = run(ready([]), { type: 'registerOpened' }, { type: 'registerRequested', key: 'k1' });
    expect(opened.effects).toEqual([]);
    expect(opened.state.form.showProblems).toBe(true);
    expect(validateSkillForm(opened.state.form)).toEqual({ name: 'required', instructions: 'required' });
    expect(validateSkillForm({ name: '   ', description: '', instructions: 'x' })).toEqual({ name: 'required' });
    expect(validateSkillForm({ name: 'a'.repeat(101), description: '', instructions: 'x' })).toEqual({ name: 'tooLong' });
  });

  it('sends a trimmed skill body', () => {
    const { effects, state } = run(filled(ready([])), { type: 'registerRequested', key: 'k1' });
    expect(state.form.status).toBe('saving');
    expect(effects).toEqual([
      {
        type: 'create',
        projectId: P,
        key: 'k1',
        body: {
          kind: 'skill',
          name: '타사 벤치마킹',
          description: '공통 기준',
          instructions: '근거를 남깁니다.',
          content: null,
          file_name: null,
        },
      },
    ]);
  });

  it('reuses the key when the same content is retried after a failure', () => {
    const failed = run(filled(ready([])), { type: 'registerRequested', key: 'k1' }, { type: 'registerFailed', error: businessError });
    expect(failed.state.form.error).toEqual(businessError);
    expect(failed.state.form.name).toBe(' 타사 벤치마킹 ');
    expect(run(failed.state, { type: 'registerRequested', key: 'k2' }).effects[0]).toEqual(expect.objectContaining({ key: 'k1' }));
    const edited = run(failed.state, { type: 'fieldChanged', field: 'name', value: '다른 이름' }, { type: 'registerRequested', key: 'k3' });
    expect(edited.effects[0]).toEqual(expect.objectContaining({ key: 'k3' }));
  });

  it('discards the input on back', () => {
    const back = run(filled(ready([])), { type: 'backToList' }).state;
    expect(back.step).toBe('list');
    expect(back.form.name).toBe('');
  });

  it('fills fields from a loaded SKILL.md, keeping fields the file does not set', () => {
    const state = run(
      ready([]),
      { type: 'registerOpened' },
      { type: 'fieldChanged', field: 'description', value: '직접 쓴 설명' },
      { type: 'fileChosen', file: new File(['body'], 'SKILL.md') },
      { type: 'fileLoaded', seq: 2, skill: { name: 'A', description: null, instructions: 'body' } },
    ).state;
    expect([state.form.name, state.form.description, state.form.instructions]).toEqual(['A', '직접 쓴 설명', 'body']);
  });

  it('reports a rejected file and clears it on the next choice', () => {
    const rejected = run(ready([]), { type: 'registerOpened' },
      { type: 'fileChosen', file: new File(['x'], 'bad.pdf') },
      { type: 'fileRejected', seq: 2, problem: 'extension' });
    expect(rejected.state.form.fileProblem).toBe('extension');
    const file = new File(['x'], 'SKILL.md');
    const chosen = run(rejected.state, { type: 'fileChosen', file });
    expect(chosen.state.form.fileProblem).toBeNull();
    expect(chosen.effects).toEqual([{ type: 'readFile', file, seq: 3 }]);
  });

  it('only accepts the latest file and blocks submission while reading', () => {
    const reading = run(ready([]), { type: 'registerOpened' },
      { type: 'fileChosen', file: new File(['old'], 'old.md') },
      { type: 'fileChosen', file: new File(['new'], 'new.md') }).state;
    expect(run(reading, { type: 'registerRequested', key: 'k1' }).effects).toEqual([]);
    const stale = run(reading,
      { type: 'fileLoaded', seq: 2, skill: { name: 'old', description: null, instructions: 'old' } },
      { type: 'fileRejected', seq: 2, problem: 'unreadable' }).state;
    expect(stale.form.name).toBe('');
    expect(stale.form.fileProblem).toBeNull();
    expect(stale.form.status).toBe('reading');
    const loaded = run(stale, { type: 'fileLoaded', seq: 3,
      skill: { name: 'new', description: null, instructions: 'new' } }).state;
    expect(loaded.form.name).toBe('new');
    expect(loaded.form.status).toBe('editing');
  });

  it('ignores a file response from a discarded registration form', () => {
    const reading = run(ready([]), { type: 'registerOpened' },
      { type: 'fileChosen', file: new File(['old'], 'old.md') }).state;
    const reopened = run(reading, { type: 'backToList' }, { type: 'registerOpened' },
      { type: 'fieldChanged', field: 'name', value: '새 초안' }).state;
    const late = run(reopened, { type: 'fileLoaded', seq: 2,
      skill: { name: 'old', description: null, instructions: 'old' } }).state;
    expect(late.form.name).toBe('새 초안');
    expect(late.form.instructions).toBe('');
  });

  it('returns to the list with the new v1 selected and refreshes the search', () => {
    const detail: ResourceDetail = {
      id: 'new',
      kind: 'skill',
      latest_revision_id: 'new-v1',
      revisions: [],
      revision: {
        id: 'new-v1',
        resource_id: 'new',
        number: 1,
        name: '타사 벤치마킹',
        description: '',
        instructions: 'body',
        content: null,
        file_name: null,
        created_by: 'account-1',
        created_at: '2026-11-09T00:00:00Z',
      },
    };
    const saving = run(filled(ready([])), { type: 'registerRequested', key: 'k1' }).state;
    const done = run(saving, { type: 'registerSucceeded', detail });
    expect(done.state.step).toBe('list');
    expect(done.state.selection).toEqual([
      { resourceId: 'new', revisionId: 'new-v1', number: 1, name: '타사 벤치마킹', kind: 'skill' },
    ]);
    expect(done.effects).toEqual([expect.objectContaining({ type: 'search', query: '', debounce: false })]);

    const pendingApplied = run(filled(initialResourcesState(P, C)), { type: 'registerRequested', key: 'k1' },
      { type: 'registerSucceeded', detail }).state;
    const initialized = run(pendingApplied, { type: 'appliedLoaded', items: [appliedItem('existing', 1)] }).state;
    expect(initialized.selection.map(item => item.revisionId)).toEqual(['existing-v1', 'new-v1']);
  });
});

describe('server events', () => {
  const at = '2026-11-09T00:00:00Z';

  it('refreshes the search when a resource of this project changes', () => {
    const state = ready([summary('a', 1)]);
    const event = {
      type: 'resource.updated',
      data: { project_id: P, resource_id: 'a', latest_revision_id: 'a-v2', latest_number: 2, occurred_at: at },
    } as const;
    expect(run(state, { type: 'serverEvent', event }).effects).toEqual([expect.objectContaining({ type: 'search' })]);
    const other = { ...event, data: { ...event.data, project_id: 'other' } };
    expect(run(state, { type: 'serverEvent', event: other }).effects).toEqual([]);
  });

  it('reloads the applied list when this conversation changes', () => {
    const state = ready([summary('a', 1)]);
    const event = { type: 'conversation_resources.updated', data: { conversation_id: C, occurred_at: at } } as const;
    expect(run(state, { type: 'serverEvent', event }).effects).toEqual([
      expect.objectContaining({ type: 'search' }), { type: 'loadApplied', conversationId: C },
    ]);
  });

  it('reloads everything after a resync', () => {
    const effects = run(ready([summary('a', 1)]), { type: 'resynced' }).effects;
    expect(effects.map((effect) => effect.type)).toEqual(['search', 'loadApplied']);
  });
});
