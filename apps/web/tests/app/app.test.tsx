// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '../../src/app/App';
import { ModalHostProvider, useModalHost, type ModalHostApi } from '../../src/app/modal/ModalHost';
import { navigate } from '../../src/app/routing/useRoute';
import { Dialog } from '../../src/ui';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLElement;
let root: Root;

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute('open', '');
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute('open');
  });
  window.history.replaceState(null, '', '/');
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

const page = () => container.querySelector('[data-page]')?.getAttribute('data-page') ?? null;
const hasShell = () => container.querySelector('.app-shell') !== null;

describe('App routing', () => {
  it('shows the empty workspace shell at /', () => {
    act(() => root.render(createElement(App)));
    expect(hasShell()).toBe(true);
  });

  it('switches pages on navigate and on browser back', () => {
    act(() => root.render(createElement(App)));

    act(() => navigate({ name: 'login' }));
    expect(window.location.pathname).toBe('/login');
    expect(page()).toBe('login');
    expect(hasShell()).toBe(false);

    act(() => navigate({ name: 'workspace', projectId: 'p1', conversationId: 'c1' }));
    expect(window.location.pathname).toBe('/projects/p1/conversations/c1');
    expect(hasShell()).toBe(true);

    act(() => {
      window.history.replaceState(null, '', '/login');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    expect(page()).toBe('login');
  });

  it('shows not found for unknown paths', () => {
    window.history.replaceState(null, '', '/nope');
    act(() => root.render(createElement(App)));
    expect(page()).toBe('not-found');
  });

  it('replace navigation does not add a history entry', () => {
    act(() => root.render(createElement(App)));
    const before = window.history.length;
    act(() => navigate({ name: 'login' }, { replace: true }));
    expect(window.history.length).toBe(before);
    expect(page()).toBe('login');
  });
});

describe('ModalHostProvider', () => {
  let host: ModalHostApi;

  function Capture() {
    host = useModalHost();
    return null;
  }

  const dialogEntry = (id: string, title: string) => ({
    id,
    render: (close: () => void) =>
      createElement(Dialog, {
        open: true,
        title,
        onOpenChange: (open: boolean) => {
          if (!open) close();
        },
        children: `${title} 본문`,
      }),
  });

  const openTitles = () =>
    [...container.querySelectorAll('dialog[open] h2')].map((el) => el.textContent);

  beforeEach(() => {
    act(() => root.render(createElement(ModalHostProvider, null, createElement(Capture))));
  });

  it('renders nothing until a modal is opened', () => {
    expect(container.querySelector('[data-testid="modal-host"]')?.childNodes).toHaveLength(0);
  });

  it('opens one modal and replaces it instead of stacking', () => {
    act(() => host.openModal(dialogEntry('task:1', '경쟁사 분석')));
    expect(openTitles()).toEqual(['경쟁사 분석']);

    act(() => host.openModal(dialogEntry('task:2', '고객 분석')));
    expect(openTitles()).toEqual(['고객 분석']);
    expect(container.querySelectorAll('dialog')).toHaveLength(1);
  });

  it('closes via the modal close button', () => {
    act(() => host.openModal(dialogEntry('task:1', '경쟁사 분석')));
    const closeButton = [...container.querySelectorAll('button')].find((b) => b.textContent === '닫기');
    act(() => closeButton?.click());
    expect(container.querySelector('dialog')).toBeNull();
  });

  it('ignores closeModal for a modal that is no longer current', () => {
    act(() => host.openModal(dialogEntry('task:2', '고객 분석')));
    act(() => host.closeModal('task:1'));
    expect(openTitles()).toEqual(['고객 분석']);
    act(() => host.closeModal());
    expect(container.querySelector('dialog')).toBeNull();
  });

  it('throws when used outside the provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const orphan = createRoot(document.createElement('div'));
    expect(() => act(() => orphan.render(createElement(Capture)))).toThrow(/ModalHostProvider/);
    spy.mockRestore();
  });
});
