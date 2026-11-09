/**
 * App routes as data. Parsing and formatting are pure so they can be unit-tested and
 * shared by the history adapter (`useRoute`) without touching `window`.
 */
export type Route =
  | { readonly name: 'login' }
  | {
      readonly name: 'workspace';
      /** Absent until the session tells us the shared sample project (P0-A4). */
      readonly projectId?: string;
      readonly conversationId?: string;
    }
  | { readonly name: 'notFound'; readonly pathname: string };

const segmentsOf = (pathname: string): string[] =>
  pathname.split('/').filter((segment) => segment.length > 0).map(safeDecode);

function safeDecode(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

export function parseRoute(pathname: string): Route {
  const segments = segmentsOf(pathname);
  const [first, projectId, third, conversationId, ...rest] = segments;

  if (segments.length === 0) return { name: 'workspace' };
  if (first === 'login' && segments.length === 1) return { name: 'login' };
  if (first === 'projects' && projectId !== undefined && rest.length === 0) {
    if (third === undefined) return { name: 'workspace', projectId };
    if (third === 'conversations' && conversationId !== undefined) {
      return { name: 'workspace', projectId, conversationId };
    }
  }
  return { name: 'notFound', pathname };
}

export function routePath(route: Route): string {
  switch (route.name) {
    case 'login':
      return '/login';
    case 'notFound':
      return route.pathname;
    case 'workspace': {
      if (route.projectId === undefined) return '/';
      const project = `/projects/${encodeURIComponent(route.projectId)}`;
      return route.conversationId === undefined
        ? project
        : `${project}/conversations/${encodeURIComponent(route.conversationId)}`;
    }
  }
}
