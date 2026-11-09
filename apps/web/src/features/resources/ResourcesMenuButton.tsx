import { useModalHost } from '../../app/modal/ModalHost';
import { Button } from '../../ui';
import { resourcesMessages as m } from './messages';
import { ResourcesModal } from './ResourcesModal';

export type ResourcesMenuButtonProps = {
  readonly projectId: string;
  readonly conversationId?: string;
};

/** Modal id from contracts.md 7장; without an open conversation it is keyed by project. */
export const resourcesModalId = (projectId: string, conversationId?: string): string =>
  conversationId === undefined ? `resources:project:${projectId}` : `resources:${conversationId}`;

/** Left menu entry "스킬·자료" (WF-10 진입). */
export function ResourcesMenuButton({ projectId, conversationId }: ResourcesMenuButtonProps) {
  const { openModal } = useModalHost();
  return (
    <Button
      variant="ghost"
      className="resources-menu-button"
      onClick={() =>
        openModal({
          id: resourcesModalId(projectId, conversationId),
          render: (close) => (
            <ResourcesModal projectId={projectId} conversationId={conversationId ?? null} onClose={close} />
          ),
        })
      }
    >
      {m.menuLabel}
    </Button>
  );
}
