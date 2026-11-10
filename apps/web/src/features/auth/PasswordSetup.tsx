import { useEffect, useId, useRef, useState, useSyncExternalStore } from 'react';
import { useModalHost } from '../../app/modal/ModalHost';
import { api, newIdempotencyKey, type AppApi } from '../../lib/api';
import { createStore, type Store } from '../../lib/mvi';
import { Button, Dialog, TextField } from '../../ui';
import { useAuth } from './AuthProvider';
import { passwordSetupMessages as m } from './messages';
import { makePasswordSetupEffects } from './passwordSetupEffects';
import { initialPasswordSetupState, passwordSetupReducer, type PasswordSetupIntent, type PasswordSetupState } from './passwordSetupModel';

type PasswordStore = Store<PasswordSetupState, PasswordSetupIntent>;
export function PasswordSetupButton({ accountId, disabled = false, client = api }: {
  readonly accountId: string; readonly disabled?: boolean; readonly client?: AppApi;
}) {
  const [, dispatchAuth] = useAuth();
  const authRef = useRef(dispatchAuth);
  authRef.current = dispatchAuth;
  const [store] = useState(() => createStore(passwordSetupReducer, initialPasswordSetupState,
    makePasswordSetupEffects(client, () => authRef.current({ type: 'sessionExpired' }))));
  const state = useSyncExternalStore(store.subscribe, store.getState, store.getState);
  const { openModal } = useModalHost();
  useEffect(() => {
    store.activate();
    store.dispatch({ type: 'load' });
    return () => { store.dispatch({ type: 'close' }); store.deactivate(); };
  }, [store]);
  return <div className="auth-password-status">
    {state.notice && <span role="status">{state.notice}</span>}
    {state.status === 'failed' ? <span className="auth-password-status-error" role="alert">
      <span>{state.statusError}</span>
      <Button variant="ghost" disabled={disabled} onClick={() => store.dispatch({ type: 'load' })}>{m.retryStatus}</Button>
    </span> : state.status === 'ready' && state.configured === false && <Button variant="outline" disabled={disabled} onClick={() => {
      store.dispatch({ type: 'open' });
      openModal({ id: `password-setup:${accountId}`, render: close => <PasswordSetupDialog store={store} onClose={close} /> });
    }}>{m.title}</Button>}
  </div>;
}

function PasswordSetupDialog({ store, onClose }: { readonly store: PasswordStore; readonly onClose: () => void }) {
  const state = useSyncExternalStore(store.subscribe, store.getState, store.getState);
  const [visible, setVisible] = useState(false);
  const formId = useId();
  const errorRef = useRef<HTMLDivElement>(null);
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      // StrictMode replays mount effects; only a real removal discards the form.
      queueMicrotask(() => { if (!mounted.current) store.dispatch({ type: 'close' }); });
    };
  }, [store]);
  useEffect(() => { if (!state.open) onClose(); }, [state.open, onClose]);
  useEffect(() => { if (state.error) errorRef.current?.focus(); }, [state.error]);
  const close = () => { store.dispatch({ type: 'close' }); onClose(); };
  const busy = state.pending !== null;
  return <Dialog open={state.open} title={m.title} className="auth-password-dialog" onOpenChange={open => { if (!open) close(); }}
    footer={<>
      <Button variant="outline" onClick={close}>{m.cancel}</Button>
      <Button type="submit" form={formId} disabled={busy}>{busy ? m.saving : m.save}</Button>
    </>}>
    <p className="auth-description">{m.description}</p>
    <form id={formId} className="auth-form" noValidate aria-busy={busy} onSubmit={event => {
      event.preventDefault(); store.dispatch({ type: 'save', key: newIdempotencyKey() });
    }}>
      <div className="auth-password-field">
        <TextField label={m.password} name="new_password" type={visible ? 'text' : 'password'} autoComplete="new-password" required autoFocus
          value={state.password} onChange={event => store.dispatch({ type: 'fieldChanged', field: 'password', value: event.target.value })}
          disabled={busy} error={state.passwordError} hint={m.passwordHint} />
        <Button type="button" variant="ghost" size="sm" className="auth-password-toggle" aria-pressed={visible}
          disabled={busy} onClick={() => setVisible(value => !value)}>{visible ? m.hidePassword : m.showPassword}</Button>
      </div>
      <TextField label={m.confirmation} name="new_password_confirmation" type={visible ? 'text' : 'password'} autoComplete="new-password" required
        value={state.confirmation} onChange={event => store.dispatch({ type: 'fieldChanged', field: 'confirmation', value: event.target.value })}
        disabled={busy} error={state.confirmationError} />
      {state.error && <div ref={errorRef} className="auth-error" role="alert" tabIndex={-1}>{state.error}</div>}
    </form>
  </Dialog>;
}
