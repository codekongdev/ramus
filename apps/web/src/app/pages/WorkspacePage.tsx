import { useWorkspaceHeader } from '../../features/auth/WorkspaceHeader';
import { useCallback, useEffect, type ReactNode } from 'react';
import { TaskConversationTree } from '../../features/task-navigation';
import { TaskQueue } from '../../features/task-queue';
import { TaskModal } from '../../features/task-modal';
import { Conversation } from '../../features/conversation';
import { ConclusionView, ResultRevisionDialog, SummaryAction, TaskResultTab, useTaskResult, type ConclusionActions, type ResultRevision } from '../../features/results';
import type { Task } from '../../lib/api/task-contract';
import { AppShell, type AppShellSlots } from '../layout/AppShell';
import { useModalHost } from '../modal/ModalHost';
import { navigate } from '../routing/useRoute';
import { ResourcesMenuButton } from '../../features/resources';
import { ReceivedResults, ReceivedResultDialog, SendConclusion, useSendConclusion, type ConversationInput } from '../../features/sharing';
import { ResultsLibraryMenuButton } from '../../features/results-library';

/** Compose result reading and sending without feature-to-feature imports. */
function WorkspaceConclusion({ revision, projectId, conversationId, actions }: {
  readonly revision: ResultRevision;
  readonly projectId: string;
  readonly conversationId: string;
  readonly actions?: ConclusionActions;
}) {
  const send = useSendConclusion();
  if (send.state.target) return <SendConclusion controller={send} />;
  return <>
    {send.state.notice && <p role="status">{send.state.notice}</p>}
    <ConclusionView revision={revision} {...actions} sendButtonRef={send.returnFocusRef}
      onSendToConversation={actions?.onSendToConversation ?? (value => send.dispatch({ type: 'open', target: { projectId, currentConversationId: conversationId, revision: value } }))} />
  </>;
}

export type WorkspacePageProps = {
  readonly projectId: string;
  readonly conversationId?: string;
  /** Keeps the parent conversation mounted while a child task is open. */
  readonly slots?: Omit<AppShellSlots, 'taskQueue' | 'conversationTree'>;
  readonly renderTaskHeaderActions?: (task: Task) => ReactNode;
  readonly renderTaskResultTab?: (task: Task, nav: { readonly closeModal: () => void }) => ReactNode;
  readonly ensureAiConnection?: () => Promise<boolean>;
  /** B6/B7 inject explicit transitions using the version currently being read. */
  readonly conclusionActions?: ConclusionActions;
};

function WorkspaceTaskModal({ taskId, close, ensureAiConnection, renderTaskHeaderActions, renderTaskResultTab, onOpenConclusion, conclusionActions }: {
  readonly taskId: string;
  readonly close: () => void;
  readonly ensureAiConnection?: () => Promise<boolean>;
  readonly renderTaskHeaderActions?: WorkspacePageProps['renderTaskHeaderActions'];
  readonly renderTaskResultTab?: WorkspacePageProps['renderTaskResultTab'];
  readonly onOpenConclusion: (revision: ResultRevision) => void;
  readonly conclusionActions?: ConclusionActions;
}) {
  const controller = useTaskResult(taskId, ensureAiConnection);
  const send = useSendConclusion();
  return <TaskModal taskId={taskId} onClose={close} ensureAiConnection={ensureAiConnection} onTaskChanged={controller.taskChanged}
    renderHeaderActions={(task, nav) => renderTaskHeaderActions ? renderTaskHeaderActions(task) : <SummaryAction controller={controller} onShowResult={nav.showResultTab} />}
    renderResultTab={(task, nav) => renderTaskResultTab ? renderTaskResultTab(task, nav)
      : send.state.target ? <SendConclusion controller={send} /> : <>
        {send.state.notice && <p role="status">{send.state.notice}</p>}
        <TaskResultTab controller={controller} onOpenConclusion={onOpenConclusion} {...conclusionActions} sendButtonRef={send.returnFocusRef}
          onSendToConversation={conclusionActions?.onSendToConversation ?? (revision => {
            const result = controller.state.result;
            if (result) send.dispatch({ type: 'open', target: { projectId: result.project_id, currentConversationId: result.source_conversation_id, revision } });
          })} />
      </>} />;
}

/** Composition point: A owns the task shell; B supplies result content and actions. */
export function WorkspacePage({
  projectId, conversationId, slots, renderTaskHeaderActions,
  renderTaskResultTab, ensureAiConnection, conclusionActions,
}: WorkspacePageProps) {
  const header = useWorkspaceHeader(projectId);
  const selectConversation = useCallback((id: string) => navigate({ name: 'workspace', projectId, conversationId: id }), [projectId]);
  const selectInitialConversation = useCallback((id: string) => navigate({ name: 'workspace', projectId, conversationId: id }, { replace: true }), [projectId]);
  const { openModal, closeModal } = useModalHost();
  useEffect(() => () => closeModal(), [projectId, conversationId, closeModal]);
  const openConclusion = useCallback((revision: ResultRevision) => {
    openModal({
      id: `result:${revision.id}`,
      render: close => <ResultRevisionDialog revisionId={revision.id} onClose={close}
        renderConclusion={value => <WorkspaceConclusion revision={value} projectId={projectId} conversationId={value.source.conversation_id} actions={conclusionActions} />} />,
    }, { preserveCurrent: true });
  }, [openModal, projectId, conclusionActions]);
  const openTask = useCallback((taskId: string) => {
    openModal({
      id: `task:${taskId}`,
      render: (close) => <WorkspaceTaskModal key={taskId} taskId={taskId} close={close}
        renderTaskHeaderActions={renderTaskHeaderActions} renderTaskResultTab={renderTaskResultTab}
        ensureAiConnection={ensureAiConnection} onOpenConclusion={openConclusion} conclusionActions={conclusionActions} />,
    });
  }, [openModal, renderTaskHeaderActions, renderTaskResultTab, ensureAiConnection, openConclusion, conclusionActions]);
  const openReceivedResult = useCallback((input: ConversationInput) => openModal({
    id: `result:${input.result_revision_id}`,
    render: close => <ReceivedResultDialog key={input.result_revision_id} projectId={projectId} input={input} onClose={close}
      renderConclusion={(revision, controls) => <ConclusionView revision={revision} {...conclusionActions} sendButtonRef={controls.sendButtonRef}
        onSendToConversation={conclusionActions?.onSendToConversation ?? controls.onSendToConversation} />} />,
  }), [openModal, projectId, conclusionActions]);
  return <AppShell project={header.project} participants={header.participants} {...slots}
    workspaceMenu={slots?.workspaceMenu ?? <>
      <ResultsLibraryMenuButton projectId={projectId} />
      <ResourcesMenuButton projectId={projectId} conversationId={conversationId} />
    </>}
    conversation={slots?.conversation ?? <Conversation projectId={projectId} conversationId={conversationId} ensureAiConnection={ensureAiConnection} />}
    conversationTree={projectId && <TaskConversationTree projectId={projectId} conversationId={conversationId}
      onSelectConversation={selectConversation} onInitialConversation={selectInitialConversation}
      onOpenTask={openTask} />}
    sharedResults={slots?.sharedResults ?? (conversationId && <ReceivedResults key={conversationId} conversationId={conversationId} onOpen={openReceivedResult} />)}
    taskQueue={projectId && conversationId && <TaskQueue conversationId={conversationId} onOpenTask={openTask} />}
  />;

}
