import { useWorkspaceHeader } from '../../features/auth/WorkspaceHeader';
import { useCallback, useEffect, useRef, useState, type ReactNode, type Ref } from 'react';
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
import { ProjectGraphMenuButton } from '../../features/project-graph';
import { NewConversationPanel } from '../../features/sharing';
import { sharingMessages } from '../../features/sharing/conversationMessages';
import type { ConclusionRevision } from '../../lib/api/result-contract';
import type { Conversation as CreatedConversation } from '../../features/sharing/model';

/** Compose result reading and sending without feature-to-feature imports. */
function WorkspaceConclusion({ revision, projectId, conversationId, actions, sendButtonRef }: {
  readonly revision: ConclusionRevision;
  readonly projectId: string;
  readonly conversationId: string;
  readonly actions?: ConclusionActions;
  readonly sendButtonRef?: Ref<HTMLButtonElement>;
}) {
  const send = useSendConclusion();
  const [source, setSource] = useState<ConclusionRevision | null>(null);
  const createButtonRef = useRef<HTMLButtonElement>(null);
  const wasCreating = useRef(false);
  useEffect(() => {
    if (wasCreating.current && !source) createButtonRef.current?.focus({ preventScroll: true });
    wasCreating.current = source !== null;
  }, [source]);
  const { closeModal } = useModalHost();
  const created = useCallback((conversation: CreatedConversation) => {
    closeModal();
    navigate({ name: 'workspace', projectId: conversation.project_id, conversationId: conversation.id });
  }, [closeModal]);
  if (source) return <NewConversationPanel key={source.id} revision={source} onBack={() => setSource(null)} onCreated={created} />;
  if (send.state.target) return <SendConclusion controller={send} />;
  return <>
    {send.state.notice && <p role="status">{send.state.notice}</p>}
    <ConclusionView revision={revision} {...actions} onCreateConversation={actions?.onCreateConversation ?? setSource} createButtonRef={createButtonRef} sendButtonRef={sendButtonRef ?? send.returnFocusRef}
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
  const [source, setSource] = useState<ConclusionRevision | null>(null);
  const createButtonRef = useRef<HTMLButtonElement>(null);
  const wasCreating = useRef(false);
  useEffect(() => {
    if (wasCreating.current && !source) createButtonRef.current?.focus({ preventScroll: true });
    wasCreating.current = source !== null;
  }, [source]);
  const created = useCallback((conversation: CreatedConversation) => {
    close();
    navigate({ name: 'workspace', projectId: conversation.project_id, conversationId: conversation.id });
  }, [close]);
  const send = useSendConclusion();
  return <TaskModal taskId={taskId} onClose={close} ensureAiConnection={ensureAiConnection} onTaskChanged={controller.taskChanged}
    contentOverride={source ? { title: sharingMessages.title, body: <NewConversationPanel key={source.id} revision={source}
      onBack={() => { controller.dispatch({ type: 'selectRevision', revisionId: source.id }); setSource(null); }} onCreated={created} /> } : undefined}
    renderHeaderActions={(task, nav) => renderTaskHeaderActions ? renderTaskHeaderActions(task) : <SummaryAction controller={controller} onShowResult={nav.showResultTab} />}
    renderResultTab={(task, nav) => renderTaskResultTab ? renderTaskResultTab(task, nav)
      : send.state.target ? <SendConclusion controller={send} /> : <>
        {send.state.notice && <p role="status">{send.state.notice}</p>}
        <TaskResultTab controller={controller} onOpenConclusion={onOpenConclusion} {...conclusionActions} onCreateConversation={conclusionActions?.onCreateConversation ?? setSource} createButtonRef={createButtonRef} sendButtonRef={send.returnFocusRef}
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
      renderConclusion={(revision, controls) => <WorkspaceConclusion revision={revision} projectId={projectId} conversationId={input.conversation_id} sendButtonRef={controls.sendButtonRef}
        actions={{ ...conclusionActions, onSendToConversation: conclusionActions?.onSendToConversation ?? controls.onSendToConversation }} />} />,
  }), [openModal, projectId, conclusionActions]);
  return <AppShell project={header.project} participants={header.participants} {...slots}
    workspaceMenu={slots?.workspaceMenu ?? <>
      <ResultsLibraryMenuButton projectId={projectId} />
      <ResourcesMenuButton projectId={projectId} conversationId={conversationId} />
      <ProjectGraphMenuButton projectId={projectId} onOpenTask={openTask} onSelectConversation={selectConversation} />
    </>}
    conversation={slots?.conversation ?? <Conversation projectId={projectId} conversationId={conversationId} ensureAiConnection={ensureAiConnection} />}
    conversationTree={projectId && <TaskConversationTree projectId={projectId} conversationId={conversationId}
      onSelectConversation={selectConversation} onInitialConversation={selectInitialConversation}
      onOpenTask={openTask} />}
    sharedResults={slots?.sharedResults ?? (conversationId && <ReceivedResults key={conversationId} conversationId={conversationId} onOpen={openReceivedResult} />)}
    taskQueue={projectId && conversationId && <TaskQueue conversationId={conversationId} onOpenTask={openTask} />}
  />;

}
