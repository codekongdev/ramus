import type { ReactNode } from 'react';
import './app-shell.css';

/**
 * WF-01 three-column workspace layout. Slots only: each feature track fills its own slot
 * from the page (roadmap 4.4 — add slots, never put a feature's content here).
 */
export type AppShellSlots = {
  /** Top bar, left: current project name / switcher (A8). */
  readonly project?: ReactNode;
  /** Top bar, right: participants (A1). */
  readonly participants?: ReactNode;
  /** Left column, top: conversation tree (A2). */
  readonly conversationTree?: ReactNode;
  /** Left column, below the tree: 결과물·스킬·자료·프로젝트 구조 menu (B8·B1·A9). */
  readonly workspaceMenu?: ReactNode;
  /** Center: the open conversation — title, messages, composer (A2). */
  readonly conversation?: ReactNode;
  /** Right column, top: AI task queue (A6). */
  readonly taskQueue?: ReactNode;
  /** Right column, bottom: shared results received by this conversation (B6). */
  readonly sharedResults?: ReactNode;
};

export function AppShell(slots: AppShellSlots) {
  return (
    <div className="app-shell">
      <header className="app-shell__top" aria-label="프로젝트">
        <div className="app-shell__slot" data-slot="project">{slots.project}</div>
        <div className="app-shell__slot" data-slot="participants">{slots.participants}</div>
      </header>
      <nav className="app-shell__left" aria-label="대화 목록">
        <div className="app-shell__slot app-shell__scroll" data-slot="conversation-tree">
          {slots.conversationTree}
        </div>
        <div className="app-shell__slot" data-slot="workspace-menu">{slots.workspaceMenu}</div>
      </nav>
      <main className="app-shell__center" aria-label="대화">
        <div className="app-shell__slot app-shell__fill" data-slot="conversation">{slots.conversation}</div>
      </main>
      <aside className="app-shell__right" aria-label="작업과 공유받은 결과">
        <section className="app-shell__slot app-shell__scroll" data-slot="task-queue" aria-label="작업">
          {slots.taskQueue}
        </section>
        <section className="app-shell__slot app-shell__scroll" data-slot="shared-results" aria-label="공유받은 결과">
          {slots.sharedResults}
        </section>
      </aside>
    </div>
  );
}
