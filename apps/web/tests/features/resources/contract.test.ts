import { describe, expect, it, vi } from 'vitest';
import {
  parseAppliedResourceList, parseResourceDetail, parseResourceSummaryList, ResourceDecodeError,
} from '../../../src/features/resources/contract';
import { makeResourcesEffectHandler } from '../../../src/features/resources/effects';
import {
  initialResourcesState, type AppliedResource, type ResourceDetail, type ResourceSummary,
  type ResourcesEffect, type ResourcesIntent, type ResourcesState,
} from '../../../src/features/resources/model';
import { resourcesReducer } from '../../../src/features/resources/reducer';
import { errorMessage, SYSTEM_ERROR_MESSAGE, type AppApi } from '../../../src/lib/api';

const summary: ResourceSummary = {
  id: 'resource-a', kind: 'skill',
  latest: { revision_id: 'a-v2', number: 2, name: '공통 기준', description: '업무 기준' },
  applied: { revision_id: 'a-v1', number: 1 },
};
const applied: AppliedResource = {
  resource_id: 'resource-a', revision_id: 'a-v1', number: 1, name: '공통 기준', kind: 'skill',
};
const detail: ResourceDetail = {
  id: 'resource-a', kind: 'skill', latest_revision_id: 'a-v2',
  revision: {
    id: 'a-v2', resource_id: 'resource-a', number: 2, name: '공통 기준', description: '업무 기준',
    instructions: '근거를 남긴다.', content: null, file_name: null,
    created_by: 'account-a', created_at: '2026-11-09T00:00:00Z',
  },
  revisions: [{ id: 'a-v2', number: 2, name: '공통 기준', created_by: 'account-a', created_at: '2026-11-09T00:00:00Z' }],
};

describe('resource API boundary schemas', () => {
  it('accepts generated-contract lists and nested details including nullable fields', () => {
    expect(parseResourceSummaryList({ items: [summary] })).toEqual({ items: [summary] });
    expect(parseAppliedResourceList({ items: [applied] })).toEqual({ items: [applied] });
    expect(parseResourceDetail(detail)).toEqual(detail);
    expect(parseResourceSummaryList({ items: [{ ...summary, applied: null }] }).items[0]?.applied).toBeNull();
    expect(parseResourceDetail({ ...detail, kind: 'file', revision: {
      ...detail.revision, instructions: null, content: '첨부 내용', file_name: 'guide.md',
    } }).revision.content).toBe('첨부 내용');
  });

  it.each([undefined, null, [], { items: null }, { items: {} }, { items: [null] }])(
    'rejects a malformed resource list: %j', value => {
      expect(() => parseResourceSummaryList(value)).toThrow(ResourceDecodeError);
      expect(() => parseAppliedResourceList(value)).toThrow(ResourceDecodeError);
    },
  );

  it.each([0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1, '1'])(
    'rejects a nonpositive or unsafe revision number: %s', number => {
      expect(() => parseResourceSummaryList({ items: [{ ...summary, latest: { ...summary.latest, number } }] }))
        .toThrow(ResourceDecodeError);
      expect(() => parseAppliedResourceList({ items: [{ ...applied, number }] })).toThrow(ResourceDecodeError);
      expect(() => parseResourceDetail({ ...detail, revision: { ...detail.revision, number } }))
        .toThrow(ResourceDecodeError);
    },
  );

  it('rejects unknown kinds, missing required nullable fields and malformed nested revisions', () => {
    expect(() => parseResourceSummaryList({ items: [{ ...summary, kind: 'pdf' }] })).toThrow(ResourceDecodeError);
    expect(() => parseAppliedResourceList({ items: [{ ...applied, kind: null }] })).toThrow(ResourceDecodeError);
    expect(() => parseResourceDetail({ ...detail, kind: 'unknown' })).toThrow(ResourceDecodeError);
    expect(() => parseResourceSummaryList({ items: [{ ...summary, applied: undefined }] })).toThrow(ResourceDecodeError);
    expect(() => parseResourceSummaryList({ items: [{ ...summary, applied: { revision_id: 'a-v1' } }] }))
      .toThrow(ResourceDecodeError);
    expect(() => parseResourceDetail({ ...detail, revision: { ...detail.revision, content: undefined } }))
      .toThrow(ResourceDecodeError);
    expect(() => parseResourceDetail({ ...detail, revisions: [{ ...detail.revisions[0], created_by: null }] }))
      .toThrow(ResourceDecodeError);
    expect(() => parseResourceDetail({ ...detail, revision: [] })).toThrow(ResourceDecodeError);
  });
});

function fakeApi(body: unknown, status = 200): AppApi {
  const reply = async () => {
    const response = new Response(null, { status });
    return response.ok ? { data: body, response } : { error: body, response };
  };
  return { GET: reply, PUT: reply, POST: reply } as unknown as AppApi;
}

