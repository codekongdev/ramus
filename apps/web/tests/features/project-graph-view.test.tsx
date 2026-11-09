// @vitest-environment jsdom
import { act } from 'react';
import { transferableAbortController } from 'node:util';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import type { paths } from '../../src/api/schema';
import { createApiClient } from '../../src/lib/api';
import { ProjectGraphModal } from '../../src/features/project-graph/ProjectGraph';

vi.mock('../../src/lib/realtime', () => ({ useProjectEventListener: () => {}, useResyncListener: () => {} }));
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

it('renders the reverse usage as a distinct dashed curve alongside the solid branch', async () => {
  vi.stubGlobal('AbortController', class { constructor() { return transferableAbortController(); } });
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
  const nodes = [
    { conversation_id: 'parent', title: '부모', parent_id: null, task_status: null },
    { conversation_id: 'child', title: '작업', parent_id: 'parent', task_status: 'ready' },
  ];
  const api = createApiClient<paths>({ baseUrl: 'http://localhost', fetch: async request => new Response(JSON.stringify(
    (request as Request).url.endsWith('/graph') ? { nodes, edges: [
      { kind: 'branch', from: 'parent', to: 'child' }, { kind: 'uses_result', from: 'child', to: 'parent' },
    ] } : { items: [] },
  ), { headers: { 'Content-Type': 'application/json' } }) });
  const container = document.createElement('div'); document.body.append(container); const root = createRoot(container);
  try {
    await act(async () => root.render(<ProjectGraphModal projectId="p1" client={api} onClose={() => {}} onOpenTask={() => {}} onSelectConversation={() => {}} />));
    await vi.waitFor(() => expect(container.querySelector('svg path.is-dashed')).not.toBeNull());
    const line = container.querySelector('svg line')!, curve = container.querySelector('svg path.is-dashed')!;
    expect(line.getAttribute('class')).toBeNull();
    expect(curve.getAttribute('d')).toContain(' Q ');
    expect(container.textContent).toContain('부모 → 작업: 분기');
    expect(container.textContent).toContain('작업 → 부모: 결론 사용');
  } finally {
    await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals();
  }
});
