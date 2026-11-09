import { Button, EmptyState } from '../../ui';
import { navigate } from '../routing/useRoute';

export function NotFoundPage() {
  return (
    <main className="app-page" data-page="not-found">
      <EmptyState
        title="페이지를 찾을 수 없습니다"
        action={<Button onClick={() => navigate({ name: 'workspace' }, { replace: true })}>처음으로</Button>}
      />
    </main>
  );
}
