// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AppShell } from '../../src/app/layout/AppShell';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLElement;
let root: Root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

const slot = (name: string) => container.querySelector(`[data-slot="${name}"]`);

describe('AppShell (WF-01 layout)', () => {
  it('renders the four regions as landmarks', () => {
    act(() => root.render(createElement(AppShell)));
    expect(container.querySelector('header[aria-label="프로젝트"]')).not.toBeNull();
    expect(container.querySelector('nav[aria-label="대화 목록"]')).not.toBeNull();
    expect(container.querySelector('main[aria-label="대화"]')).not.toBeNull();
    expect(container.querySelector('aside[aria-label="작업과 공유받은 결과"]')).not.toBeNull();
  });

  it('leaves every slot empty by default', () => {
    act(() => root.render(createElement(AppShell)));
    const slots = [...container.querySelectorAll('[data-slot]')];
    expect(slots.map((el) => el.getAttribute('data-slot'))).toEqual([
      'project',
      'participants',
      'conversation-tree',
      'workspace-menu',
      'conversation',
      'task-queue',
      'shared-results',
    ]);
    for (const el of slots) expect(el.childNodes).toHaveLength(0);
  });

  it('places each slot in its WF-01 region', () => {
    act(() =>
      root.render(
        createElement(AppShell, {
          project: 'P',
          participants: 'U',
          conversationTree: 'T',
          workspaceMenu: 'M',
          conversation: 'C',
          taskQueue: 'Q',
          sharedResults: 'S',
        }),
      ),
    );
    expect(slot('project')?.closest('header')?.textContent).toBe('PU');
    expect(slot('participants')?.textContent).toBe('U');
    expect(slot('conversation-tree')?.closest('nav')?.textContent).toBe('TM');
    expect(slot('conversation')?.closest('main')?.textContent).toBe('C');
    expect(slot('task-queue')?.closest('aside')?.textContent).toBe('QS');
    expect(slot('shared-results')?.getAttribute('aria-label')).toBe('공유받은 결과');
  });
});
