import createClient, { type Client, type Middleware } from 'openapi-fetch';
import { toHttpError, toThrownError, type ApiResult } from './result';

export const IDEMPOTENCY_HEADER = 'Idempotency-Key';

const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export interface ApiClientOptions {
  /** Defaults to same-origin; the Vite dev server proxies `/api` to the backend. */
  baseUrl?: string;
  fetch?: typeof globalThis.fetch;
  newIdempotencyKey?: () => string;
}

/**
 * Adds an `Idempotency-Key` to every mutating request that doesn't carry one (부록 A:
 * 모든 변경 요청은 Idempotency-Key 헤더를 받는다). A generated key only protects against
 * the network layer replaying one request; to retry a user action safely, create the key
 * once with `newIdempotencyKey()` and pass it in `headers` on every attempt.
 */
export function idempotencyMiddleware(newKey: () => string): Middleware {
  return {
    onRequest({ request }) {
      if (!MUTATING_METHODS.has(request.method.toUpperCase())) return undefined;
      if (request.headers.has(IDEMPOTENCY_HEADER)) return undefined;
      request.headers.set(IDEMPOTENCY_HEADER, newKey());
      return request;
    },
  };
}

export const newIdempotencyKey = (): string => crypto.randomUUID();

/**
 * Typed client over the generated OpenAPI `paths` (contracts/openapi.json →
 * src/api/schema.d.ts, produced by P0-A3). Session auth rides on the httpOnly cookie.
 */
export function createApiClient<Paths extends {}>(options: ApiClientOptions = {}): Client<Paths> {
  const client = createClient<Paths>({
    baseUrl: options.baseUrl ?? '',
    credentials: 'same-origin',
    ...(options.fetch ? { fetch: options.fetch } : {}),
  });
  client.use(idempotencyMiddleware(options.newIdempotencyKey ?? newIdempotencyKey));
  return client;
}

/**
 * Normalises an openapi-fetch call into `ApiResult`, so EffectHandlers never throw for
 * expected failures:
 *
 *   const result = await toResult(api.GET('/api/me', { signal }));
 *   dispatch(result.ok ? { type: 'loaded', me: result.data } : { type: 'failed', error: result.error });
 */
export async function toResult<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<ApiResult<T>> {
  try {
    const { data, error, response } = await call;
    if (!response.ok) return { ok: false, error: toHttpError(response.status, error) };
    return { ok: true, data: data as T, status: response.status };
  } catch (cause) {
    return { ok: false, error: toThrownError(cause) };
  }
}
