// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from '../../src/features/auth/AuthProvider';
import { PasswordSetupButton } from '../../src/features/auth/PasswordSetup';
import { ModalHostProvider } from '../../src/app/modal/ModalHost';

const api = vi.hoisted(() => ({ GET: vi.fn(), PUT: vi.fn(), POST: vi.fn() }));
vi.mock('../../src/lib/api/app', () => ({ api }));
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const me = { account: { id: 'legacy-account', email: 'person@example.test', display_name: 'Person' }, default_project_id: 'project', ai_connection: { status: 'none' } };
const success = (data: unknown) => ({ data, response: new Response('{}') });
let configured = false;
let container: HTMLElement;
let root: Root;
function Harness() {
  const [auth] = useAuth();
  return auth.me ? createElement(PasswordSetupButton, { key: auth.me.account.id, accountId: auth.me.account.id }) : createElement('p', null, 'anonymous');
}
const button = (label: string) => [...container.querySelectorAll('button')].find(node => node.textContent === label)!;
const input = (name: string) => container.querySelector<HTMLInputElement>(`input[name="${name}"]`)!;
async function fill(name: string, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input(name), value);
    input(name).dispatchEvent(new Event('input', { bubbles: true }));
  });
}
async function submit() {
  await act(async () => container.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
}
async function mount() {
  await act(async () => root.render(createElement(AuthProvider, null, createElement(ModalHostProvider, null, createElement(Harness)))));
}
beforeEach(() => {
  configured = false;
  api.GET.mockReset();
  api.GET.mockImplementation(async path => success(path === '/api/me' ? me : { configured }));
  api.PUT.mockReset();
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

describe('current session initial password setup', () => {
  it('only offers setup when the current account has no configured password', async () => {
    configured = true;
    await mount();
    expect(button('비밀번호 설정')).toBeUndefined();
    expect(api.GET.mock.calls.some(call => call[0] === '/api/me/password')).toBe(true);
  });
  it('retries a failed status read before offering setup', async () => {
    let failures = 1;
    api.GET.mockImplementation(async path => path === '/api/me/password' && failures-- > 0
      ? { error: { error: { code: 'SERVICE_UNAVAILABLE', message: 'Unavailable', details: null } }, response: new Response('{}', { status: 503 }) }
      : success(path === '/api/me' ? me : { configured }));
    await mount();
    expect(button('비밀번호 설정')).toBeUndefined();
    await act(async () => button('비밀번호 상태 다시 확인').click());
    expect(button('비밀번호 설정')).toBeDefined();
  });
  it('provides password-manager fields and discards cancelled drafts on reopen', async () => {
    await mount();
    await act(async () => button('비밀번호 설정').click());
    expect(container.querySelector('dialog[open] h2')?.textContent).toBe('비밀번호 설정');
    expect(input('new_password').labels?.[0].textContent).toBe('새 비밀번호');
    expect(input('new_password_confirmation').labels?.[0].textContent).toBe('새 비밀번호 확인');
    expect(input('new_password').autocomplete).toBe('new-password');
    expect(container.querySelector('input[type="email"]')).toBeNull();
    await fill('new_password', 'Synthetic-setup-passphrase');
    await fill('new_password_confirmation', 'Synthetic-setup-passphrase');
    await act(async () => button('비밀번호 보기').click());
    expect(input('new_password').type).toBe('text');
    await act(async () => button('취소').click());
    await act(async () => button('비밀번호 설정').click());
    expect(input('new_password').value).toBe('');
    expect(input('new_password_confirmation').value).toBe('');
    expect(input('new_password').type).toBe('password');
    expect(api.PUT).not.toHaveBeenCalled();
  });
  it('validates confirmation then closes and removes setup after successful save', async () => {
    api.PUT.mockImplementation(async () => { configured = true; return success({ configured: true }); });
    await mount();
    await act(async () => button('비밀번호 설정').click());
    await fill('new_password', 'Synthetic-setup-passphrase');
    await fill('new_password_confirmation', 'A different test passphrase');
    await submit();
    expect(container.textContent).toContain('비밀번호가 일치하지 않습니다.');
    expect(api.PUT).not.toHaveBeenCalled();
    await fill('new_password_confirmation', 'Synthetic-setup-passphrase');
    await submit();
    expect(api.PUT).toHaveBeenCalledTimes(1);
    expect(container.querySelector('dialog')).toBeNull();
    expect(button('비밀번호 설정')).toBeUndefined();
    expect(container.textContent).toContain('비밀번호가 설정되었습니다.');
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
  it('clears the dialog and reloads configuration after PASSWORD_ALREADY_SET', async () => {
    api.PUT.mockImplementation(async () => {
      configured = true;
      return { error: { error: { code: 'PASSWORD_ALREADY_SET', message: 'Already set', details: null } }, response: new Response('{}', { status: 409 }) };
    });
    await mount();
    await act(async () => button('비밀번호 설정').click());
    await fill('new_password', 'Synthetic-setup-passphrase');
    await fill('new_password_confirmation', 'Synthetic-setup-passphrase');
    await submit();
    expect(container.querySelector('dialog')).toBeNull();
    expect(button('비밀번호 설정')).toBeUndefined();
    expect(container.textContent).toContain('비밀번호가 이미 설정되어 있습니다.');
    expect(api.GET.mock.calls.filter(call => call[0] === '/api/me/password')).toHaveLength(2);
  });
  it('clears the dialog when the session expires during a save', async () => {
    api.PUT.mockResolvedValue({ error: { error: { code: 'UNAUTHORIZED', message: 'Expired', details: null } }, response: new Response('{}', { status: 401 }) });
    await mount();
    await act(async () => button('비밀번호 설정').click());
    await fill('new_password', 'Synthetic-setup-passphrase');
    await fill('new_password_confirmation', 'Synthetic-setup-passphrase');
    await submit();
    expect(container.querySelector('dialog')).toBeNull();
    expect(container.textContent).toContain('anonymous');
  });
});
