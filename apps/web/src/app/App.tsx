import { useCallback, useEffect } from 'react';
import { AuthProvider, useAuth } from '../features/auth/AuthProvider';
import { authMessages as m } from '../features/auth/messages';
import { AiConnectionButton, AiConnectionModalHost, AiConnectionProvider, useAiConnection } from '../features/ai-connection';
import { ProjectEventsProvider } from '../lib/realtime';
import { Button } from '../ui';
import './app.css';
import { ModalHostProvider } from './modal/ModalHost';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { useRoute } from './routing/useRoute';

export function App() {
  return <AuthProvider><AppRoutes /></AuthProvider>;
}

function AppRoutes() {
  const [route, navigate] = useRoute();
  const [auth, dispatch] = useAuth();
  useEffect(() => {
    if (route.name === 'notFound') return;
    if (auth.status === 'anonymous' && route.name !== 'login') navigate({ name: 'login' }, { replace: true });
    if (auth.status === 'authenticated' && auth.me && (route.name === 'login' || !route.projectId)) navigate({ name: 'workspace', projectId: auth.me.default_project_id }, { replace: true });
  }, [auth.status, auth.me, route, navigate]);
  if (route.name === 'notFound') return <NotFoundPage />;
  if (auth.status === 'initial' || auth.status === 'checking' || auth.status === 'checkFailed') return <main className="app-page"><div className="auth-session"><p role={auth.error ? 'alert' : 'status'}>{auth.error ?? m.checkSession}</p>{auth.status === 'checkFailed' && <Button onClick={() => dispatch({ type: 'start' })}>{m.retry}</Button>}</div></main>;
  if (auth.status === 'anonymous') return <LoginPage />;
  if (auth.me) {
    const projectId = route.name === 'workspace' && route.projectId ? route.projectId : auth.me.default_project_id;
    return <AuthenticatedWorkspace key={`${auth.me.account.id}:${projectId}`} projectId={projectId} conversationId={route.name === 'workspace' ? route.conversationId : undefined} />;
  }
  return null;
}

function AuthenticatedWorkspace({ projectId, conversationId }: { readonly projectId: string; readonly conversationId?: string }) {
  const [, dispatch] = useAuth();
  const expireSession = useCallback(() => dispatch({ type: 'sessionExpired' }), [dispatch]);
  // The modal host is inside the same project event connection as the parent workspace.
  return <ProjectEventsProvider projectId={projectId} onUnauthorized={expireSession}>
    <AiConnectionProvider>
      <ModalHostProvider>
        <AiConnectionModalHost />
        <ConnectedWorkspace projectId={projectId} conversationId={conversationId} />
      </ModalHostProvider>
    </AiConnectionProvider>
  </ProjectEventsProvider>;
}

function ConnectedWorkspace(props: { readonly projectId: string; readonly conversationId?: string }) {
  const { ensure } = useAiConnection();
  return <WorkspacePage {...props} ensureAiConnection={ensure} slots={{ accountActions: <AiConnectionButton /> }} />;
}
