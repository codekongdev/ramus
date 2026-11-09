// @vitest-environment jsdom
import { StrictMode, act, useRef, useState, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ModalHostProvider, useModalHost } from '../../../src/app/modal/ModalHost';
import {
  AiConnectionModalHost, AiConnectionProvider, useAiConnection, useAiConnectionController,
} from '../../../src/features/ai-connection/AiConnectionProvider';
import { AiConnectionButton } from '../../../src/features/ai-connection/AiConnectionButton';
import type { AiConnectionApi, ConnectionState, ConnectionStatus } from '../../../src/features/ai-connection/api';
import { aiConnectionMessages as messages } from '../../../src/features/ai-connection/messages';
import type { ApiResult } from '../../../src/lib/api';
import { Dialog, UiProvider } from '../../../src/ui';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const ok = (status: ConnectionStatus): ApiResult<ConnectionState> => ({ ok: true, status: 200, data: { status } });

let container: HTMLElement;
let root: Root;
let api: AiConnectionApi;
let controller: ReturnType<typeof useAiConnectionController>;

function Capture() {
  controller = useAiConnectionController();
  return null;
}

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute('open', '');
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute('open');
  });
  window.history.replaceState(null, '', '/');
  api = {
    read: vi.fn().mockResolvedValue(ok('none')),
    connect: vi.fn().mockResolvedValue(ok('connected')),
    disconnect: vi.fn().mockResolvedValue(ok('none')),
  };
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

async function render(children: ReactNode, strict = false) {
  const tree = <UiProvider><AiConnectionProvider api={api}><ModalHostProvider>
    <AiConnectionModalHost /><Capture />{children}
  </ModalHostProvider></AiConnectionProvider></UiProvider>;
  await act(async () => root.render(strict ? <StrictMode>{tree}</StrictMode> : tree));
}

function button(text: string) {
  const result = [...container.querySelectorAll('button')].find((element) => element.textContent === text);
  if (!result) throw new Error(`Missing button: ${text}`);
  return result;
}

async function click(text: string) {
  await act(async () => button(text).click());
}

