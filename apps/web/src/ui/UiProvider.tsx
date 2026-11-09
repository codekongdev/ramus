import type { ReactNode } from 'react';
import { RamusProvider } from '@ramus/design-system';
import { UI_CONTRAST, UI_THEME } from './theme';

export function UiProvider({ children }: { readonly children: ReactNode }) {
  return (
    <RamusProvider theme={UI_THEME} contrast={UI_CONTRAST} className="ui-root">
      {children}
    </RamusProvider>
  );
}
