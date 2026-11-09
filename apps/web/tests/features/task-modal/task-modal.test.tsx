// @vitest-environment jsdom
import { act, createElement } from 'react';
import { transferableAbortController } from 'node:util';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { components, paths } from '../../../src/api/schema';
import { TaskModal } from '../../../src/features/task-modal';
import { createApiClient } from '../../../src/lib/api';
import { ProjectEventsProvider, type EventSourceLike } from '../../../src/lib/realtime';
import { conversation, date, me, message, task } from './fixtures';
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
class Source implements EventSourceLike {
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  listeners = new Map<string, ((event: MessageEvent<string>) => void)[]>();
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) { this.listeners.set(type, [...this.listeners.get(type) ?? [], listener]); }
  close() {}
  emit(type: string, data: unknown) { for (const listener of this.listeners.get(type) ?? []) listener(new MessageEvent(type, { data: JSON.stringify(data) })); }
}
let root: Root;
let container: HTMLElement;
let source: Source;
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
beforeEach(() => {
  vi.stubGlobal('AbortController', class { constructor() { return transferableAbortController(); } });
  HTMLDialogElement.prototype.showModal = vi.fn(function(this: HTMLDialogElement) { this.setAttribute('open', ''); });
  HTMLDialogElement.prototype.close = vi.fn(function(this: HTMLDialogElement) { this.removeAttribute('open'); });
  container = document.createElement('div'); document.body.append(container); root = createRoot(container); source = new Source();
});
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals(); });
const button = (text: string) => [...container.querySelectorAll('button')].find(node => node.textContent === text)!;
const draft = () => container.querySelector('textarea')!;
async function type(value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(draft(), value);
    draft().dispatchEvent(new Event('input', { bubbles: true }));
  });
}
async function renderModal(options: { task?: components['schemas']['Task']; viewer?: boolean; post?: (request: Request) => Promise<Response>; onClose?: () => void } = {}) {
  const fetch = vi.fn<typeof globalThis.fetch>(async input => {
    const request = input as Request;
    if (request.method === 'POST') return options.post?.(request) ?? json({ message: message(2), run: null });
    if (request.url.endsWith('/api/me')) return json(options.viewer ? { ...me, account: { ...me.account, id: 'viewer' } } : me);
    if (request.url.endsWith('/api/tasks/task-1')) return json(options.task ?? task);
    if (request.url.endsWith('/api/conversations/child-1')) return json(conversation);
    return json({ items: [message(1, { body: '자식 작업에서만 작성한 메시지' })], next_after_seq: null });
  });
  const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch });
  await act(async () => root.render(createElement(ProjectEventsProvider, { projectId: 'project-1', onUnauthorized: vi.fn(), connectionOptions: { createEventSource: () => source } }, createElement(TaskModal, {
    taskId: task.id, onClose: options.onClose ?? vi.fn(), client,
    renderHeaderActions: () => createElement('button', { type: 'button' }, '결과 정리'),
    renderResultTab: () => createElement('p', null, '결과 탭 내용'),
  }))));
  return fetch;
}

describe('TaskModal', () => {
  it('shows only the child messages and keeps the draft when changing tabs', async () => {
    const fetch = await renderModal();
    expect(container.textContent).toContain('자식 작업에서만 작성한 메시지');
    expect(container.textContent).toContain(task.goal);
    expect(button('결과 정리')).toBeDefined();
    await type('작업 초안');
    await act(async () => button('결과').click());
    expect(container.querySelector('[role="tabpanel"]:not([hidden])')?.textContent).toContain('결과 탭 내용');
    await act(async () => button('대화').click());
    expect(draft().value).toBe('작업 초안');
    expect(fetch.mock.calls.some(([request]) => (request as Request).method === 'POST')).toBe(false);
  });
  it('closes a running task without a cancel request and offers cancellation only to the requester', async () => {
    const onClose = vi.fn();
    const fetch = await renderModal({ task: { ...task, status: 'running' }, onClose });
    expect(button('작업 중단')).toBeDefined();
    expect(button('결과 정리')).toBeUndefined();
    await act(async () => button('닫기').click());
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls.every(([request]) => (request as Request).method === 'GET')).toBe(true);
  });
  it('keeps read-only participants from stopping a task and leaves plain discussion enabled', async () => {
    await renderModal({ task: { ...task, status: 'running' }, viewer: true });
    expect(button('작업 중단')).toBeUndefined();
    await type('@AI 보완해줘');
    expect(button('전송').disabled).toBe(true);
    await type('사람끼리 논의를 계속합니다.');
    expect(button('전송').disabled).toBe(false);
  });
  it('retains the draft after a business conflict and submits to the child', async () => {
    const post = vi.fn(async (_request: Request) => json({ error: { code: 'ACTIVE_RUN_EXISTS', message: '다른 요청이 진행 중입니다.', details: null } }, 409));
    await renderModal({ post });
    await type('@AI 정책도 비교해줘');
    await act(async () => button('전송').click());
    expect(post).toHaveBeenCalledTimes(1);
    expect(post.mock.calls[0][0].url).toContain('/child-1/messages');
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('다른 요청이 진행 중입니다.');
    expect(draft().value).toBe('@AI 정책도 비교해줘');
  });
  it('updates child messages on a relevant SSE event and re-reads on reconnect', async () => {
    const fetch = await renderModal();
    const before = fetch.mock.calls.length;
    await act(async () => source.emit('message.created', { conversation_id: 'parent-1', message_id: 'other', seq: 2, occurred_at: date }));
    expect(fetch.mock.calls).toHaveLength(before);
    await act(async () => source.emit('message.created', { conversation_id: 'child-1', message_id: 'm2', seq: 2, occurred_at: date }));
    expect(fetch.mock.calls.length).toBeGreaterThan(before);
    const after = fetch.mock.calls.length;
    await act(async () => source.onopen?.(new Event('open')));
    expect(fetch.mock.calls.length).toBeGreaterThan(after);
  });
  it('sends an empty JSON body with an idempotency key only after an explicit stop click', async () => {
    const post = vi.fn(async (_request: Request) => json({ ...task, status: 'cancelled' }));
    await renderModal({ task: { ...task, status: 'running' }, post });
    await act(async () => button('작업 중단').click());
    const request = post.mock.calls[0][0];
    expect(request.url).toContain('/api/tasks/task-1/cancel');
    expect(await request.json()).toEqual({});
    expect(request.headers.get('Idempotency-Key')).toBeTruthy();
  });
});
