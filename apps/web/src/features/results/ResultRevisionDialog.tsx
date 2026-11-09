import { useEffect, useMemo } from 'react';
import { api, type AppApi } from '../../lib/api';
import { useStore } from '../../lib/mvi';
import { Button, Dialog, Spinner } from '../../ui';
import { ConclusionView, type ConclusionActions } from './ConclusionView';
import { makeConclusionEffectHandler } from './conclusionEffects';
import { conclusionReducer, initialConclusionState } from './conclusionModel';
import { resultMessages as messages } from './messages';

export type ResultRevisionDialogProps = ConclusionActions & {
  readonly revisionId: string;
  readonly onClose: () => void;
  readonly client?: AppApi;
};

/** Received conclusions and task results use the same fixed-revision reader. */
export function ResultRevisionDialog({ revisionId, onClose, client = api, ...actions }: ResultRevisionDialogProps) {
  const handler = useMemo(() => makeConclusionEffectHandler(client), [client]);
  const [state, dispatch] = useStore(conclusionReducer, () => initialConclusionState(revisionId), handler);
  useEffect(() => { dispatch({ type: 'open', revisionId }); }, [dispatch, revisionId]);
  // Do not display the previous target during the render before its open intent runs.
  const current = state.revisionId === revisionId;
  const revision = current ? state.revision : null;
  return <Dialog open onOpenChange={open => { if (!open) onClose(); }}
    title={revision?.title ?? messages.viewConclusion} className="conclusion-dialog">
    {(!current || state.loading) && <p role="status"><Spinner label={messages.loadingConclusion} /> {messages.loadingConclusion}</p>}
    {current && state.error && <div className="task-result__error" role="alert">
      <p>{state.error}</p><Button variant="outline" onClick={() => dispatch({ type: 'retry' })}>{messages.retryLoad}</Button>
    </div>}
    {revision && <ConclusionView revision={revision} {...actions} />}
  </Dialog>;
}
