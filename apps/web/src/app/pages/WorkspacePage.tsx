import { useWorkspaceHeader } from '../../features/auth/WorkspaceHeader';
import { useCallback, useEffect, type ReactNode } from 'react';
import { TaskConversationTree } from '../../features/task-navigation';
import { TaskQueue } from '../../features/task-queue';
import { TaskModal } from '../../features/task-modal';
import { Conversation } from '../../features/conversation';
import { SummaryAction, TaskResultTab, useTaskResult } from '../../features/results';
import type { Task } from '../../lib/api/task-contract';
import { AppShell, type AppShellSlots } from '../layout/AppShell';
import { useModalHost } from '../modal/ModalHost';
import { navigate } from '../routing/useRoute';
import { ResourcesMenuButton } from '../../features/resources';

export type WorkspacePageProps = {
  readonly projectId: string;
  readonly conversationId?: string;
  /** Keeps the parent conversation mounted while a child task is open. */
  readonly slots?: Omit<AppShellSlots, 'taskQueue' | 'conversationTree'>;
  readonly renderTaskHeaderActions?: (task: Task) => ReactNode;
  readonly renderTaskResultTab?: (task: Task, nav: { readonly closeModal: () => void }) => ReactNode;
  readonly ensureAiConnection?: () => Promise<boolean>;
};

function WorkspaceTaskModal({ taskId, close, ensureAiConnection, renderTaskHeaderActions, renderTaskResultTab }: {
  readonly taskId: string;
  readonly close: () => void;
  readonly ensureAiConnection?: () => Promise<boolean>;
  readonly renderTaskHeaderActions?: WorkspacePageProps['renderTaskHeaderActions'];
  readonly renderTaskResultTab?: WorkspacePageProps['renderTaskResultTab'];
}) {
  const controller = useTaskResult(taskId, ensureAiConnection);
  return <TaskModal taskId={taskId} onClose={close} ensureAiConnection={ensureAiConnection} onTaskChanged={controller.taskChanged}
    renderHeaderActions={(task, nav) => renderTaskHeaderActions ? renderTaskHeaderActions(task) : <SummaryAction controller={controller} onShowResult={nav.showResultTab} />}
    renderResultTab={(task, nav) => renderTaskResultTab ? renderTaskResultTab(task, nav) : <TaskResultTab controller={controller} />} />;
}

/** Composition point: A owns the task shell; B supplies result content and actions. */
export function WorkspacePage({
  projectId, conversationId, slots, renderTaskHeaderActions,
  renderTaskResultTab, ensureAiConnection,
}: WorkspacePageProps) {
  const header = useWorkspaceHeader(projectId);
  const selectConversation = useCallback((id: string) => navigate({ name: 'workspace', projectId, conversationId: id }), [projectId]);
  const selectInitialConversation = useCallback((id: string) => navigate({ name: 'workspace', projectId, conversationId: id }, { replace: true }), [projectId]);
  const { openModal, closeModal } = useModalHost();
  useEffect(() => () => closeModal(), [projectId, conversationId, closeModal]);
  const openTask = useCallback((taskId: string) => {
    openModal({
      id: `task:${taskId}`,
      render: (close) => <WorkspaceTaskModal key={taskId} taskId={taskId} close={close}
        renderTaskHeaderActions={renderTaskHeaderActions} renderTaskResultTab={renderTaskResultTab}
        ensureAiConnection={ensureAiConnection} />,
    });
  }, [openModal, renderTaskHeaderActions, renderTaskResultTab, ensureAiConnection]);
  return <AppShell project={header.project} participants={header.participants} {...slots}
    workspaceMenu={slots?.workspaceMenu ?? <ResourcesMenuButton projectId={projectId} conversationId={conversationId} />}
    conversation={slots?.conversation ?? <Conversation projectId={projectId} conversationId={conversationId} ensureAiConnection={ensureAiConnection} />}
    conversationTree={projectId && <TaskConversationTree projectId={projectId} conversationId={conversationId}
      onSelectConversation={selectConversation} onInitialConversation={selectInitialConversation}
      onOpenTask={openTask} />}
    taskQueue={projectId && conversationId && <TaskQueue conversationId={conversationId} onOpenTask={openTask} />}
  />;

}
