import { KeyRound } from 'lucide-react';
import { Button, Spinner } from '../../ui';
import { useAiConnection } from './AiConnectionProvider';
import { aiConnectionMessages as messages } from './messages';

export function AiConnectionButton() {
  const { manage, status, busy } = useAiConnection();
  return <Button variant="outline" size="sm" onClick={manage} aria-disabled={busy} aria-busy={busy}>
    {busy ? <Spinner /> : <KeyRound size={16} aria-hidden="true" />}
    {messages.title}{status !== 'unknown' && <span className="ai-connection-button-status">{messages.status[status]}</span>}
  </Button>;
}
