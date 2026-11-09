// @vitest-environment jsdom
import { createElement, act, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Dialog, DialogVisibilityProvider } from '../../src/ui';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const showModal = vi.fn(function (this: HTMLDialogElement) {
  this.setAttribute('open', '');
});
const close = vi.fn(function (this: HTMLDialogElement) {
  this.removeAttribute('open');
});

let container: HTMLElement;
let root: Root;

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = showModal;
  HTMLDialogElement.prototype.close = close;
  showModal.mockClear();
  close.mockClear();
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

function renderDialog(open: boolean, onOpenChange = vi.fn(), extra: Record<string, unknown> = {}) {
  act(() => {
    root.render(
      createElement(Dialog, { open, onOpenChange, title: '작업 모달', children: createElement('p', null, '본문'), ...extra }),
    );
  });
  return onOpenChange;
}

const dialogEl = () => container.querySelector('dialog') as HTMLDialogElement;

describe('Dialog', () => {
  it('calls showModal when open and close when closed', () => {
    renderDialog(true);
    expect(showModal).toHaveBeenCalledTimes(1);
    expect(dialogEl().hasAttribute('open')).toBe(true);
    renderDialog(false);
    expect(close).toHaveBeenCalled();
    expect(dialogEl().hasAttribute('open')).toBe(false);
  });

  it('does not show the modal while closed and does not render children', () => {
    renderDialog(false);
    expect(showModal).not.toHaveBeenCalled();
    expect(container.textContent).not.toContain('본문');
  });

  it('is named by its title and has a Korean close button', () => {
    renderDialog(true);
    const labelId = dialogEl().getAttribute('aria-labelledby');
    expect(labelId).toBeTruthy();
    expect(document.getElementById(labelId!)?.textContent).toBe('작업 모달');
    const closeButton = [...container.querySelectorAll('button')].find((b) => b.textContent === '닫기');
    expect(closeButton).toBeDefined();
  });

  it('close button calls onOpenChange(false)', () => {
    const onOpenChange = renderDialog(true);
    const closeButton = [...container.querySelectorAll('button')].find((b) => b.textContent === '닫기')!;
    act(() => closeButton.click());
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('Escape (native cancel event) calls onOpenChange(false) and is default-prevented', () => {
    const onOpenChange = renderDialog(true);
    const cancel = new Event('cancel', { cancelable: true });
    act(() => {
      dialogEl().dispatchEvent(cancel);
    });
    expect(cancel.defaultPrevented).toBe(true);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('renders headerActions and footer', () => {
    renderDialog(true, vi.fn(), {
      headerActions: createElement('button', { type: 'button' }, '결과 정리'),
      footer: createElement('span', null, '푸터'),
    });
    expect(container.textContent).toContain('결과 정리');
    expect(container.textContent).toContain('푸터');
  });

  it('restores focus to the previously focused element after closing', () => {
    const opener = document.createElement('button');
    opener.textContent = '열기';
    document.body.append(opener);
    opener.focus();
    expect(document.activeElement).toBe(opener);

    function Harness() {
      const [open, setOpen] = useState(false);
      return createElement(
        'div',
        null,
        createElement('button', { id: 'toggle', onClick: () => setOpen(true) }, 'x'),
        createElement(Dialog, { open, onOpenChange: setOpen, title: 't', children: 'c' }),
      );
    }
    act(() => root.render(createElement(Harness)));
    const toggle = container.querySelector('#toggle') as HTMLButtonElement;
    toggle.focus();
    act(() => toggle.click());
    const inside = [...container.querySelectorAll('button')].find((b) => b.textContent === '닫기')!;
    inside.focus();
    expect(document.activeElement).toBe(inside);
    act(() => inside.click());
    expect(document.activeElement).toBe(toggle);
    opener.remove();
  });

  it('closes native visibility while preserving requested content and ignoring the queued close event', () => {
    const onOpenChange = vi.fn();
    const renderVisible = (visible: boolean) => act(() => root.render(
      createElement(DialogVisibilityProvider, { visible, children:
        createElement(Dialog, { open: true, onOpenChange, title: 'Task', children: createElement('textarea', { defaultValue: 'draft' }) }),
      }),
    ));
    renderVisible(true);
    const dialog = dialogEl();
    const textarea = container.querySelector('textarea')!;
    textarea.value = 'unsaved draft';
    renderVisible(false);
    expect(dialog.open).toBe(false);
    expect(dialog.hidden).toBe(true);
    expect(container.querySelector('textarea')).toBe(textarea);
    expect(textarea.value).toBe('unsaved draft');
    act(() => dialog.dispatchEvent(new Event('close')));
    expect(onOpenChange).not.toHaveBeenCalled();
    renderVisible(true);
    expect(dialogEl()).toBe(dialog);
    expect(dialog.open).toBe(true);
    expect(dialog.hidden).toBe(false);
    expect(container.querySelector('textarea')).toBe(textarea);
    expect(textarea.value).toBe('unsaved draft');
  });
});
