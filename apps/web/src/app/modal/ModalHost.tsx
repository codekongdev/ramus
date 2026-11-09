import { createContext, useContext, useMemo, useReducer, type ReactNode } from 'react';
import { initialModalHostState, modalHostReducer, type ModalEntry } from './modalHostReducer';

export type ModalHostApi = {
  readonly openModal: (entry: ModalEntry) => void;
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
      openModal: (entry) => dispatch({ type: 'open', entry }),
      closeModal: (id) => dispatch({ type: 'close', id }),
    }),
    [],
  );
  const current = state.current;

  return (
    <ModalHostContext.Provider value={api}>
      {children}
      <div className="app-modal-host" data-testid="modal-host">
        {current && (
          <ModalSlot key={current.id}>
            {current.render(() => dispatch({ type: 'close', id: current.id }))}
          </ModalSlot>
        )}
      </div>
    </ModalHostContext.Provider>
  );
}

function ModalSlot({ children }: { readonly children: ReactNode }) {
  return <>{children}</>;
}

export function useModalHost(): ModalHostApi {
  const api = useContext(ModalHostContext);
  if (!api) throw new Error('useModalHost must be used inside <ModalHostProvider>');
  return api;
}
