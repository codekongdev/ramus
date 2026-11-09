import { useModalHost } from '../../app/modal/ModalHost';
import { Button } from '../../ui';
import { resultsLibraryMessages as m } from './messages';
import { ResultsLibraryModal } from './ResultsLibraryModal';

export function ResultsLibraryMenuButton({ projectId }: { readonly projectId: string }) {
  const { openModal } = useModalHost();
  return <Button variant="ghost" className="results-library-menu-button" onClick={() => openModal({
    id: `results-library:${projectId}`,
    render: close => <ResultsLibraryModal projectId={projectId} onClose={close} />,
  })}>{m.menu}</Button>;
}
