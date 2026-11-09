import { useCallback, useSyncExternalStore } from 'react';
import { parseRoute, routePath, type Route } from './route';

/** History adapter: the only place that reads or writes `window.location` / `history`. */
const NAVIGATE_EVENT = 'ramus:navigate';

function subscribe(onChange: () => void): () => void {
  window.addEventListener('popstate', onChange);
  window.addEventListener(NAVIGATE_EVENT, onChange);
  return () => {
    window.removeEventListener('popstate', onChange);
    window.removeEventListener(NAVIGATE_EVENT, onChange);
  };
}

const currentPathname = () => window.location.pathname;
const serverPathname = () => '/';

export function navigate(route: Route, options: { readonly replace?: boolean } = {}): void {
  const path = routePath(route);
  if (path === window.location.pathname) return;
  if (options.replace) window.history.replaceState(null, '', path);
  else window.history.pushState(null, '', path);
  window.dispatchEvent(new Event(NAVIGATE_EVENT));
}

export function useRoute(): readonly [Route, typeof navigate] {
  const pathname = useSyncExternalStore(subscribe, currentPathname, serverPathname);
  const route = parseRoute(pathname);
  const go = useCallback<typeof navigate>((next, options) => navigate(next, options), []);
  return [route, go] as const;
}
