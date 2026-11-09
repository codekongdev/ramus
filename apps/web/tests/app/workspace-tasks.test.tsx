// @vitest-environment jsdom
import { act, createElement, useEffect } from 'react';
import { transferableAbortController } from 'node:util';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AuthProvider } from '../../src/features/auth/AuthProvider';
import { WorkspacePage } from '../../src/app/pages/WorkspacePage';
import { ModalHostProvider } from '../../src/app/modal/ModalHost';
import { ProjectEventsProvider, type EventSourceLike } from '../../src/lib/realtime';
import { task, conversation, parent, message, me } from '../fixtures/tasks';
const { fakeFetch } = vi.hoisted(() => ({ fakeFetch: vi.fn<typeof globalThis.fetch>() }));
vi.mock('../../src/lib/api/app', async () => {
  const { createApiClient } = await import('../../src/lib/api/client');
  return { api: createApiClient({ baseUrl: 'http://localhost', fetch: fakeFetch }) };
});
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
class Source implements EventSourceLike {
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  addEventListener() {}
  close() {}
}
let root: Root;
let container: HTMLElement;
beforeEach(() => {
  vi.stubGlobal('AbortController', class { constructor() { return transferableAbortController(); } });
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
  fakeFetch.mockImplementation(async input => {
    const path = new URL((input as Request).url).pathname;
    const data = path === '/api/me' ? me : path === '/api/projects' ? { items: [{ id: 'p1', name: '공동 샘플', is_shared_sample: true }] }
      : path === '/api/projects/p1/participants' ? { items: [me.account] } : path === '/api/tasks/t1' ? task
      : path === '/api/projects/p1/conversations' ? { items: [parent, conversation] }
      : path === '/api/conversations/c1/tasks' ? { items: [task] }
      : path === '/api/conversations/child1' ? conversation : { items: [message], next_after_seq: null };
    return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
  });
  window.history.replaceState(null, '', '/projects/p1/conversations/c1');
  container = document.createElement('div'); document.body.append(container); root = createRoot(container);
});
afterEach(() => { act(() => root.unmount()); container.remove(); vi.unstubAllGlobals(); fakeFetch.mockReset(); });

it('keeps the same parent message panel, draft, scroll and route across queue/tree task modal visits', async () => {
  let mounts = 0;
  function ParentConversation() {
    useEffect(() => { mounts += 1; }, []);
    return createElement('div', { id: 'parent-messages', style: { overflow: 'auto', height: 100 } },
      createElement('div', { style: { height: 1000 } }, '부모 논의'),
      createElement('textarea', { defaultValue: '보내지 않은 부모 초안' }));
  }
  await act(async () => root.render(createElement(AuthProvider, null, createElement(ProjectEventsProvider, {
    projectId: 'p1', onUnauthorized: vi.fn(), connectionOptions: { createEventSource: () => new Source() },
  }, createElement(ModalHostProvider, null, createElement(WorkspacePage, {
    projectId: 'p1', conversationId: 'c1', slots: { conversation: createElement(ParentConversation) },
  }))))));
  const panel = container.querySelector('#parent-messages') as HTMLDivElement;
  const draft = panel.querySelector('textarea')!;
  draft.value = '논의 중인 부모 초안';
  panel.scrollTop = 320;
  for (const slot of ['task-queue', 'conversation-tree']) {
    const opener = [...container.querySelectorAll(`[data-slot="${slot}"] button`)].find(button => button.textContent?.includes(task.title)) as HTMLButtonElement;
    await act(async () => opener.click());
    expect(container.querySelectorAll('dialog[open]')).toHaveLength(1);
    expect(container.querySelector('dialog')?.textContent).toContain(message.body);
    const close = [...container.querySelectorAll('dialog button')].find(button => button.textContent === '닫기') as HTMLButtonElement;
    await act(async () => close.click());
    expect(container.querySelector('dialog')).toBeNull();
    expect(container.querySelector('#parent-messages')).toBe(panel);
    expect(draft.value).toBe('논의 중인 부모 초안');
    expect(panel.scrollTop).toBe(320);
    expect(window.location.pathname).toBe('/projects/p1/conversations/c1');
  }
  expect(mounts).toBe(1);
  expect(fakeFetch.mock.calls.every(([request]) => (request as Request).method === 'GET')).toBe(true);
});
