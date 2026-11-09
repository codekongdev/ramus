import type { ReactNode } from 'react';

/**
 * The app shows at most one modal. Ordinary opens replace it; an interruption such as
 * AI connection may retain the original entry so its pending effects and drafts survive.
 * Step changes inside a modal are the feature's own state, not new host entries.
 */
export type ModalRender = (close: () => void) => ReactNode;

export type ModalEntry = {
  /** Stable key such as `task:<taskId>`. Re-opening the same id keeps the modal mounted. */
  readonly id: string;
  readonly render: ModalRender;
};

export type ModalHostState = {
  readonly current: ModalEntry | null;
  readonly suspended?: ModalEntry;
};

export type ModalHostIntent =
  | { readonly type: 'open'; readonly entry: ModalEntry; readonly preserveCurrent?: boolean }
  /** A matching id resumes a suspended entry. Omitting it dismisses the entire flow. */
  | { readonly type: 'close'; readonly id?: string };

export const initialModalHostState: ModalHostState = { current: null };

export function modalHostReducer(state: ModalHostState, intent: ModalHostIntent): ModalHostState {
  switch (intent.type) {
    case 'open':
      if (intent.preserveCurrent && state.current) {
        if (intent.entry.id === state.current.id) return { ...state, current: intent.entry };
        // Only the original flow is retained if its interruption is replaced again.
        return { current: intent.entry, suspended: state.suspended ?? state.current };
      }
      return { current: intent.entry };
    case 'close':
      if (state.current === null) return state;
      if (intent.id !== undefined && intent.id !== state.current.id) return state;
      if (intent.id !== undefined && state.suspended) return { current: state.suspended };
      return { current: null };
  }
}
