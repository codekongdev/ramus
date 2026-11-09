// @vitest-environment jsdom
import { StrictMode, act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ModalHostProvider, useModalHost, type ModalHostApi } from '../../src/app/modal/ModalHost';
import { next, useStore, type EffectHandler, type Reducer } from '../../src/lib/mvi';
import { Dialog } from '../../src/ui';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

type State = { draft: string; phase: 'idle' | 'waiting' | 'sent' };
type Intent = { type: 'edit'; value: string } | { type: 'submit' } | { type: 'finished'; accepted: boolean };
type Effect = { draft: string };
const reducer: Reducer<State, Intent, Effect> = (state, intent) => {
  switch (intent.type) {
    case 'edit': return next({ ...state, draft: intent.value });
    case 'submit': return next({ ...state, phase: 'waiting' }, { draft: state.draft });
    case 'finished': return next({ ...state, phase: intent.accepted ? 'sent' : 'idle' });
  }
};

let container: HTMLElement;
let root: Root;
let host: ModalHostApi;
let gate: ReturnType<typeof deferred<boolean>>;
let execute: ReturnType<typeof vi.fn>;
let signals: AbortSignal[];
let maximumOpenDialogs: number;

function CaptureHost() {
  host = useModalHost();
  return null;
}

function Connection({ close }: { close: () => void }) {
  const finish = (accepted: boolean) => { gate.resolve(accepted); close(); };
  return <Dialog open title="AI connection" onOpenChange={(open) => { if (!open) finish(false); }}>
    <button onClick={() => finish(true)}>Accept key</button>
    <button onClick={() => finish(false)}>Cancel connection</button>
  </Dialog>;
}

function Task({ close }: { close: () => void }) {
  const handleEffect: EffectHandler<Effect, Intent> = async (effect, dispatch, signal) => {
    signals.push(signal);
    host.openModal({ id: 'ai-connection', render: (dismiss) => <Connection close={dismiss} /> }, { preserveCurrent: true });
    const accepted = await gate.promise;
    if (signal.aborted) return;
    if (accepted) execute(effect.draft);
    dispatch({ type: 'finished', accepted });
  };
      const [state, dispatch] = useStore<State, Intent, Effect>(reducer, { draft: '', phase: 'idle' }, handleEffect);
  return <Dialog open title="Original task" onOpenChange={(open) => { if (!open) close(); }}>
    <textarea aria-label="Task draft" value={state.draft} onChange={(event) => dispatch({ type: 'edit', value: event.target.value })} />
    <button disabled={state.phase === 'waiting'} onClick={() => dispatch({ type: 'submit' })}>Request AI</button>
    <output>{state.phase}</output>
  </Dialog>;
}

beforeEach(async () => {
  maximumOpenDialogs = 0;
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute('open', '');
    maximumOpenDialogs = Math.max(maximumOpenDialogs, document.querySelectorAll('dialog[open]').length);
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute('open');
    queueMicrotask(() => this.dispatchEvent(new Event('close')));
  });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  gate = deferred<boolean>();
  execute = vi.fn();
  signals = [];
  await act(async () => root.render(<StrictMode><ModalHostProvider><CaptureHost /></ModalHostProvider></StrictMode>));
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

const openTitles = () => [...container.querySelectorAll('dialog[open] h2')].map((element) => element.textContent);
const taskDialog = () => [...container.querySelectorAll('dialog')].find((dialog) => dialog.querySelector('h2')?.textContent === 'Original task')!;
async function click(text: string) {
  const button = [...container.querySelectorAll('button')].find((element) => element.textContent === text)!;
  await act(async () => button.click());
}

async function startRequest() {
  await act(async () => host.openModal({ id: 'task:one', render: (close) => <Task close={close} /> }));
  const task = taskDialog();
  const textarea = task.querySelector('textarea')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(textarea, 'unsaved original draft');
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await click('Request AI');
  expect(openTitles()).toEqual(['AI connection']);
  expect(task.open).toBe(false);
  expect(task.hidden).toBe(true);
  expect(task.querySelector('textarea')).toBe(textarea);
  expect(signals[0]!.aborted).toBe(false);
  expect(maximumOpenDialogs).toBe(1);
  return { task, textarea };
}

describe('preserved modal interruptions', () => {
  it('keeps the original task store and draft mounted and resumes its pending request after success', async () => {
    const { task, textarea } = await startRequest();
    await click('Accept key');
    expect(openTitles()).toEqual(['Original task']);
    expect(taskDialog()).toBe(task);
    expect(task.querySelector('textarea')).toBe(textarea);
    expect(textarea.value).toBe('unsaved original draft');
    expect(task.querySelector('output')?.textContent).toBe('sent');
    expect(execute).toHaveBeenCalledExactlyOnceWith('unsaved original draft');
    expect(signals[0]!.aborted).toBe(false);
    expect(maximumOpenDialogs).toBe(1);
  });

  it.each(['button', 'escape'] as const)('returns to the same task and draft after connection cancellation via %s', async (method) => {
    const { task, textarea } = await startRequest();
    if (method === 'button') await click('Cancel connection');
    else await act(async () => container.querySelector('dialog[open]')!.dispatchEvent(new Event('cancel', { cancelable: true })));
    expect(openTitles()).toEqual(['Original task']);
    expect(taskDialog()).toBe(task);
    expect(task.querySelector('textarea')).toBe(textarea);
    expect(textarea.value).toBe('unsaved original draft');
    expect(task.querySelector('output')?.textContent).toBe('idle');
    expect(execute).not.toHaveBeenCalled();
    expect(signals[0]!.aborted).toBe(false);
  });

  it('disposes both modals and aborts hidden effects on closeModal() for route changes', async () => {
    await startRequest();
    await act(async () => host.closeModal());
    expect(container.querySelectorAll('dialog')).toHaveLength(0);
    expect(signals[0]!.aborted).toBe(true);
    await act(async () => gate.resolve(true));
    expect(execute).not.toHaveBeenCalled();
    expect(container.querySelector('[data-testid="modal-host"]')?.childNodes).toHaveLength(0);
  });

  it('disposes a suspended task when an ordinary modal replaces the interruption', async () => {
    await startRequest();
    await act(async () => host.openModal({ id: 'task:two', render: () => (
      <Dialog open title="Replacement task" onOpenChange={() => undefined}>New task</Dialog>
    ) }));
    expect(openTitles()).toEqual(['Replacement task']);
    expect(container.querySelectorAll('dialog')).toHaveLength(1);
    expect(signals[0]!.aborted).toBe(true);
    await act(async () => gate.resolve(true));
    expect(execute).not.toHaveBeenCalled();
    expect(maximumOpenDialogs).toBe(1);
  });

  it('disposes both entries when the modal host unmounts while a task is suspended', async () => {
    await startRequest();
    await act(async () => root.render(<p>Left workspace</p>));
    expect(container.querySelectorAll('dialog')).toHaveLength(0);
    expect(signals[0]!.aborted).toBe(true);
    await act(async () => gate.resolve(true));
    expect(execute).not.toHaveBeenCalled();
  });
});
