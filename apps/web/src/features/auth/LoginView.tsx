import { useEffect } from 'react';
import { formatNumber } from '../../lib/format';
import { DEFAULT_LOCALE } from '../../lib/locale';
import { newIdempotencyKey } from '../../lib/api';
import { Button, InputOTP, TextField } from '../../ui';
import { useAuth } from './AuthProvider';
import { authMessages as m } from './messages';
import './auth.css';

export function LoginView() {
  const [state, dispatch] = useAuth();
  useEffect(() => {
    dispatch({ type: 'tick', now: Date.now() });
    const timer = window.setInterval(() => dispatch({ type: 'tick', now: Date.now() }), 1000);
    return () => window.clearInterval(timer);
  }, [dispatch]);
  const seconds = Math.max(0, Math.ceil((state.resendAt - state.now) / 1000));
  return <main className="app-page auth-page" aria-label={m.verify} data-page="login">
    <section className="auth-card" aria-labelledby="auth-title">
      <div className="auth-brand">{m.brand}</div>
      <h1 id="auth-title">{state.phase === 'email' ? m.title : m.codeTitle}</h1>
      <p className="auth-description">{state.phase === 'email' ? m.description : m.codeDescription(state.email)}</p>
      <form className="auth-form" aria-busy={state.busy} onSubmit={event => {
        event.preventDefault();
        dispatch({ type: state.phase === 'email' ? 'send' : 'verify', key: newIdempotencyKey() });
      }}>
        {state.phase === 'email' ? <TextField key="email" label={m.email} name="email" type="email" autoComplete="email" placeholder={m.emailPlaceholder} maxLength={254} value={state.email} onChange={event => dispatch({ type: 'emailChanged', email: event.target.value })} required disabled={state.busy} autoFocus /> : <div className="auth-code-field">
          <label htmlFor="auth-code">{m.code}</label>
          <InputOTP key="code" id="auth-code" name="code" label={m.code} value={state.code} onValueChange={code => dispatch({ type: 'codeChanged', code })} disabled={state.busy} aria-describedby={state.error ? 'auth-code-hint auth-error' : 'auth-code-hint'} aria-invalid={state.error ? true : undefined} required autoFocus />
          <p id="auth-code-hint" className="auth-hint">{m.expiry}</p>
        </div>}
        {state.error && <p id="auth-error" className="auth-error" role="alert">{state.error}</p>}
        <Button type="submit" size="lg" className="auth-submit" disabled={state.busy || (state.phase === 'code' && state.code.length !== 6)}>{state.phase === 'email' ? (state.busy ? m.sending : m.send) : (state.busy ? m.verifying : m.verify)}</Button>
        {state.phase === 'code' && <div className="auth-actions">
          <Button variant="ghost" disabled={state.busy || (seconds > 0 && state.retry?.kind !== 'send')} onClick={() => dispatch({ type: 'send', key: newIdempotencyKey() })}>{seconds > 0 && state.retry?.kind !== 'send' ? m.resendWait(formatNumber(seconds, DEFAULT_LOCALE)) : m.resend}</Button>
          <Button variant="ghost" disabled={state.busy} onClick={() => dispatch({ type: 'editEmail' })}>{m.editEmail}</Button>
        </div>}
      </form>
    </section>
  </main>;
}
