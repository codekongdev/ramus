import { useWorkspaceHeader } from '../../features/auth/WorkspaceHeader';
import { AppShell } from '../layout/AppShell';

export type WorkspacePageProps = {
  readonly projectId: string;
  readonly conversationId?: string;
};

/** Each feature mounts into its own shell slot. */
export function WorkspacePage({ projectId }: WorkspacePageProps) {
  const header = useWorkspaceHeader(projectId);
  return <AppShell project={header.project} participants={header.participants} />;
}
