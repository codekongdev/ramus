import { useEffect, useId, useRef, useState, useSyncExternalStore, type FormEvent } from 'react';
import { Check, Eye, EyeOff, KeyRound, ShieldCheck } from 'lucide-react';
import { Alert, Badge, Button, Dialog, Input, Label, Spinner } from '../../ui';
import { useAiConnectionController } from './AiConnectionProvider';
import { aiConnectionMessages as messages } from './messages';

export function AiConnectionDialog() {
  const controller = useAiConnectionController();
  const state = useSyncExternalStore(controller.store.subscribe, controller.store.getState, controller.store.getState);
  // Secrets stay in the mounted form, never in a shared store, URL or persistent browser storage.
  const [key, setKey] = useState('');
  const [visible, setVisible] = useState(false);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const busy = state.phase !== 'idle';
  const hasConnection = state.status === 'connected' || state.status === 'invalid';

  useEffect(() => controller.mountDialog(), [controller]);
  useEffect(() => { setKey(''); setVisible(false); }, [state.clearKey]);
  useEffect(() => {
    if (!busy && (state.status === 'none' || state.status === 'invalid' || state.error)) inputRef.current?.focus();
  }, [busy, state.status, state.error]);

  const connect = (event: FormEvent) => {
    event.preventDefault();
    controller.store.dispatch({ type: 'connect', apiKey: key });
  };
  const cancel = () => controller.cancel();

  return (
    <Dialog open={state.open} title={state.required ? messages.requiredTitle : messages.title}
      className="ai-connection-dialog" onOpenChange={(open) => { if (!open) cancel(); }}
      footer={<>
        {hasConnection && !confirmDisconnect && <Button variant="ghost" disabled={busy}
          onClick={() => setConfirmDisconnect(true)}>{messages.disconnect}</Button>}
        <Button variant="outline" onClick={cancel}>{state.notice && !state.required ? messages.done : messages.cancel}</Button>
        {!confirmDisconnect && <Button type="submit" form={`${inputId}-form`} disabled={busy || key.trim().length === 0}>
          {state.phase === 'saving' ? <><Spinner aria-hidden="true" />{messages.saving}</> : state.required
            ? messages.connectAndContinue : hasConnection ? messages.replace : messages.connect}
        </Button>}
      </>}
    >
      <div className="ai-connection-content">
        <p className="ai-connection-description">{messages.description}</p>
        {state.required && <p className="ai-connection-pending">{messages.pendingRequest}</p>}
        <div className="ai-connection-provider">
          <span className="ai-connection-provider-name"><KeyRound size={20} aria-hidden="true" />{messages.provider}</span>
          <Badge variant={state.status === 'connected' ? 'success' : 'muted'}>
            {state.status === 'connected' && <Check size={14} aria-hidden="true" />}{messages.status[state.status]}
          </Badge>
        </div>
        {state.phase === 'checking' && <p role="status" className="ai-connection-progress"><Spinner aria-hidden="true" />{messages.checking}</p>}
        {state.notice && <p role="status" className="ai-connection-notice">{state.notice}</p>}
        {state.status === 'invalid' && !state.error && <Alert>{messages.invalid}</Alert>}
        {state.error && <Alert variant="destructive" id={`${inputId}-error`}>
          {state.error}
          {state.status === 'unknown' && <Button variant="link" disabled={busy}
            onClick={() => controller.store.dispatch({ type: 'retry' })}>{messages.retry}</Button>}
        </Alert>}
        {confirmDisconnect ? <section className="ai-connection-confirm" aria-label={messages.disconnectTitle}>
          <strong>{messages.disconnectTitle}</strong>
          <p>{messages.disconnectDescription}</p>
          <div className="ai-connection-confirm-actions">
            <Button variant="outline" disabled={busy} onClick={() => setConfirmDisconnect(false)}>{messages.keepConnection}</Button>
            <Button variant="destructive" disabled={busy} onClick={() => {
              controller.store.dispatch({ type: 'disconnect' });
              setConfirmDisconnect(false);
            }}>{state.phase === 'removing' ? messages.removing : messages.disconnect}</Button>
          </div>
        </section> : <form id={`${inputId}-form`} onSubmit={connect} className="ai-connection-form" aria-busy={busy}>
          <Label htmlFor={inputId}>{hasConnection ? messages.replacementLabel : messages.keyLabel}</Label>
          <div className="ai-connection-key">
            <Input ref={inputRef} id={inputId} type={visible ? 'text' : 'password'} value={key}
              onChange={(event) => setKey(event.target.value)} autoComplete="off" autoCapitalize="none"
              spellCheck={false} maxLength={512} disabled={busy} placeholder={messages.keyPlaceholder}
              aria-invalid={Boolean(state.error)} aria-describedby={`${inputId}-help${state.error ? ` ${inputId}-error` : ''}`} />
            <Button variant="ghost" size="icon" disabled={busy} aria-label={visible ? messages.hideKey : messages.showKey}
              aria-pressed={visible} onClick={() => setVisible(!visible)}>
              {visible ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
            </Button>
          </div>
          <p id={`${inputId}-help`} className="ai-connection-help">{messages.keyHelp}</p>
          <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer">{messages.keyLink}</a>
        </form>}
        {state.phase === 'removing' && <p role="status" className="ai-connection-progress"><Spinner aria-hidden="true" />{messages.removing}</p>}
        <div className="ai-connection-privacy"><ShieldCheck size={18} aria-hidden="true" /><p>{messages.privacy}</p></div>
        <p className="ai-connection-help">{messages.optional}</p>
      </div>
    </Dialog>
  );
}
