import type { ReactNode } from 'react';

/**
 * Modal host state. The app shows at most one modal: opening another replaces the current
 * one instead of stacking (roadmap 4.2). Step changes inside a modal (e.g. 결론 보기 → 보내기)
 * are the feature's own state, not new host entries.
 */
export type ModalRender = (close: () => void) => ReactNode;

export type ModalEntry = {
  /** Stable key such as `task:<taskId>`. Re-opening the same id keeps the modal mounted. */
  readonly id: string;
  readonly render: ModalRender;
};

export type ModalHostState = { readonly current: ModalEntry | null };

export type ModalHostIntent =
  | { readonly type: 'open'; readonly entry: ModalEntry }
  /** With `id`, only closes when that modal is still the current one (ignores stale closes). */
  | { readonly type: 'close'; readonly id?: string };

export const initialModalHostState: ModalHostState = { current: null };

export function modalHostReducer(state: ModalHostState, intent: ModalHostIntent): ModalHostState {
  switch (intent.type) {
    case 'open':
      return { current: intent.entry };
    case 'close':
      if (state.current === null) return state;
      if (intent.id !== undefined && intent.id !== state.current.id) return state;
      return { current: null };
  }
}
