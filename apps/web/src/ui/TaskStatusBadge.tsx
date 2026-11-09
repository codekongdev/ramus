import type { Task } from '../lib/api/task-contract';
import { Badge, type BadgeVariant } from '@ramus/design-system';

const states: Record<Task['status'], { readonly label: string; readonly variant: BadgeVariant }> = {
  pending: { label: '대기 중', variant: 'secondary' },
  running: { label: '진행 중', variant: 'warning' },
  ready: { label: '준비됨', variant: 'success' },
  failed: { label: '실패', variant: 'destructive' },
  cancelled: { label: '중단됨', variant: 'muted' },
};

export function TaskStatusBadge({ status }: { readonly status: Task['status'] }) {
  const state = states[status];
  return <Badge variant={state.variant}>{state.label}</Badge>;
}
