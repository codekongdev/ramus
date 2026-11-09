import './app.css';
import { ModalHostProvider } from './modal/ModalHost';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { useRoute } from './routing/useRoute';

export function App() {
  return (
    <ModalHostProvider>
      <AppRoutes />
    </ModalHostProvider>
  );
}

function AppRoutes() {
  const [route] = useRoute();
  switch (route.name) {
    case 'login':
      return <LoginPage />;
    case 'workspace':
      return <WorkspacePage projectId={route.projectId} conversationId={route.conversationId} />;
    case 'notFound':
      return <NotFoundPage />;
  }
}
