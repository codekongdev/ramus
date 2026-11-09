// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ResourcesModal } from '../../../src/features/resources';
import { IDEMPOTENCY_HEADER, type AppApi } from '../../../src/lib/api';
import { ProjectEventsProvider, type EventSourceLike, type ProjectEventsConnectionOptions } from '../../../src/lib/realtime';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const P = '11111111-1111-4111-8111-111111111111';
const C = '22222222-2222-4222-8222-222222222222';

type Call = {
  readonly method: 'GET' | 'PUT' | 'POST';
  readonly path: string;
  readonly params: { path?: Record<string, string>; query?: Record<string, string> };
  readonly body: unknown;
  readonly key: string | null;
};
type Reply = { status: number; body: unknown };
type Handler = (call: Call) => Reply | Promise<Reply>;

const json = (status: number, body: unknown): Reply => ({ status, body });

const skill = (id: string, name: string, latest: number, applied: number | null) => ({
  id,
  kind: 'skill',
  latest: { revision_id: `${id}-v${latest}`, number: latest, name, description: `${name} 설명` },
  applied: applied === null ? null : { revision_id: `${id}-v${applied}`, number: applied },
});

let container: HTMLElement;
let root: Root;
let requests: Call[];
let source: FakeEventSource;
let retry: (() => void) | undefined;
let connectionOptions: ProjectEventsConnectionOptions;

class FakeEventSource implements EventSourceLike {
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  private listeners = new Map<string, ((event: MessageEvent<string>) => void)[]>();

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close() {}

  emit(type: string, data: Record<string, unknown>) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: JSON.stringify({ ...data, occurred_at: '2026-11-09T00:00:00Z' }) }));
    }
  }
}

/**
 * Stand-in for the openapi-fetch client (covered by tests/lib/api-client.test.ts). jsdom's
 * AbortSignal is rejected by Node's Request, so the real client cannot run in this environment.
 */
function fakeApi(handler: Handler): AppApi {
  const call = (method: Call['method']) => async (path: string, init: Record<string, unknown> = {}) => {
    const headers = (init.headers ?? {}) as Record<string, string>;
    const entry: Call = {
      method,
      path,
      params: (init.params ?? {}) as Call['params'],
      body: init.body ?? null,
      key: headers[IDEMPOTENCY_HEADER] ?? null,
    };
    requests.push(entry);
    const reply = await handler(entry);
    const response = new Response(null, { status: reply.status });
    return reply.status < 400 ? { data: reply.body, response } : { error: reply.body, response };
  };
  return { GET: call('GET'), PUT: call('PUT'), POST: call('POST') } as unknown as AppApi;
}

const readBytes = (file: File) =>
  new Promise<Uint8Array>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(file);
  });

function setup(handler: Handler, conversationId: string | null = C) {
  requests = [];
  const onClose = vi.fn();
  act(() => {
    root.render(
      createElement(
        ProjectEventsProvider,
        { projectId: P, onUnauthorized: vi.fn(), connectionOptions },
        createElement(ResourcesModal, {
          projectId: P,
          conversationId,
          onClose,
          api: fakeApi(handler),
          delay: async () => {},
          readBytes,
        }),
      ),
    );
  });
  return { onClose };
}

const settle = () => act(async () => {
  for (let i = 0; i < 5; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));
});

const text = () => container.textContent ?? '';
const button = (label: string) => {
  const found = [...container.querySelectorAll('button')].find((b) => b.textContent?.trim() === label);
  if (!found) throw new Error(`button "${label}" not found`);
  return found;
};
const click = (element: Element) => act(() => (element as HTMLElement).click());
const typeInto = (element: HTMLInputElement | HTMLTextAreaElement, value: string) =>
  act(() => {
    const proto = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(element, value);
    element.dispatchEvent(new Event('input', { bubbles: true }));
  });

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute('open', '');
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute('open');
  });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  retry = undefined;
  connectionOptions = {
    createEventSource: () => { source = new FakeEventSource(); return source; },
    checkSession: async () => false,
    timers: { setTimeout: (callback) => { retry = callback; return 1; }, clearTimeout: () => { retry = undefined; } },
  };
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

