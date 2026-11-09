// @vitest-environment jsdom
import { act, createElement, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ProjectEvent } from '../../src/lib/events';
import {
  ProjectEventsProvider,
  useProjectEventListener,
  useProjectEventsStatus,
  useResyncListener,
  type EventSourceLike,
  type ProjectEventsConnectionOptions,
} from '../../src/lib/realtime';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

class FakeEventSource implements EventSourceLike {
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;
  private listeners = new Map<string, ((event: MessageEvent<string>) => void)[]>();
  constructor(readonly url: string) {}
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  close() {
    this.closed = true;
  }
  emit(type: string, data: unknown) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: JSON.stringify(data) }));
    }
  }
}

let container: HTMLElement;
let root: Root;
let sources: FakeEventSource[];
let options: ProjectEventsConnectionOptions;

beforeEach(() => {
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  sources = [];
  options = {
    createEventSource: (url) => {
      const source = new FakeEventSource(url);
      sources.push(source);
      return source;
    },
    checkSession: async () => true,
    onInvalidEvent: vi.fn(),
  };
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

const latest = () => sources[sources.length - 1]!;

function Feature({ name, log }: { name: string; log: string[] }) {
  const status = useProjectEventsStatus();
  useProjectEventListener((event: ProjectEvent) => log.push(`${name}:${event.type}`));
  useResyncListener((reason) => log.push(`${name}:resync:${reason}`));
  return createElement('p', { id: name }, status);
}

function renderTree(projectId: string, children: ReactNode, onUnauthorized = vi.fn()) {
  act(() =>
    root.render(
      createElement(ProjectEventsProvider, { projectId, onUnauthorized, connectionOptions: options }, children),
    ),
  );
  return onUnauthorized;
}

describe('ProjectEventsProvider', () => {
  it('shares one connection and fans validated events out to every feature', () => {
    const log: string[] = [];
    renderTree('p1', [
      createElement(Feature, { key: 'a', name: 'a', log }),
      createElement(Feature, { key: 'b', name: 'b', log }),
    ]);
    expect(sources).toHaveLength(1);
    expect(latest().url).toBe('/api/projects/p1/events');
    expect(container.textContent).toBe('connectingconnecting');

    act(() => latest().onopen?.(new Event('open')));
    expect(container.textContent).toBe('openopen');
    expect(log).toEqual(['a:resync:initial', 'b:resync:initial']);

    log.length = 0;
    act(() =>
      latest().emit('conversation_inputs.updated', { conversation_id: 'c1', occurred_at: '2026-11-09T00:00:00Z' }),
    );
    act(() => latest().emit('conversation_inputs.updated', { conversation_id: 'c1' })); // invalid: no occurred_at
    expect(log).toEqual(['a:conversation_inputs.updated', 'b:conversation_inputs.updated']);
    expect(options.onInvalidEvent).toHaveBeenCalledTimes(1);
  });

  it('reconnects when the project changes and keeps listeners subscribed', () => {
    const log: string[] = [];
    const tree = createElement(Feature, { name: 'a', log });
    renderTree('p1', tree);
    renderTree('p2', tree);
    expect(sources[0]!.closed).toBe(true);
    expect(latest().url).toBe('/api/projects/p2/events');
    act(() => latest().onopen?.(new Event('open')));
    expect(log).toEqual(['a:resync:initial']);
  });

  it('reports an expired session through onUnauthorized', async () => {
    const onUnauthorized = renderTree('p1', createElement(Feature, { name: 'a', log: [] }));
    await act(async () => latest().onerror?.(new Event('error')));
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(container.textContent).toBe('unauthorized');
  });

  it('closes the connection on unmount', () => {
    renderTree('p1', null);
    act(() => root.render(null));
    expect(latest().closed).toBe(true);
  });

  it('hooks fail loudly outside the provider', () => {
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => act(() => root.render(createElement(Feature, { name: 'x', log: [] })))).toThrow(
      /inside <ProjectEventsProvider>/,
    );
    errors.mockRestore();
  });
});
