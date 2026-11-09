import { useEffect, useId, useMemo, useRef } from 'react';
import { api, newIdempotencyKey, type AppApi } from '../../lib/api';
import { useStore } from '../../lib/mvi';
import { Badge, Button, Checkbox, Input, Label, Spinner } from '../../ui';
import { sharingMessages as m } from './messages';
import { makeSendEffectHandler } from './sendEffects';
import { initialSendState, sendReducer } from './sendModel';
import './sharing.css';

export function useSendConclusion(client: AppApi = api) {
  const handle = useMemo(() => makeSendEffectHandler(client), [client]);
  const [state, dispatch] = useStore(sendReducer, initialSendState, handle);
  const returnFocusRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  useEffect(() => {
    if (wasOpen.current && !state.target) returnFocusRef.current?.focus({ preventScroll: true });
    wasOpen.current = state.target !== null;
  }, [state.target]);
  return { state, dispatch, returnFocusRef };
}
export type SendController = ReturnType<typeof useSendConclusion>;
export function SendConclusion({ controller }: { readonly controller: SendController }) {
  const { state, dispatch } = controller;
  const searchId = useId();
  const target = state.target;
  if (!target) return null;
  const busy = state.mutation !== null;
  return <section className="sharing-step" aria-label={m.action}>
    <div className="sharing-actions"><Button variant="ghost" disabled={busy} onClick={() => dispatch({ type: 'back' })}>{m.back}</Button><Badge>{m.version(target.revision.version)}</Badge></div>
    <h3>{m.action}</h3>
    <Label htmlFor={searchId}>{m.search}</Label>
    <Input id={searchId} type="search" maxLength={100} value={state.query} autoFocus placeholder={m.searchHint} disabled={busy}
      onChange={event => dispatch({ type: 'query', query: event.target.value })} />
    {state.selected.length > 0 && <ul className="sharing-chips" aria-label={m.selected}>{state.selected.map(item => {
      const sameName = state.selected.filter(selected => selected.title === item.title).length > 1;
      const name = sameName ? `${item.title} (${item.path.join(' / ') || m.top})` : item.title;
      return <li key={item.id}><Button variant="secondary" disabled={busy} aria-label={m.remove(name)} onClick={() => dispatch({ type: 'toggle', conversation: item })}>{name} <span aria-hidden="true">×</span></Button></li>;
    })}</ul>}
    {state.loading && <p role="status"><Spinner label={m.loading} /> {m.loading}</p>}
    {state.error && <div role="alert"><p>{state.error}</p>{!state.failedMutation && <Button variant="outline" onClick={() => dispatch({ type: 'refresh' })}>{m.retry}</Button>}</div>}
    <ul className="sharing-targets" aria-label={m.targets}>{state.matches.map(item => {
      const checked = state.selected.some(selected => selected.id === item.id);
      return <li key={item.id}><label className="sharing-target">
        <Checkbox checked={checked} disabled={busy || (!checked && state.selected.length >= 20)} onCheckedChange={() => dispatch({ type: 'toggle', conversation: item })} />
        <span className="sharing-target__text"><span className="sharing-title">{item.title}</span><span className="sharing-hint">{item.path.length ? item.path.join(' / ') : m.top}</span></span>
      </label></li>;
    })}</ul>
    {!state.loading && !state.error && state.matches.length === 0 && <p className="sharing-hint">{m.noTargets}</p>}
    {state.selected.length >= 20 && <p className="sharing-hint">{m.selectionLimit}</p>}
    <div className="sharing-actions sharing-actions--end"><Button disabled={busy || state.selected.length === 0} onClick={() => dispatch({ type: 'send', key: newIdempotencyKey() })}>{busy ? m.sending : m.send}</Button></div>
  </section>;
}
