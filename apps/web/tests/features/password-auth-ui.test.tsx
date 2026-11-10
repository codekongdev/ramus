// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../../src/features/auth/AuthProvider';
import { LoginView } from '../../src/features/auth/LoginView';

const api = vi.hoisted(() => ({ GET: vi.fn(), POST: vi.fn() }));
vi.mock('../../src/lib/api/app', () => ({ api }));
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let container: HTMLElement;
let root: Root;
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
beforeEach(async () => {
  api.GET.mockResolvedValue({ error: { error: { code: 'UNAUTHORIZED', message: 'login', details: null } }, response: new Response('{}', { status: 401 }) });
  api.POST.mockReset();
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  await act(async () => root.render(createElement(AuthProvider, null, createElement(LoginView))));
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

describe('password authentication form', () => {
  it('starts with a labeled password-manager-compatible login and has no code step', () => {
    expect(input('email').autocomplete).toBe('username');
    expect(input('password').autocomplete).toBe('current-password');
    expect(input('password').type).toBe('password');
    expect(input('email').labels?.[0].textContent).toBe('이메일');
    expect(input('password').labels?.[0].textContent).toBe('비밀번호');
    expect(container.querySelector('input[name="code"]')).toBeNull();
    expect(button('로그인')).toBeDefined();
    expect(button('회원가입')).toBeDefined();
  });
  it('switches to registration, clears passwords on mode change, and allows explicit visibility', async () => {
    await fill('password', 'Synthetic-test-passphrase');
    await act(async () => button('회원가입').click());
    expect(input('password').value).toBe('');
    expect(input('display_name').labels?.[0].textContent).toBe('닉네임');
    expect(input('confirm_password').labels?.[0].textContent).toBe('비밀번호 확인');
    expect(input('password').autocomplete).toBe('new-password');
    expect(input('confirm_password').autocomplete).toBe('new-password');
    await fill('password', 'Synthetic-test-passphrase');
    await fill('confirm_password', 'Synthetic-test-passphrase');
    await act(async () => button('비밀번호 보기').click());
    expect(input('password').type).toBe('text');
    expect(input('confirm_password').type).toBe('text');
    expect(button('비밀번호 숨기기').getAttribute('aria-pressed')).toBe('true');
    await act(async () => button('로그인으로 돌아가기').click());
    expect(input('password').value).toBe('');
    expect(input('password').type).toBe('password');
  });
  it('shows inline mismatched password feedback and focuses the error summary without requesting', async () => {
    await act(async () => button('회원가입').click());
    await fill('display_name', 'Person');
    await fill('email', 'person@example.test');
    await fill('password', 'Synthetic-test-passphrase');
    await fill('confirm_password', 'A different test passphrase');
    await submit();
    expect(input('confirm_password').getAttribute('aria-invalid')).toBe('true');
    expect(container.textContent).toContain('비밀번호가 일치하지 않습니다.');
    expect(document.activeElement).toBe(container.querySelector('#auth-error'));
    expect(api.POST).not.toHaveBeenCalled();
  });
  it('keeps a rejected login editable and makes no mail request', async () => {
    api.POST.mockResolvedValue({ error: { error: { code: 'AUTH_INVALID_CREDENTIALS', message: '이메일 또는 비밀번호를 확인해 주세요.', details: null } }, response: new Response('{}', { status: 401 }) });
    await fill('email', 'person@example.test');
    await fill('password', 'Synthetic-test-passphrase');
    await submit();
    expect(api.POST).toHaveBeenCalledTimes(1);
    expect(api.POST.mock.calls[0][0]).toBe('/api/auth/login');
    expect(input('email').value).toBe('person@example.test');
    expect(input('password').disabled).toBe(false);
    expect(container.textContent).toContain('이메일 또는 비밀번호를 확인해 주세요.');
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
