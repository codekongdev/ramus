import { useEffect, useId, useRef } from 'react';
import { ChevronDown, Plus } from 'lucide-react';
import { navigate } from '../../app/routing/useRoute';
import { api, newIdempotencyKey } from '../../lib/api';
import { useStore } from '../../lib/mvi';
import { Button, Dialog, Input, Label } from '../../ui';
import { useAuth } from '../auth/AuthProvider';
import { makeProjectsEffects } from './effects';
import { projectMessages as m } from './messages';
import { initialProjectsState, projectsReducer } from './model';
import './projects.css';

const effects = makeProjectsEffects(api, projectId => navigate({ name: 'workspace', projectId }));

export function ProjectSwitcher({ projectId, projectName }: { readonly projectId: string; readonly projectName: string }) {
  const [state, dispatch] = useStore(projectsReducer, initialProjectsState, effects);
  const [, dispatchAuth] = useAuth();
  const inputId = useId();
  const hintId = useId();
  const searchRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (state.unauthorized) dispatchAuth({ type: 'sessionExpired' });
  }, [state.unauthorized, dispatchAuth]);
  useEffect(() => {
    if (!state.open) return;
    const input = (state.mode === 'list' ? searchRef : nameRef).current;
    let cancelled = false;
    // Native showModal() can run again in StrictMode; focus after that replay.
    queueMicrotask(() => {
      if (!cancelled && input?.isConnected) input.focus({ preventScroll: true });
    });
    return () => { cancelled = true; };
  }, [state.open, state.mode]);
  const query = state.query.trim().toLocaleLowerCase();
  const items = state.items.filter(project => project.name.toLocaleLowerCase().includes(query));

  return <>
    <Button variant="ghost" className="project-switcher-trigger" aria-label={m.switchLabel(projectName)}
      aria-haspopup="dialog" aria-expanded={state.open} onClick={() => dispatch({ type: 'open' })}>
      <span className="project-switcher-name">{projectName}</span><ChevronDown size={16} aria-hidden="true" />
    </Button>
    {state.open && <Dialog open onOpenChange={open => { if (!open) dispatch({ type: 'close' }); }} title={state.mode === 'list' ? m.switch : m.create} className="projects-dialog">
      {state.mode === 'list' ? <div className="projects-list-view">
        <div className="projects-field">
          <Label htmlFor={inputId}>{m.search}</Label>
          <Input ref={searchRef} id={inputId} type="search" value={state.query} onChange={event => dispatch({ type: 'queryChanged', value: event.target.value })} />
        </div>
        {state.loading && <p role="status">{m.loading}</p>}
        {state.listError && <div role="alert" className="projects-error">{state.listError}<Button variant="ghost" onClick={() => dispatch({ type: 'reload' })}>{m.retry}</Button></div>}
        {!state.loading && !state.listError && items.length === 0 && <p role="status">{query ? m.noMatches : m.empty}</p>}
        <ul className="projects-list" aria-label={m.switch}>
          {items.map(project => <li key={project.id}>
            <Button variant="ghost" className="projects-option" aria-label={m.openProject(project.name)} aria-current={project.id === projectId ? 'true' : undefined}
              onClick={() => dispatch(project.id === projectId ? { type: 'close' } : { type: 'select', projectId: project.id })}>
              <span className="projects-option-name">{project.name}</span>
              <span className="projects-option-meta">{project.id === projectId ? m.current : project.is_shared_sample ? m.sample : null}</span>
            </Button>
          </li>)}
        </ul>
        <Button variant="secondary" className="projects-new" onClick={() => dispatch({ type: 'showCreate' })}><Plus size={16} aria-hidden="true" />{m.create}</Button>
      </div> : <form className="projects-form" aria-busy={state.creating} onSubmit={event => { event.preventDefault(); dispatch({ type: 'submit', key: newIdempotencyKey() }); }}>
        <div className="projects-field">
          <Label htmlFor={inputId}>{m.name}</Label>
          <Input ref={nameRef} id={inputId} value={state.name} disabled={state.creating} aria-invalid={Boolean(state.nameError)} aria-describedby={hintId}
            onChange={event => dispatch({ type: 'nameChanged', value: event.target.value })} />
          <p id={hintId} className={state.nameError ? 'projects-error' : 'projects-hint'}>{state.nameError ?? m.nameHint}</p>
        </div>
        {state.createError && <p role="alert" className="projects-error">{state.createError}</p>}
        <div className="projects-form-actions">
          <Button type="button" variant="ghost" disabled={state.creating} onClick={() => dispatch({ type: 'showList' })}>{m.cancel}</Button>
          <Button type="submit" disabled={state.creating}>{state.creating ? m.creating : m.submit}</Button>
        </div>
      </form>}
    </Dialog>}
  </>;
}
