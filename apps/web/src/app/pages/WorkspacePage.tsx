import { ResourcesMenuButton } from '../../features/resources';
import { AppShell } from '../layout/AppShell';

export type WorkspacePageProps = {
  readonly projectId?: string;
  readonly conversationId?: string;
};

/**
 * Composition point for the workspace screen. Each track mounts its feature component
 * into one slot here (one line per slot); until then every slot stays empty.
 */
export function WorkspacePage({ projectId, conversationId }: WorkspacePageProps) {
  return (
    <AppShell
      workspaceMenu={projectId && <ResourcesMenuButton projectId={projectId} conversationId={conversationId} />}
    />
  );
}
