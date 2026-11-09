import { createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from 'react';
import { useModalHost } from '../../app/modal/ModalHost';
import { api as appApi } from '../../lib/api';
import { createAiConnectionApi, type AiConnectionApi } from './api';
import { createAiConnectionController, type AiConnectionController } from './controller';
import { AiConnectionDialog } from './AiConnectionDialog';
import './ai-connection.css';

const productionApi = createAiConnectionApi(appApi);
const Context = createContext<AiConnectionController | null>(null);

export function AiConnectionProvider({ children, api = productionApi }: {
  readonly children: ReactNode;
  readonly api?: AiConnectionApi;
}) {
  const [controller] = useState(() => createAiConnectionController(api));
  useEffect(() => {
    controller.activate();
    return () => controller.deactivate();
  }, [controller]);
  return <Context.Provider value={controller}>{children}</Context.Provider>;
}

export function useAiConnectionController() {
  const controller = useContext(Context);
  if (!controller) throw new Error('useAiConnection requires AiConnectionProvider');
  return controller;
}

/** Call immediately before submitting the captured request; false leaves the caller's draft intact. */
export function useAiConnection() {
  const controller = useAiConnectionController();
  const state = useSyncExternalStore(controller.store.subscribe, controller.store.getState, controller.store.getState);
  return useMemo(() => ({
    status: state.status,
    busy: state.phase !== 'idle',
    ensure: controller.ensure,
    manage: controller.manage,
  }), [controller, state.status, state.phase]);
}

/** Mount inside ModalHostProvider, with AiConnectionProvider above both the host and its children. */
export function AiConnectionModalHost() {
  const controller = useAiConnectionController();
  const state = useSyncExternalStore(controller.store.subscribe, controller.store.getState, controller.store.getState);
  const { openModal, closeModal } = useModalHost();
  useEffect(() => {
    if (state.open) {
      openModal({ id: 'ai-connection', render: () => <AiConnectionDialog /> }, { preserveCurrent: true });
    } else {
      closeModal('ai-connection');
    }
  }, [state.open, openModal, closeModal]);
  return null;
}