async function fill(input: HTMLInputElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

const keyInput = () => container.querySelector('dialog input') as HTMLInputElement;
async function submitKey() {
  await act(async () => {
    container.querySelector('dialog form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });
}

type RequestDraft = { conversationId: string; body: string; attachments: string[] };
function RequestCaller({ draft, send }: { draft: RequestDraft; send: (request: RequestDraft) => void }) {
  const { ensure } = useAiConnection();
  const [body, setBody] = useState(draft.body);
  const sending = useRef(false);
  return <>
    <input className="request-draft" value={body} onChange={(event) => setBody(event.target.value)} />
    <button onClick={async () => {
      if (sending.current) return;
      sending.current = true;
      const captured = { conversationId: draft.conversationId, body, attachments: [...draft.attachments] };
      if (await ensure()) send(captured);
      sending.current = false;
    }}>Send request</button>
  </>;
}

describe('AI connection dialog integration', () => {
  it('masks keys, supports validation correction, clears secrets after success and never persists them', async () => {
    const persist = vi.spyOn(Storage.prototype, 'setItem');
    vi.mocked(api.connect).mockResolvedValueOnce({
      ok: false, error: { kind: 'business', status: 422, code: 'AI_KEY_INVALID', message: 'Invalid test key.', details: null },
    });
    await render(<AiConnectionButton />, true);
    await click(messages.title);
    const input = keyInput();
    expect(input.type).toBe('password');
    expect(document.activeElement).toBe(input);
    expect(document.querySelector(`label[for="${input.id}"]`)?.textContent).toBe(messages.keyLabel);
    expect(button(messages.connect).disabled).toBe(true);

    await fill(input, 'test-only-invalid-key');
    await act(async () => (container.querySelector('[aria-label="' + messages.showKey + '"]') as HTMLButtonElement).click());
    expect(input.type).toBe('text');
    await submitKey();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Invalid test key.');
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.value).toBe('test-only-invalid-key');
    expect(JSON.stringify(controller.store.getState())).not.toContain('test-only-invalid-key');

    await fill(input, 'test-only-corrected-key');
    await submitKey();
    expect(container.textContent).toContain(messages.connected);
    expect(keyInput().value).toBe('');
    expect(keyInput().type).toBe('password');
    expect(persist).not.toHaveBeenCalled();
    expect(window.location.href).not.toContain('test-only');
    await click(messages.done);
    expect(container.querySelector('dialog')).toBeNull();
    expect(api.connect).toHaveBeenCalledTimes(2);
  });

  it('replaces a connected key, confirms removal and returns to disconnected settings', async () => {
    vi.mocked(api.read).mockResolvedValue(ok('connected'));
    await render(<AiConnectionButton />);
    await click(messages.title);
    expect(keyInput().value).toBe('');
    expect(container.querySelector('label')?.textContent).toBe(messages.replacementLabel);
    await fill(keyInput(), 'test-only-replacement-key');
    await submitKey();
    expect(api.connect).toHaveBeenCalledWith('test-only-replacement-key', expect.any(String), expect.any(AbortSignal));
    await click(messages.disconnect);
    expect(container.textContent).toContain(messages.disconnectDescription);
    await click(messages.keepConnection);
    expect(api.disconnect).not.toHaveBeenCalled();
    await click(messages.disconnect);
    await click(messages.disconnect);
    expect(api.disconnect).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain(messages.disconnected);
    expect(controller.store.getState().status).toBe('none');
    expect(keyInput().value).toBe('');
  });

  it('keeps the original target, body and attachments while connecting and resumes the request once', async () => {
    const send = vi.fn();
    const original: RequestDraft = { conversationId: 'conversation-original', body: '@AI compare these', attachments: ['file-one'] };
    await render(<RequestCaller draft={original} send={send} />, true);
    await click('Send request');
    expect(container.querySelector('dialog h2')?.textContent).toBe(messages.requiredTitle);
    expect(container.textContent).toContain(messages.pendingRequest);
    expect((container.querySelector('.request-draft') as HTMLInputElement).value).toBe(original.body);
    expect(send).not.toHaveBeenCalled();
    await render(<RequestCaller draft={{ conversationId: 'conversation-later', body: 'later', attachments: ['file-two'] }} send={send} />, true);
    await click('Send request');
    await fill(keyInput(), 'test-only-key');
    await submitKey();
    expect(send).toHaveBeenCalledTimes(1);
    expect(send).toHaveBeenCalledWith(original);
    expect(container.querySelector('dialog')).toBeNull();
  });

  it('leaves the caller draft intact and does not run the request on cancel or Escape', async () => {
    const send = vi.fn();
    const draft: RequestDraft = { conversationId: 'conversation-one', body: '@AI draft to keep', attachments: ['file-one'] };
    await render(<RequestCaller draft={draft} send={send} />);
    await click('Send request');
    await fill(keyInput(), 'test-only-unsubmitted-key');
    await click(messages.cancel);
    expect(container.querySelector('dialog')).toBeNull();
    expect(send).not.toHaveBeenCalled();
    expect(api.connect).not.toHaveBeenCalled();
    expect((container.querySelector('.request-draft') as HTMLInputElement).value).toBe(draft.body);
    await click('Send request');
    expect(keyInput().value).toBe('');
    await act(async () => container.querySelector('dialog')!.dispatchEvent(new Event('cancel', { cancelable: true })));
    expect(container.querySelector('dialog')).toBeNull();
    expect(send).not.toHaveBeenCalled();
  });

  it('resolves the pending caller as cancelled when another host modal replaces the connection', async () => {
    const send = vi.fn();
    function ReplaceModal() {
      const host = useModalHost();
      return <button onClick={() => host.openModal({ id: 'other', render: () => (
        <Dialog open title="Other modal" onOpenChange={() => undefined}>Other content</Dialog>
      ) })}>Replace modal</button>;
    }
    const draft: RequestDraft = { conversationId: 'conversation-one', body: '@AI preserve', attachments: [] };
    await render(<><RequestCaller draft={draft} send={send} /><ReplaceModal /></>);
    await click('Send request');
    await click('Replace modal');
    expect(container.querySelector('dialog h2')?.textContent).toBe('Other modal');
    expect(controller.store.getState().open).toBe(false);
    expect(send).not.toHaveBeenCalled();
    expect((container.querySelector('.request-draft') as HTMLInputElement).value).toBe(draft.body);
  });

  it('can retry a failed state read without losing the pending caller', async () => {
    vi.mocked(api.read).mockResolvedValueOnce({ ok: false, error: { kind: 'network', cause: new TypeError('offline') } });
    const send = vi.fn();
    await render(<RequestCaller draft={{ conversationId: 'c1', body: '@AI wait', attachments: [] }} send={send} />);
    await click('Send request');
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
    vi.mocked(api.read).mockResolvedValueOnce(ok('connected'));
    await click(messages.retry);
    expect(send).toHaveBeenCalledTimes(1);
    expect(container.querySelector('dialog')).toBeNull();
  });
});
