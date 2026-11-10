import { useEffect, useRef, useState } from 'react';
import { newIdempotencyKey } from '../../lib/api';
import { Button, TextField } from '../../ui';
import { useAuth } from './AuthProvider';
import type { AuthField } from './model';
import { authMessages as m } from './messages';
import './auth.css';

export function LoginView() {
  const [state, dispatch] = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const register = state.mode === 'register';
  const errors = Object.entries(state.fieldErrors).filter((entry): entry is [AuthField, string] => Boolean(entry[1]));
  const fieldLabels = { email: m.email, password: m.password, displayName: m.nickname, confirmPassword: m.confirmPassword };
  useEffect(() => { setShowPassword(false); }, [state.mode]);
  useEffect(() => { if (state.error) errorRef.current?.focus(); }, [state.error]);
  const change = (field: AuthField, value: string) => dispatch({ type: 'fieldChanged', field, value });
  return <main className="app-page auth-page" aria-label={register ? m.register : m.login} data-page="login">
    <section className="auth-card" aria-labelledby="auth-title">
      <div className="auth-brand">{m.brand}</div>
      <h1 id="auth-title">{register ? m.registerTitle : m.title}</h1>
      <p className="auth-description">{register ? m.registerDescription : m.description}</p>
      <form className="auth-form" aria-busy={state.busy} noValidate onSubmit={event => {
        event.preventDefault();
        dispatch({ type: 'submit', key: newIdempotencyKey() });
      }}>
        {register && <TextField id="auth-displayName" label={m.nickname} name="display_name" autoComplete="nickname" maxLength={100}
          value={state.displayName} onChange={event => change('displayName', event.target.value)} required disabled={state.busy}
          error={state.fieldErrors.displayName} hint={m.nicknameHint} autoFocus />}
        <TextField id="auth-email" label={m.email} name="email" type="email" autoComplete="username" placeholder={m.emailPlaceholder}
          autoCapitalize="none" autoCorrect="off" spellCheck={false}
          maxLength={254} value={state.email} onChange={event => change('email', event.target.value)} required disabled={state.busy}
          error={state.fieldErrors.email} autoFocus={!register} />
        <div className="auth-password-field">
          <TextField id="auth-password" label={m.password} name="password" type={showPassword ? 'text' : 'password'}
            autoComplete={register ? 'new-password' : 'current-password'} value={state.password}
            onChange={event => change('password', event.target.value)} required disabled={state.busy}
            error={state.fieldErrors.password} hint={register ? m.passwordHint : undefined} />
          <Button type="button" variant="ghost" size="sm" className="auth-password-toggle" aria-pressed={showPassword}
            disabled={state.busy} onClick={() => setShowPassword(value => !value)}>{showPassword ? m.hidePassword : m.showPassword}</Button>
        </div>
        {register && <TextField id="auth-confirmPassword" label={m.confirmPassword} name="confirm_password" type={showPassword ? 'text' : 'password'}
          autoComplete="new-password" value={state.confirmPassword} onChange={event => change('confirmPassword', event.target.value)}
          required disabled={state.busy} error={state.fieldErrors.confirmPassword} />}
        {state.error && <div ref={errorRef} id="auth-error" className="auth-error" role="alert" tabIndex={-1}>
          <p>{state.error}</p>
          {errors.length > 0 && <ul>{errors.map(([field]) => <li key={field}><a href={`#auth-${field}`} onClick={event => {
            event.preventDefault(); document.getElementById(`auth-${field}`)?.focus();
          }}>{fieldLabels[field]}</a></li>)}</ul>}
        </div>}
        <Button type="submit" size="lg" className="auth-submit" disabled={state.busy}>
          {register ? state.busy ? m.registering : m.registerSubmit : state.busy ? m.loggingIn : m.login}
        </Button>
      </form>
      <div className="auth-switch">
        <span>{register ? m.hasAccount : m.noAccount}</span>
        <Button type="button" variant="link" disabled={state.busy} onClick={() => dispatch({ type: 'modeChanged', mode: register ? 'login' : 'register' })}>
          {register ? m.loginInstead : m.register}
        </Button>
      </div>
    </section>
  </main>;
}
