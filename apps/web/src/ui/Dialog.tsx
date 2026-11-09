import { createContext, useContext, useEffect, useId, useRef, type ReactNode } from 'react';
import { ButtonV2 } from '@ramus/design-system';
import { UI_CONTRAST, UI_THEME } from './theme';

const DialogVisibilityContext = createContext(true);

/** Hides an interrupted modal without unmounting its form or cancelling its effect store. */
export function DialogVisibilityProvider({ visible, children }: {
  readonly visible: boolean;
  readonly children: ReactNode;
}) {
  const parentVisible = useContext(DialogVisibilityContext);
  return <DialogVisibilityContext.Provider value={parentVisible && visible}>{children}</DialogVisibilityContext.Provider>;
}

export type DialogProps = {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly title: string;
  readonly headerActions?: ReactNode;
  readonly children: ReactNode;
  readonly footer?: ReactNode;
  readonly className?: string;
};

/**
 * General-purpose modal on a native <dialog>, styled with the kit's `h-dialog` classes.
 * Controlled: `open` drives showModal()/close(); Escape and the close button only request
 * `onOpenChange(false)`, so the parent stays the source of truth.
 */
export function Dialog({ open, onOpenChange, title, headerActions, children, footer, className }: DialogProps) {
  const visible = useContext(DialogVisibilityContext);
  const effectiveOpen = open && visible;
  const titleId = useId();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const focusedInside = useRef<HTMLElement | null>(null);
  const latest = useRef({ open: effectiveOpen, onOpenChange });
  useEffect(() => {
    latest.current = { open: effectiveOpen, onOpenChange };
  });

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || !effectiveOpen) return;
    const active = dialog.ownerDocument.activeElement;
    const opener = active instanceof HTMLElement ? active : null;
    const restoreInside = focusedInside.current;
    if (!dialog.open) dialog.showModal();
    if (restoreInside?.isConnected && dialog.contains(restoreInside)) restoreInside.focus({ preventScroll: true });
    return () => {
      // Runs on controlled close, unmount and StrictMode effect replay.
      if (dialog.open) dialog.close();
      if (opener?.isConnected) opener.focus({ preventScroll: true });
    };
  }, [effectiveOpen]);

  const requestClose = () => {
    if (latest.current.open) latest.current.onOpenChange(false);
  };

  return (
    <dialog
      ref={dialogRef}
      data-theme={UI_THEME}
      data-contrast={UI_CONTRAST}
      className={['ramus', 'h-dialog', 'ui-dialog', className].filter(Boolean).join(' ')}
      aria-labelledby={titleId}
      onFocusCapture={event => { if (event.target instanceof HTMLElement) focusedInside.current = event.target; }}
      hidden={!visible}
      onCancel={(event) => {
        event.preventDefault();
        requestClose();
      }}
      onClose={(event) => {
        // Ignore the queued close event of a dialog that was reopened or closed by the parent.
        if (!event.currentTarget.open && !event.currentTarget.hidden) requestClose();
      }}
    >
      {open && (
        <>
          <header className="h-dialog-header">
            <h2 className="h-dialog-title" id={titleId}>{title}</h2>
            <div className="ui-dialog-actions">
              {headerActions}
              <ButtonV2 variant="ghost" onClick={requestClose}>닫기</ButtonV2>
            </div>
          </header>
          <div className="h-dialog-body">{children}</div>
          {footer && <footer className="ui-dialog-footer">{footer}</footer>}
        </>
      )}
    </dialog>
  );
}
