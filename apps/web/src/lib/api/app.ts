import type { Client } from 'openapi-fetch';
import type { paths } from '../../api/schema';
import { createApiClient } from './client';

export type AppApi = Client<paths>;

/**
 * The app's single API client, typed by the generated contract (contracts.md 7장).
 * EffectHandlers receive it as a dependency so tests can pass a client with a fake fetch:
 *
 *   const handle = makeEffectHandler(api);              // production
 *   const handle = makeEffectHandler(createApiClient<paths>({ fetch: fakeFetch })); // test
 */
export const api: AppApi = createApiClient<paths>();
