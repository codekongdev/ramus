import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import '@ramus/design-system/styles.css';
import './ui/overrides.css';
import { App } from './app/App';
import { UiProvider } from './ui';

// Dev-only component catalog. The `import.meta.env.DEV` guard is statically replaced in
// production builds, so the catalog chunk is tree-shaken out of the bundle.
const Catalog = import.meta.env.DEV ? lazy(() => import('@ramus/design-system/catalog')) : null;
const showCatalog = import.meta.env.DEV && window.location.pathname === '/__catalog';

const container = document.getElementById('root');
if (!container) throw new Error('#root element not found');

createRoot(container).render(
  <StrictMode>
    {showCatalog && Catalog ? (
      <UiProvider>
        <Suspense fallback={null}>
          <Catalog />
        </Suspense>
      </UiProvider>
    ) : (
      <UiProvider>
        <App />
      </UiProvider>
    )}
  </StrictMode>,
);
