// @vitest-environment jsdom
import { act, createElement } from 'react';
import { transferableAbortController } from 'node:util';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { paths } from '../../../src/api/schema';
import { TaskQueue } from '../../../src/features/task-queue';
import { createApiClient, SYSTEM_ERROR_MESSAGE } from '../../../src/lib/api';
import { ProjectEventsProvider, type EventSourceLike, type ProjectEventsConnectionOptions } from '../../../src/lib/realtime';
import { task, taskEvent } from './fixtures';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

class FakeEventSource implements EventSourceLike {
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  private listeners = new Map<string, ((event: MessageEvent<string>) => void)[]>();
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  close() {}
  emit(data: unknown) {
    for (const listener of this.listeners.get('task.updated') ?? []) {
      listener(new MessageEvent('task.updated', { data: JSON.stringify(data) }));
    }
  }
}

let container: HTMLElement;
let root: Root;
let source: FakeEventSource;
let options: ProjectEventsConnectionOptions;
let retry: (() => void) | undefined;
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

beforeEach(() => {
  // jsdom's AbortSignal belongs to a different realm than Node's native fetch/Request.
  vi.stubGlobal('AbortController', class {
    constructor() { return transferableAbortController(); }
  });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  retry = undefined;
  options = {
    createEventSource: () => { source = new FakeEventSource(); return source; },
    checkSession: async () => false,
    timers: { setTimeout: (callback) => { retry = callback; return 1; }, clearTimeout: () => { retry = undefined; } },
  };
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
});

async function renderQueue(fetch: typeof globalThis.fetch, onOpenTask = vi.fn()) {
  const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch });
  await act(async () => {
    root.render(createElement(
      ProjectEventsProvider,
      { projectId: 'project-1', onUnauthorized: vi.fn(), connectionOptions: options },
      createElement(TaskQueue, { conversationId: 'parent-1', onOpenTask, client }),
    ));
  });
  return onOpenTask;
}

describe('TaskQueue with the generated API client and shared SSE provider', () => {
  it('supports cancellable generated API reads in the browser test environment', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => json({ items: [task()] }));
    const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch });
    const response = await client.GET('/api/conversations/{conversation_id}/tasks', {
      params: { path: { conversation_id: 'parent-1' } }, signal: new AbortController().signal,
    });
    expect(response.data?.items).toHaveLength(1);
  });
  it('updates ready status silently and opens only the clicked row without navigating', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => json({ items: [task()] }));
    const open = await renderQueue(fetch);
    expect(container.textContent).toContain('경쟁사 비교');
    expect(container.textContent).toContain('대기 중');
    expect(fetch.mock.calls[0][0]).toBeInstanceOf(Request);
    expect((fetch.mock.calls[0][0] as Request).url).toBe('http://localhost/api/conversations/parent-1/tasks');
    act(() => source.emit(taskEvent({ status: 'ready' }).data));
    expect(container.textContent).toContain('준비됨');
    expect(open).not.toHaveBeenCalled();
    const path = window.location.pathname;
    act(() => (container.querySelector('li button') as HTMLButtonElement).click());
    expect(open).toHaveBeenCalledExactlyOnceWith('task-1');
    expect(window.location.pathname).toBe(path);
  });

  it('ignores another conversation and reloads on every SSE connection opening', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => json({ items: [task()] }));
    await renderQueue(fetch);
    act(() => source.emit(taskEvent({ title: '다른 대화의 작업', source_conversation_id: 'parent-2' }).data));
    expect(container.textContent).not.toContain('다른 대화의 작업');
    expect(fetch).toHaveBeenCalledTimes(1);
    await act(async () => source.onopen?.(new Event('open')));
    await act(async () => source.onerror?.(new Event('error')));
    act(() => retry?.());
    await act(async () => source.onopen?.(new Event('open')));
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it('shows recoverable API errors and can reload an empty queue', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(json({ error: { code: 'NOT_IMPLEMENTED', message: '아직 준비 중입니다.', details: null } }, 501))
      .mockResolvedValueOnce(json({ items: [] }));
    await renderQueue(fetch);
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(SYSTEM_ERROR_MESSAGE);
    await act(async () => (container.querySelector('button') as HTMLButtonElement).click());
    expect(container.textContent).toContain('아직 작업이 없습니다.');
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  it('rejects an invalid success payload rather than rendering unvalidated task data', async () => {
    await renderQueue(async () => json({ items: [{ id: 'invalid', title: 'invalid payload', status: 'ready' }] }));
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(SYSTEM_ERROR_MESSAGE);
    expect(container.textContent).not.toContain('invalid payload');
  });

  it('does not regress an SSE ready update when a pending GET completes later', async () => {
    let resolve!: (response: Response) => void;
    await renderQueue(() => new Promise<Response>((done) => { resolve = done; }));
    expect(container.textContent).toContain('작업을 불러오는 중입니다.');
    act(() => source.emit(taskEvent({ status: 'ready' }).data));
    await act(async () => resolve(json({ items: [task()] })));
    expect(container.textContent).toContain('준비됨');
    expect(container.textContent).not.toContain('대기 중');
  });
});
