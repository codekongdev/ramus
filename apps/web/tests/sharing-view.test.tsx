// @vitest-environment jsdom
import { act } from 'react';
import { transferableAbortController } from 'node:util';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import type { paths } from '../src/api/schema';
import { SendConclusion, useSendConclusion } from '../src/features/sharing/SendConclusion';
import { createApiClient } from '../src/lib/api';
import { revision } from './results-fixtures';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => vi.unstubAllGlobals());
it('distinguishes same-name paths in search and selected chips; removing one preserves the other and returns keyboard focus', async () => {
  vi.stubGlobal('AbortController', class { constructor() { return transferableAbortController(); } });
  const conversations = ['상위 A', '상위 B'].map((parent, index) => ({ id: `c${index}`, project_id: 'p1', parent_id: `parent${index}`, task_id: null,
    title: '같은 이름', path: [parent], created_by: 'u1', created_at: revision.created_at }));
  const fetch = vi.fn(async () => new Response(JSON.stringify({ items: conversations }), { headers: { 'Content-Type': 'application/json' } }));
  const client = createApiClient<paths>({ baseUrl: 'http://localhost', fetch });
  function Harness() {
    const controller = useSendConclusion(client);
    return controller.state.target ? <SendConclusion controller={controller} /> : <button ref={controller.returnFocusRef} onClick={() => controller.dispatch({ type: 'open', target: { projectId: 'p1', currentConversationId: 'current', revision } })}>열기</button>;
  }
  const container = document.createElement('div');
  document.body.append(container);
  const root = createRoot(container);
  try {
    await act(async () => root.render(<Harness />));
    await act(async () => container.querySelector('button')!.click());
    expect(container.querySelector('input[type="search"]')?.getAttribute('maxlength')).toBe('100');
    const checkboxes = [...container.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')];
    expect(checkboxes.map(checkbox => checkbox.closest('label')?.textContent)).toEqual(['같은 이름상위 A', '같은 이름상위 B']);
    act(() => { checkboxes[0]!.click(); checkboxes[1]!.click(); });
    expect(container.querySelectorAll('.sharing-chips li')).toHaveLength(2);
    expect(container.querySelector('.sharing-chips')?.textContent).toContain('같은 이름 (상위 A)');
    expect(container.querySelector('.sharing-chips')?.textContent).toContain('같은 이름 (상위 B)');
    act(() => container.querySelector<HTMLButtonElement>('[aria-label="같은 이름 (상위 A) 선택 해제"]')!.click());
    expect(checkboxes[0]!.checked).toBe(false);
    expect(checkboxes[1]!.checked).toBe(true);
    expect(container.querySelectorAll('.sharing-chips li')).toHaveLength(1);
    act(() => [...container.querySelectorAll('button')].find(button => button.textContent === '결론으로 돌아가기')!.click());
    expect(document.activeElement).toBe(container.querySelector('button'));
    expect(fetch).toHaveBeenCalledOnce();
  } finally {
    act(() => root.unmount());
    container.remove();
  }
});