describe('ResourcesModal · WF-10', () => {
  const routes: Handler = (request) => {
    if (request.path === '/api/projects/{project_id}/resources' && request.method === 'GET') {
      return json(200, { items: [skill('a', '타사 벤치마킹', 2, 1), skill('b', '기능 벤치마킹', 1, null)] });
    }
    if (request.path === '/api/conversations/{conversation_id}/resources' && request.method === 'GET') {
      return json(200, { items: [{ resource_id: 'a', revision_id: 'a-v1', number: 1, name: '타사 벤치마킹', kind: 'skill' }] });
    }
    if (request.path === '/api/conversations/{conversation_id}/resources' && request.method === 'PUT') {
      return json(200, { items: [] });
    }
    return json(404, { error: { code: 'NOT_FOUND', message: '없음', details: null } });
  };

  it('shows latest and applied versions, and the applied version as a chip', async () => {
    setup(routes);
    await settle();
    expect(requests.map((r) => [r.method, r.path, r.params])).toEqual([
      ['GET', '/api/projects/{project_id}/resources', { path: { project_id: P }, query: { conversation_id: C } }],
      ['GET', '/api/conversations/{conversation_id}/resources', { path: { conversation_id: C } }],
    ]);
    expect(text()).toContain('최신 v2 · 현재 적용 v1');
    expect(container.querySelector('[aria-label="선택한 스킬·자료"]')?.textContent).toContain('타사 벤치마킹 · v1');
    expect(button('적용').disabled).toBe(true);
  });

  it('applies the chosen exact versions with an idempotency key and closes', async () => {
    const { onClose } = setup(routes);
    await settle();
    await click(button('최신 v2로 바꾸기'));
    await click(container.querySelector('input[aria-label="기능 벤치마킹 선택"]')!);
    expect(container.querySelector('[aria-label="선택한 스킬·자료"]')?.textContent).toContain('타사 벤치마킹 · v2');
    await click(button('적용'));
    await settle();
    const put = requests.find((r) => r.method === 'PUT')!;
    expect(put.params.path).toEqual({ conversation_id: C });
    expect(put.body).toEqual({ revision_ids: ['a-v2', 'b-v1'] });
    expect(put.key).toBeTruthy();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('keeps the query and selection when apply fails, and retries with the same key', async () => {
    let attempts = 0;
    setup((request) => {
      if (request.method === 'PUT') {
        attempts += 1;
        return json(422, { error: { code: 'INVALID_INPUT', message: '적용할 수 없는 버전입니다.', details: null } });
      }
      return routes(request);
    });
    await settle();
    await typeInto(container.querySelector<HTMLInputElement>('input[type="search"]')!, '벤치');
    await settle();
    await click(container.querySelector('input[aria-label="기능 벤치마킹 선택"]')!);
    await click(button('적용'));
    await settle();
    expect(text()).toContain('적용할 수 없는 버전입니다.');
    expect(container.querySelector<HTMLInputElement>('input[type="search"]')!.value).toBe('벤치');
    expect(container.querySelector('[aria-label="선택한 스킬·자료"]')?.textContent).toContain('기능 벤치마킹 · v1');

    await click(button('적용'));
    await settle();
    const keys = requests.filter((r) => r.method === 'PUT').map((r) => r.key);
    expect(attempts).toBe(2);
    expect(keys[0]).toBe(keys[1]);
  });

  it('shows the server message when the endpoint is not ready', async () => {
    setup(() => json(501, { error: { code: 'NOT_IMPLEMENTED', message: '아직 준비되지 않았습니다.', details: null } }));
    await settle();
    expect(text()).toContain('요청을 처리하는 중에 문제가 생겼습니다');
    expect(button('다시 시도')).toBeTruthy();
  });

  it('without a conversation, lists resources but offers no apply', async () => {
    setup(routes, null);
    await settle();
    expect(requests).toHaveLength(1);
    expect(text()).toContain('대화를 열면');
    expect(container.querySelector('input[type="checkbox"]')).toBeNull();
    expect([...container.querySelectorAll('button')].some((b) => b.textContent === '적용')).toBe(false);
  });

  it('waits for applied versions before editing so adding a skill keeps the existing selection', async () => {
    let resolveApplied!: (reply: Reply) => void;
    setup((request) => request.method === 'GET' && request.path.startsWith('/api/conversations/')
      ? new Promise<Reply>((resolve) => { resolveApplied = resolve; })
      : routes(request));
    await settle();
    const checkbox = container.querySelector<HTMLInputElement>('input[aria-label="기능 벤치마킹 선택"]')!;
    expect(checkbox.disabled).toBe(true);
    await click(checkbox);
    expect(button('적용').disabled).toBe(true);

    await act(async () => resolveApplied(json(200, {
      items: [{ resource_id: 'a', revision_id: 'a-v1', number: 1, name: '타사 벤치마킹', kind: 'skill' }],
    })));
    await settle();
    expect(checkbox.disabled).toBe(false);
    await click(checkbox);
    await click(button('적용'));
    await settle();
    expect(requests.find((request) => request.method === 'PUT')?.body).toEqual({ revision_ids: ['a-v1', 'b-v1'] });
  });

  it('refreshes a changed resource through the shared project event connection without changing its pinned version', async () => {
    let latest = 2;
    setup((request) => request.method === 'GET' && request.path.startsWith('/api/projects/')
      ? json(200, { items: [skill('a', '타사 벤치마킹', latest, 1)] })
      : routes(request));
    await settle();
    latest = 3;
    act(() => source.emit('resource.updated', {
      project_id: P, resource_id: 'a', latest_revision_id: 'a-v3', latest_number: 3,
    }));
    await settle();
    expect(text()).toContain('최신 v3 · 현재 적용 v1');
    expect(container.querySelector('[aria-label="선택한 스킬·자료"]')?.textContent).toContain('타사 벤치마킹 · v1');
    expect(button('적용').disabled).toBe(true);
  });

  it('refreshes both applied chips and version labels after another user changes the conversation', async () => {
    let applied: number | null = null;
    setup((request) => {
      if (request.method === 'GET' && request.path.startsWith('/api/projects/')) {
        return json(200, { items: [skill('a', '타사 벤치마킹', 2, applied)] });
      }
      if (request.method === 'GET' && request.path.startsWith('/api/conversations/')) {
        return json(200, { items: applied === null ? [] : [
          { resource_id: 'a', revision_id: `a-v${applied}`, number: applied, name: '타사 벤치마킹', kind: 'skill' },
        ] });
      }
      return routes(request);
    });
    await settle();
    expect(container.querySelector('[aria-label="선택한 스킬·자료"]')).toBeNull();
    applied = 1;
    act(() => source.emit('conversation_resources.updated', { conversation_id: C }));
    await settle();
    expect(container.querySelector('[aria-label="선택한 스킬·자료"]')?.textContent).toContain('타사 벤치마킹 · v1');
    expect(text()).toContain('최신 v2 · 현재 적용 v1');
    expect(button('적용').disabled).toBe(true);
  });

  it('resyncs after reconnect while preserving the search, selection and registration draft', async () => {
    setup(routes);
    await settle();
    act(() => source.onopen?.(new Event('open')));
    await settle();
    await typeInto(container.querySelector<HTMLInputElement>('input[type="search"]')!, '벤치');
    await settle();
    await click(container.querySelector('input[aria-label="기능 벤치마킹 선택"]')!);
    await click(button('스킬 등록'));
    await typeInto(container.querySelector<HTMLInputElement>('.h-field input')!, '작성 중인 스킬');
    await typeInto(container.querySelector<HTMLTextAreaElement>('textarea')!, '저장 전 지침');
    const beforeReconnect = requests.filter((request) => request.method === 'GET').length;

    act(() => source.onerror?.(new Event('error')));
    await settle();
    expect(retry).toBeTypeOf('function');
    act(() => retry?.());
    act(() => source.onopen?.(new Event('open')));
    await settle();

    expect(requests.filter((request) => request.method === 'GET').length).toBe(beforeReconnect + 2);
    expect(container.querySelector<HTMLInputElement>('.h-field input')!.value).toBe('작성 중인 스킬');
    expect(container.querySelector<HTMLTextAreaElement>('textarea')!.value).toBe('저장 전 지침');
    expect(requests.some((request) => request.method === 'POST' || request.method === 'PUT')).toBe(false);
    await click(button('← 목록'));
    expect(container.querySelector<HTMLInputElement>('input[type="search"]')!.value).toBe('벤치');
    const chips = container.querySelector('[aria-label="선택한 스킬·자료"]')?.textContent;
    expect(chips).toContain('타사 벤치마킹 · v1');
    expect(chips).toContain('기능 벤치마킹 · v1');
  });
});

describe('ResourcesModal · WF-14', () => {
  it('blocks empty input, loads SKILL.md, registers and returns to the list with v1 selected', async () => {
    let listed = [] as unknown[];
    setup((request) => {
      if (request.method === 'POST') {
        listed = [skill('new', '타사 벤치마킹', 1, null)];
        return json(201, {
          id: 'new',
          kind: 'skill',
          latest_revision_id: 'new-v1',
          revisions: [],
          revision: {
            id: 'new-v1',
            resource_id: 'new',
            number: 1,
            name: '타사 벤치마킹',
            description: '공통 기준',
            instructions: '근거를 남깁니다.',
            content: null,
            file_name: null,
            created_by: 'acc',
            created_at: '2026-11-09T00:00:00Z',
          },
        });
      }
      if (request.path.startsWith('/api/conversations/')) return json(200, { items: [] });
      return json(200, { items: listed });
    });
    await settle();
    expect(text()).toContain('등록된 스킬·자료가 없습니다');

    await click(button('스킬 등록'));
    await click(button('등록'));
    expect(text()).toContain('이름을 입력하세요.');
    expect(text()).toContain('지침을 입력하세요.');
    expect(requests.some((r) => r.method === 'POST')).toBe(false);

    const fileInput = container.querySelector<HTMLInputElement>('[data-testid="skill-file-input"]')!;
    const file = new File(['---\nname: 타사 벤치마킹\ndescription: 공통 기준\n---\n근거를 남깁니다.\n'], 'SKILL.md');
    await act(async () => {
      Object.defineProperty(fileInput, 'files', { value: [file], configurable: true });
      fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await settle();
    const inputs = container.querySelectorAll<HTMLInputElement>('.h-field input');
    expect([...inputs].map((input) => input.value)).toEqual(['타사 벤치마킹', '공통 기준']);
    expect(container.querySelector('textarea')!.value).toBe('근거를 남깁니다.');

    await click(button('등록'));
    await settle();
    const post = requests.find((r) => r.method === 'POST')!;
    expect(post.params.path).toEqual({ project_id: P });
    expect(post.body).toEqual({
      kind: 'skill',
      name: '타사 벤치마킹',
      description: '공통 기준',
      instructions: '근거를 남깁니다.',
      content: null,
      file_name: null,
    });
    expect(post.key).toBeTruthy();
    expect(container.querySelector('[data-step="list"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="선택한 스킬·자료"]')?.textContent).toContain('타사 벤치마킹 · v1');
    expect(button('적용').disabled).toBe(false);
  });

  it('reports an unsupported file instead of dropping it silently', async () => {
    setup(() => json(200, { items: [] }));
    await settle();
    await click(button('스킬 등록'));
    const fileInput = container.querySelector<HTMLInputElement>('[data-testid="skill-file-input"]')!;
    await act(async () => {
      Object.defineProperty(fileInput, 'files', { value: [new File(['x'], 'skill.pdf')], configurable: true });
      fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await settle();
    expect(text()).toContain('.md 또는 .txt 파일만 불러올 수 있습니다.');
  });

  it('back discards the input', async () => {
    setup(() => json(200, { items: [] }));
    await settle();
    await click(button('스킬 등록'));
    await typeInto(container.querySelector<HTMLInputElement>('.h-field input')!, '임시');
    await click(button('← 목록'));
    await click(button('스킬 등록'));
    expect(container.querySelector<HTMLInputElement>('.h-field input')!.value).toBe('');
    expect(requests.some((r) => r.method === 'POST')).toBe(false);
  });
});