async function execute(effect: ResourcesEffect, body: unknown, initial = initialResourcesState('project-a', 'conversation-a'), status = 200) {
  let state = initial;
  const intents: ResourcesIntent[] = [];
  const effects: ResourcesEffect[] = [];
  const close = vi.fn();
  const handler = makeResourcesEffectHandler({ api: fakeApi(body, status), close, delay: async () => {} });
  await handler(effect, intent => {
    intents.push(intent);
    const result = resourcesReducer(state, intent);
    state = result.state;
    effects.push(...result.effects);
  }, new AbortController().signal);
  return { state, intents, effects, close };
}

describe('resource effect response validation', () => {
  it('reports a malformed search response as a system failure without rendering invalid data', async () => {
    const start = resourcesReducer(initialResourcesState('project-a', 'conversation-a'), { type: 'opened' });
    const outcome = await execute(start.effects[0]!, { items: [{ ...summary, latest: null }] }, start.state);
    expect(outcome.intents).toEqual([{
      type: 'searchFailed', seq: start.state.searchSeq,
      error: { kind: 'system', status: 502, code: null, message: null, details: null },
    }]);
    expect(outcome.state.search.status).toBe('failed');
    if (outcome.state.search.status === 'failed') {
      expect(errorMessage(outcome.state.search.error)).toBe(SYSTEM_ERROR_MESSAGE);
    }
  });

  it('reports a malformed applied list rather than changing the pinned selection', async () => {
    const initial: ResourcesState = { ...initialResourcesState('project-a', 'conversation-a'), selection: [
      { resourceId: applied.resource_id, revisionId: applied.revision_id, name: applied.name, number: 1, kind: 'skill' },
    ] };
    const outcome = await execute({ type: 'loadApplied', conversationId: 'conversation-a' }, { items: [{ ...applied, kind: 'unknown' }] }, initial);
    expect(outcome.intents[0]?.type).toBe('appliedFailed');
    expect(outcome.state.applied.status).toBe('failed');
    expect(outcome.state.selection).toEqual(initial.selection);
  });

  it('keeps search and selection on malformed apply success and never closes the modal', async () => {
    const initial: ResourcesState = {
      ...initialResourcesState('project-a', 'conversation-a'), query: '공통',
      search: { status: 'ready', data: [summary] }, applied: { status: 'ready', data: [] },
      selection: [{ resourceId: applied.resource_id, revisionId: applied.revision_id, name: applied.name, number: 1, kind: 'skill' }],
      selectionTouched: true, apply: { status: 'saving', error: null, lastAttempt: { key: 'apply-key', revisionIds: ['a-v1'] } },
    };
    const outcome = await execute({ type: 'apply', conversationId: 'conversation-a', revisionIds: ['a-v1'], key: 'apply-key' }, { items: {} }, initial);
    expect(outcome.intents[0]?.type).toBe('applyFailed');
    expect(outcome.state.query).toBe('공통');
    expect(outcome.state.selection).toEqual(initial.selection);
    expect(outcome.state.apply).toMatchObject({ status: 'idle', error: { kind: 'system', status: 502 } });
    expect(outcome.effects).toEqual([]);
    expect(outcome.close).not.toHaveBeenCalled();
  });

  it('keeps the registration draft when a successful HTTP response contains an invalid nested revision', async () => {
    const initial: ResourcesState = {
      ...initialResourcesState('project-a', 'conversation-a'), step: 'register',
      form: {
        ...initialResourcesState('project-a', 'conversation-a').form,
        name: '작성 중 기준', description: '입력 설명', instructions: '입력 지침', status: 'saving',
      },
    };
    const outcome = await execute({ type: 'create', projectId: 'project-a', key: 'register-key', body: {
      kind: 'skill', name: initial.form.name, description: initial.form.description, instructions: initial.form.instructions,
    } }, { ...detail, revision: { ...detail.revision, number: 0 } }, initial);
    expect(outcome.intents[0]?.type).toBe('registerFailed');
    expect(outcome.state.step).toBe('register');
    expect(outcome.state.form).toMatchObject({
      name: '작성 중 기준', description: '입력 설명', instructions: '입력 지침', status: 'editing', error: { kind: 'system', status: 502 },
    });
    expect(outcome.effects).toEqual([]);
    expect(outcome.close).not.toHaveBeenCalled();
  });

  it('preserves an HTTP business failure instead of masking it as a decode failure', async () => {
    const outcome = await execute({ type: 'apply', conversationId: 'conversation-a', revisionIds: ['a-v1'], key: 'key' },
      { error: { code: 'FORBIDDEN', message: '접근 권한이 없습니다.', details: null } }, undefined, 403);
    expect(outcome.intents).toEqual([{
      type: 'applyFailed', error: { kind: 'business', status: 403, code: 'FORBIDDEN', message: '접근 권한이 없습니다.', details: null },
    }]);
  });
});
