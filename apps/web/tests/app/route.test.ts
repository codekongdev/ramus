import { describe, expect, it } from 'vitest';
import { parseRoute, routePath, type Route } from '../../src/app/routing/route';

describe('parseRoute', () => {
  it.each<[string, Route]>([
    ['/', { name: 'workspace' }],
    ['', { name: 'workspace' }],
    ['/login', { name: 'login' }],
    ['/login/', { name: 'login' }],
    ['/projects/p1', { name: 'workspace', projectId: 'p1' }],
    ['/projects/p1/conversations/c1', { name: 'workspace', projectId: 'p1', conversationId: 'c1' }],
    ['/projects/a%2Fb', { name: 'workspace', projectId: 'a/b' }],
  ])('%s', (pathname, expected) => {
    expect(parseRoute(pathname)).toEqual(expected);
  });

  it.each(['/projects', '/projects/p1/conversations', '/projects/p1/other/c1', '/projects/p1/conversations/c1/x', '/login/x', '/nope'])(
    '%s is not found',
    (pathname) => {
      expect(parseRoute(pathname)).toEqual({ name: 'notFound', pathname });
    },
  );

  it('keeps a malformed escape as-is instead of throwing', () => {
    expect(parseRoute('/projects/%E0%A4%A')).toEqual({ name: 'workspace', projectId: '%E0%A4%A' });
  });
});

describe('routePath', () => {
  it.each<Route>([
    { name: 'login' },
    { name: 'workspace' },
    { name: 'workspace', projectId: 'p1' },
    { name: 'workspace', projectId: 'p 1', conversationId: 'c/1' },
  ])('round-trips %j', (route) => {
    expect(parseRoute(routePath(route))).toEqual(route);
  });

  it('drops a conversation without a project', () => {
    expect(routePath({ name: 'workspace', conversationId: 'c1' })).toBe('/');
  });
});
