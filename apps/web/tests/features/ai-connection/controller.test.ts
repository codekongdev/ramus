import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AiConnectionApi, ConnectionState, ConnectionStatus } from '../../../src/features/ai-connection/api';
import { createAiConnectionController } from '../../../src/features/ai-connection/controller';
import type { ApiResult } from '../../../src/lib/api';

const ok = (status: ConnectionStatus): ApiResult<ConnectionState> => ({ ok: true, status: 200, data: { status } });
const invalid: ApiResult<ConnectionState> = {
  ok: false, error: { kind: 'business', status: 422, code: 'AI_KEY_INVALID', message: 'Invalid key.', details: null },
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

const controllers: ReturnType<typeof createAiConnectionController>[] = [];
function setup(status: ConnectionStatus = 'none') {
  const api: AiConnectionApi = {
    read: vi.fn().mockResolvedValue(ok(status)),
    connect: vi.fn().mockResolvedValue(ok('connected')),
    disconnect: vi.fn().mockResolvedValue(ok('none')),
  };
  const controller = createAiConnectionController(api);
  controllers.push(controller);
  controller.activate();
  return { controller, api };
}

afterEach(async () => {
  controllers.splice(0).forEach((controller) => controller.deactivate());
  await Promise.resolve();
});

describe('AI connection request gating', () => {
  it('coalesces ensure calls and resolves them only after a successful connection', async () => {
    const { controller, api } = setup();
    const first = controller.ensure();
    expect(controller.ensure()).toBe(first);
    await vi.waitFor(() => expect(controller.store.getState()).toMatchObject({ open: true, status: 'none' }));
    expect(api.read).toHaveBeenCalledTimes(1);
    const resolved = vi.fn();
    void first.then(resolved);
    await Promise.resolve();
    expect(resolved).not.toHaveBeenCalled();

    controller.store.dispatch({ type: 'connect', apiKey: '  test-only-key  ' });
    expect(JSON.stringify(controller.store.getState())).not.toContain('test-only-key');
    await expect(first).resolves.toBe(true);
    expect(api.connect).toHaveBeenCalledWith('test-only-key', expect.any(String), expect.any(AbortSignal));
    expect(controller.store.getState()).toMatchObject({ status: 'connected', open: false, phase: 'idle' });
  });

  it('checks the server for every request, including after a previously connected account is disconnected elsewhere', async () => {
    const { controller, api } = setup('connected');
    await expect(controller.ensure()).resolves.toBe(true);
    expect(controller.store.getState().open).toBe(false);
    vi.mocked(api.read).mockResolvedValue(ok('none'));
    const next = controller.ensure();
    await vi.waitFor(() => expect(controller.store.getState().open).toBe(true));
    expect(api.read).toHaveBeenCalledTimes(2);
    controller.cancel();
    await expect(next).resolves.toBe(false);
  });

  it('cancels a pending read and ignores its late connected response', async () => {
    const { controller, api } = setup();
    const read = deferred<ApiResult<ConnectionState>>();
    vi.mocked(api.read).mockReturnValueOnce(read.promise);
    const pending = controller.ensure();
    const signal = vi.mocked(api.read).mock.calls[0]![0];
    controller.cancel();
    await expect(pending).resolves.toBe(false);
    expect(signal.aborted).toBe(true);
    read.resolve(ok('connected'));
    await Promise.resolve();
    expect(controller.store.getState()).toMatchObject({ status: 'unknown', open: false, phase: 'idle' });
  });

  it('does not resume a cancelled request when a successful key validation arrives late', async () => {
    const { controller, api } = setup();
    const save = deferred<ApiResult<ConnectionState>>();
    vi.mocked(api.connect).mockReturnValueOnce(save.promise);
    const pending = controller.ensure();
    await vi.waitFor(() => expect(controller.store.getState().open).toBe(true));
    controller.store.dispatch({ type: 'connect', apiKey: 'test-only-key' });
    controller.cancel();
    await expect(pending).resolves.toBe(false);
    save.resolve(ok('connected'));
    await Promise.resolve();
    expect(controller.store.getState()).toMatchObject({ status: 'none', open: false });

    const retry = controller.ensure();
    await vi.waitFor(() => expect(controller.store.getState().open).toBe(true));
    controller.cancel();
    await expect(retry).resolves.toBe(false);
  });

  it('keeps the caller waiting through an invalid key and allows correction and retry', async () => {
    const { controller, api } = setup();
    vi.mocked(api.connect).mockResolvedValueOnce(invalid);
    const pending = controller.ensure();
    await vi.waitFor(() => expect(controller.store.getState().open).toBe(true));
    controller.store.dispatch({ type: 'connect', apiKey: 'test-only-invalid' });
    await vi.waitFor(() => expect(controller.store.getState().error).toBe('Invalid key.'));
    expect(controller.store.getState()).toMatchObject({ open: true, required: true, phase: 'idle' });
    controller.store.dispatch({ type: 'connect', apiKey: 'test-only-corrected' });
    await expect(pending).resolves.toBe(true);
    expect(api.connect).toHaveBeenCalledTimes(2);
    expect(JSON.stringify(controller.store.getState())).not.toContain('test-only');
  });

  it('does not validate empty or oversized keys or submit a second connection while busy', async () => {
    const { controller, api } = setup();
    controller.manage();
    await vi.waitFor(() => expect(controller.store.getState().phase).toBe('idle'));
    controller.store.dispatch({ type: 'connect', apiKey: '   ' });
    controller.store.dispatch({ type: 'connect', apiKey: 'x'.repeat(513) });
    expect(api.connect).not.toHaveBeenCalled();
    const save = deferred<ApiResult<ConnectionState>>();
    vi.mocked(api.connect).mockReturnValueOnce(save.promise);
    controller.store.dispatch({ type: 'connect', apiKey: 'test-only-key' });
    controller.store.dispatch({ type: 'connect', apiKey: 'test-only-key' });
    expect(api.connect).toHaveBeenCalledTimes(1);
    save.resolve(ok('connected'));
  });

  it('ends a pending request and aborts its read when the provider is removed', async () => {
    const { controller, api } = setup();
    vi.mocked(api.read).mockReturnValueOnce(new Promise(() => undefined));
    const pending = controller.ensure();
    const signal = vi.mocked(api.read).mock.calls[0]![0];
    controller.deactivate();
    await expect(pending).resolves.toBe(false);
    expect(signal.aborted).toBe(true);
  });

  it('preserves a request across StrictMode teardown replay, but cancels when its modal is replaced', async () => {
    const { controller, api } = setup();
    const pending = controller.ensure();
    controller.deactivate();
    controller.activate();
    await vi.waitFor(() => expect(controller.store.getState().open).toBe(true));
    expect(vi.mocked(api.read).mock.calls[0]![0].aborted).toBe(false);
    const unmount = controller.mountDialog();
    unmount();
    const finalUnmount = controller.mountDialog();
    await Promise.resolve();
    expect(controller.store.getState().open).toBe(true);
    finalUnmount();
    await expect(pending).resolves.toBe(false);
    expect(controller.store.getState().open).toBe(false);
  });

  it('reports disconnected after removal and requires a new connection before another request', async () => {
    const { controller, api } = setup('connected');
    controller.manage();
    await vi.waitFor(() => expect(controller.store.getState().status).toBe('connected'));
    controller.store.dispatch({ type: 'disconnect' });
    await vi.waitFor(() => expect(controller.store.getState().status).toBe('none'));
    expect(api.disconnect).toHaveBeenCalledTimes(1);
    vi.mocked(api.read).mockResolvedValue(ok('none'));
    const pending = controller.ensure();
    await vi.waitFor(() => expect(controller.store.getState().required).toBe(true));
    controller.cancel();
    await expect(pending).resolves.toBe(false);
  });
});
