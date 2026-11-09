import { useEffect, useState } from 'react';
import type { AppApi } from '../../lib/api';
import { formatDateTime } from '../../lib/format';
import { DEFAULT_LOCALE } from '../../lib/locale';
import { useStore } from '../../lib/mvi';
import { useProjectEventListener, useResyncListener } from '../../lib/realtime';
import { Alert, Badge, Button, Dialog, EmptyState, Spinner } from '../../ui';
import { makeResultsLibraryEffects } from './effects';
import { resultsLibraryMessages as m } from './messages';
import { initialResultsLibraryState, resultsLibraryReducer } from './model';
import './results-library.css';

export type ResultsLibraryModalProps = {
  readonly projectId: string;
  readonly onClose: () => void;
  readonly client?: AppApi;
};

export function ResultsLibraryModal(props: ResultsLibraryModalProps) {
  return <ProjectResults key={props.projectId} {...props} />;
}

function ProjectResults({ projectId, onClose, client }: ResultsLibraryModalProps) {
  const [effects] = useState(() => makeResultsLibraryEffects(client));
  const [state, dispatch] = useStore(resultsLibraryReducer, () => initialResultsLibraryState(projectId), effects);
  useEffect(() => { dispatch({ type: 'refresh' }); }, [dispatch]);
  useProjectEventListener(event => dispatch({ type: 'serverEvent', event }));
  useResyncListener(() => dispatch({ type: 'refresh' }));

  return <Dialog open title={m.title} className="results-library-modal" onOpenChange={open => { if (!open) onClose(); }}>
    <div className="results-library-content">
      <div className="results-library-toolbar">
        <p>{m.description}</p>
        <Button variant="outline" disabled={state.status === 'loading'} onClick={() => dispatch({ type: 'refresh' })}>{m.refresh}</Button>
      </div>
      {state.status === 'loading' ? <div className="results-library-status" role="status"><Spinner /><span>{m.loading}</span></div>
        : state.status === 'failed' ? <Alert variant="destructive">
          <p>{state.error}</p><Button variant="link" onClick={() => dispatch({ type: 'refresh' })}>{m.retry}</Button>
        </Alert>
          : state.items.length === 0 ? <EmptyState title={m.empty} description={m.emptyHint} />
            : <ul className="results-library-list" aria-label={m.list}>
              {state.items.map(item => <li key={item.result_id} className="results-library-row" data-result-id={item.result_id}>
                <div className="results-library-heading"><h3>{item.title}</h3><Badge variant="secondary">{m.version(item.latest_version)}</Badge></div>
                <dl className="results-library-meta">
                  <div><dt>{m.source}</dt><dd>{item.source_conversation_title}</dd></div>
                  <div><dt>{m.savedAt}</dt><dd><time dateTime={item.updated_at}>{formatDateTime(item.updated_at, DEFAULT_LOCALE)}</time></dd></div>
                </dl>
              </li>)}
            </ul>}
    </div>
  </Dialog>;
}
