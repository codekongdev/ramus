import { useEffect } from 'react';
import { formatNumber } from '../../lib/format';
import { DEFAULT_LOCALE } from '../../lib/locale';
import { api, newIdempotencyKey } from '../../lib/api';
import { useStore } from '../../lib/mvi';
import { Avatar, Button } from '../../ui';
import { ProjectSwitcher } from '../projects';
import { useAuth } from './AuthProvider';
import { PasswordSetupButton } from './PasswordSetup';
import { authMessages as m } from './messages';
import { initialParticipantsState, makeParticipantsEffects, participantsReducer } from './participants';

const effects = makeParticipantsEffects(api);
export function useWorkspaceHeader(projectId: string) {
  const [auth, dispatchAuth] = useAuth();
  const [state, dispatch] = useStore(participantsReducer, initialParticipantsState, effects);
  useEffect(() => {
    const load = () => dispatch({ type: 'load', projectId });
    load();
    const interval = window.setInterval(load, 15000);
    window.addEventListener('focus', load);
    return () => { window.clearInterval(interval); window.removeEventListener('focus', load); };
  }, [dispatch, projectId]);
  useEffect(() => { if (state.unauthorized) dispatchAuth({ type: 'sessionExpired' }); }, [state.unauthorized, dispatchAuth]);
  const account = auth.me?.account;
  return {
    project: <ProjectSwitcher projectId={projectId} projectName={state.projectId === projectId && state.project ? state.project.name : state.loading ? m.projectLoading : m.projectUnavailable} />,
    participants: <div className="auth-participants">
      {state.error && <div className="auth-error" role="alert">{state.error}<Button variant="ghost" onClick={() => dispatch({ type: 'load', projectId })}>{m.retry}</Button></div>}
      {state.projectId === projectId && <details>
        <summary aria-label={m.participants}>{state.loading && state.items.length === 0 ? m.participantsLoading : m.participantsCount(formatNumber(state.items.length, DEFAULT_LOCALE))}</summary>
        <ul aria-label={m.participants}>
          {state.items.map(member => <li key={member.id}><Avatar name={member.display_name} size="xs" /><span>{member.id === account?.id ? m.currentAccount(member.display_name) : member.display_name}</span></li>)}
        </ul>
      </details>}
      {account && <div className="auth-account"><Avatar name={account.display_name} size="xs" /><span className="auth-account-name" title={account.email}>{account.display_name}</span><PasswordSetupButton key={account.id} accountId={account.id} disabled={auth.busy} /><Button variant="ghost" disabled={auth.busy} onClick={() => dispatchAuth({ type: 'logout', key: newIdempotencyKey() })}>{auth.busy ? m.loggingOut : m.logout}</Button></div>}
      {auth.error && <p role="alert" className="auth-error">{auth.error}</p>}
    </div>,
  };
}
