import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import openapiTS, { astToString, COMMENT_HEADER } from 'openapi-typescript';
import { describe, expect, it } from 'vitest';

// Same input, output and default options as `pnpm --filter @ramus/web gen:api` (the openapi-typescript CLI).
const OPENAPI_URL = new URL('../../../../contracts/openapi.json', import.meta.url);
const SCHEMA_URL = new URL('../../src/api/schema.d.ts', import.meta.url);
const REGENERATE_HINT =
  'src/api/schema.d.ts is out of date with contracts/openapi.json. Run `pnpm gen:api` from the repository root and commit the result.';

describe('generated API types', () => {
  it('match contracts/openapi.json', async () => {
    const ast = await openapiTS(OPENAPI_URL, { silent: true });
    const generated = `${COMMENT_HEADER}${astToString(ast)}`;
    const committed = readFileSync(fileURLToPath(SCHEMA_URL), 'utf8');
    expect(committed === generated, REGENERATE_HINT).toBe(true);
  });
});
