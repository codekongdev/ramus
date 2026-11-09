import { createContext, useContext, useMemo, useReducer, type ReactNode } from 'react';
import { DialogVisibilityProvider } from '../../ui';
import { initialModalHostState, modalHostReducer, type ModalEntry } from './modalHostReducer';

export type ModalHostApi = {
  readonly openModal: (entry: ModalEntry, options?: { readonly preserveCurrent?: boolean }) => void;
  readonly closeModal: (id?: string) => void;
};

const ModalHostContext = createContext<ModalHostApi | null>(null);

/**
 * Provides `useModalHost()` and renders the current modal after `children`.
 * The entry's `render(close)` returns the modal itself, normally `src/ui` Dialog:
 *
 *   openModal({ id: `task:${id}`, render: (close) => (
 *     <Dialog open title="…" onOpenChange={(open) => { if (!open) close(); }}>…</Dialog>
 *   ) });
 */
export function ModalHostProvider({ children }: { readonly children: ReactNode }) {
  const [state, dispatch] = useReducer(modalHostReducer, initialModalHostState);
  const api = useMemo<ModalHostApi>(
    () => ({
      openModal: (entry, options) => dispatch({ type: 'open', entry, preserveCurrent: options?.preserveCurrent }),
      closeModal: (id) => dispatch({ type: 'close', id }),
    }),
    [],
  );
  const current = state.current;
  const entries = state.suspended ? [state.suspended, ...(current ? [current] : [])] : current ? [current] : [];

  return (
    <ModalHostContext.Provider value={api}>
      {children}
      <div className="app-modal-host" data-testid="modal-host">
        {entries.map((entry) => (
          <ModalSlot key={entry.id} visible={entry.id === current?.id}>
            {entry.render(() => dispatch({ type: 'close', id: entry.id }))}
          </ModalSlot>
        ))}
      </div>
    </ModalHostContext.Provider>
  );
}

function ModalSlot({ children, visible }: { readonly children: ReactNode; readonly visible: boolean }) {
  return <DialogVisibilityProvider visible={visible}>
    <div hidden={!visible} inert={!visible}>{children}</div>
  </DialogVisibilityProvider>;
}

export function useModalHost(): ModalHostApi {
  const api = useContext(ModalHostContext);
  if (!api) throw new Error('useModalHost must be used inside <ModalHostProvider>');
  return api;
}
