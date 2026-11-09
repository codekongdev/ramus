// @vitest-environment jsdom
import { act, createElement } from 'react';
import { transferableAbortController } from 'node:util';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { paths } from '../src/api/schema';
import { ConclusionView } from '../src/features/results/ConclusionView';
import { ResultRevisionDialog } from '../src/features/results/ResultRevisionDialog';
import { createApiClient } from '../src/lib/api';
import { revision } from './results-fixtures';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let container: HTMLElement;
let root: Root;
const button = (text: string) => [...container.querySelectorAll('button')].find(node => node.textContent === text)!;
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});
beforeEach(() => {
  vi.stubGlobal('AbortController', class { constructor() { return transferableAbortController(); } });
  HTMLDialogElement.prototype.showModal = vi.fn(function(this: HTMLDialogElement) { this.setAttribute('open', ''); });
  HTMLDialogElement.prototype.close = vi.fn(function(this: HTMLDialogElement) { this.removeAttribute('open'); });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
});

describe('ConclusionView', () => {
  it('renders only the conclusion body and gives both explicit actions the same emphasis', () => {
    const value = { ...revision, conclusion: '첫 문단\n두 번째 문단 <script>private()</script>' };
    act(() => root.render(createElement(ConclusionView, { revision: value })));
    expect(container.textContent).toContain(value.conclusion);
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('textarea')).toBeNull();
    expect(container.textContent).not.toContain('출처 정보');
    expect(container.textContent).not.toContain(revision.source.run_id);
    const create = button('새 대화 만들기');
    const send = button('다른 대화에 보내기');
    expect(create.disabled).toBe(true);
    expect(send.disabled).toBe(true);
    expect(create.className).toBe(send.className);
  });

  it('never invokes downstream actions while reading; each click passes the displayed fixed revision', () => {
    const onCreateConversation = vi.fn();
    const onSendToConversation = vi.fn();
    act(() => root.render(createElement(ConclusionView, { revision, onCreateConversation, onSendToConversation })));
    expect(onCreateConversation).not.toHaveBeenCalled();
    expect(onSendToConversation).not.toHaveBeenCalled();
    act(() => button('새 대화 만들기').click());
    expect(onCreateConversation).toHaveBeenCalledExactlyOnceWith(revision);
    expect(onSendToConversation).not.toHaveBeenCalled();
    act(() => button('다른 대화에 보내기').click());
    expect(onSendToConversation).toHaveBeenCalledExactlyOnceWith(revision);
  });
});

describe('ResultRevisionDialog', () => {
  it('fetches a fixed conclusion and closes by button or Escape without writes or action callbacks', async () => {
    const fetch = vi.fn(async (_request: Request) => json(revision));
    const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch: fetch as typeof globalThis.fetch });
    const onClose = vi.fn();
    const onCreateConversation = vi.fn();
    const onSendToConversation = vi.fn();
    await act(async () => root.render(createElement(ResultRevisionDialog, {
      revisionId: revision.id, client, onClose, onCreateConversation, onSendToConversation,
    })));
    const dialog = container.querySelector('dialog')!;
    expect(dialog.open).toBe(true);
    expect(container.querySelector('h2')?.textContent).toBe(revision.title);
    expect(container.textContent).toContain(revision.conclusion);
    expect(container.querySelector('textarea')).toBeNull();
    await act(async () => button('닫기').click());
    expect(onClose).toHaveBeenCalledOnce();
    const cancel = new Event('cancel', { cancelable: true });
    act(() => dialog.dispatchEvent(cancel));
    expect(cancel.defaultPrevented).toBe(true);
    expect(onClose).toHaveBeenCalledTimes(2);
    expect(onCreateConversation).not.toHaveBeenCalled();
    expect(onSendToConversation).not.toHaveBeenCalled();
    expect(fetch.mock.calls.every(([request]) => request.method === 'GET')).toBe(true);
    expect(fetch.mock.calls.every(([request]) => request.url.endsWith(`/api/result-revisions/${revision.id}`))).toBe(true);
  });

  it('offers an explicit retry after a read failure and never starts a mutation', async () => {
    let failing = true;
    const fetch = vi.fn(async (_request: Request) => failing
      ? json({ error: { code: 'NOT_FOUND', message: '결론을 찾을 수 없습니다.', details: null } }, 404)
      : json(revision));
    const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch: fetch as typeof globalThis.fetch });
    await act(async () => root.render(createElement(ResultRevisionDialog, { revisionId: revision.id, client, onClose: vi.fn() })));
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('결론을 찾을 수 없습니다.');
    expect(button('새 대화 만들기')).toBeUndefined();
    failing = false;
    await act(async () => button('다시 불러오기').click());
    expect(container.textContent).toContain(revision.conclusion);
    expect(container.querySelector('[role="alert"]')).toBeNull();
    expect(fetch.mock.calls).toHaveLength(2);
    expect(fetch.mock.calls.every(([request]) => request.method === 'GET')).toBe(true);
  });

  it('hides the previous body during target changes and ignores a late response for another revision', async () => {
    const pending = new Map<string, (response: Response) => void>();
    const fetch = vi.fn(async (request: Request) => {
      const id = new URL(request.url).pathname.split('/').at(-1)!;
      return id === revision.id ? json(revision) : new Promise<Response>(resolve => pending.set(id, resolve));
    });
    const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch: fetch as typeof globalThis.fetch });
    const onClose = vi.fn();
    const onCreateConversation = vi.fn();
    const render = async (revisionId: string) => {
      await act(async () => root.render(createElement(ResultRevisionDialog, { revisionId, client, onClose, onCreateConversation })));
    };
    await render(revision.id);
    expect(container.textContent).toContain(revision.conclusion);
    await render('revision2');
    expect(container.textContent).not.toContain(revision.conclusion);
    expect(container.querySelector('h2')?.textContent).toBe('결론 보기');
    expect(button('새 대화 만들기')).toBeUndefined();
    await render('revision3');
    await act(async () => pending.get('revision2')!(json({ ...revision, id: 'revision2', conclusion: '늦게 도착한 결론' })));
    expect(container.textContent).not.toContain('늦게 도착한 결론');
    const current = { ...revision, id: 'revision3', version: 3, conclusion: '지금 선택한 고정 버전' };
    await act(async () => pending.get('revision3')!(json(current)));
    expect(container.textContent).toContain(current.conclusion);
    expect(onCreateConversation).not.toHaveBeenCalled();
    act(() => button('새 대화 만들기').click());
    expect(onCreateConversation).toHaveBeenCalledExactlyOnceWith(current);
    expect(fetch.mock.calls.every(([request]) => request.method === 'GET')).toBe(true);
  });
});
