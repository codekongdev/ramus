import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { apiLogPath, e2eDatabaseUrl, findLoginCode } from './env.mjs';

describe('findLoginCode', () => {
  const line = (email, code) =>
    `INFO:     [DEV MAIL - not sent] Ramus login code for ${email}: ${code} (valid for 10 minutes)\n`;

  it('returns the latest code for the email', () => {
    const log = line('a@example.test', '111111') + line('b@example.test', '222222') + line('a@example.test', '333333');
    assert.equal(findLoginCode(log, 'a@example.test'), '333333');
    assert.equal(findLoginCode(log, 'b@example.test'), '222222');
  });

  it('matches case-insensitively by normalizing the email and treats dots literally', () => {
    const log = line('mason@example.test', '123456');
    assert.equal(findLoginCode(log, 'Mason@Example.test'), '123456');
    assert.equal(findLoginCode(log, 'mason@exampleXtest'), null);
  });

  it('returns null when there is no code', () => {
    assert.equal(findLoginCode('', 'a@example.test'), null);
  });
});

describe('e2eDatabaseUrl', () => {
  it('swaps only the database name', () => {
    assert.equal(
      e2eDatabaseUrl({ DATABASE_URL: 'postgresql+psycopg://u:p@127.0.0.1:55432/ramus' }),
      'postgresql+psycopg://u:p@127.0.0.1:55432/ramus_e2e',
    );
    assert.equal(e2eDatabaseUrl({ DATABASE_URL: 'postgresql://u@h/db?sslmode=disable' }), 'postgresql://u@h/ramus_e2e?sslmode=disable');
  });

  it('defaults to the local compose database and honors an explicit override', () => {
    assert.match(e2eDatabaseUrl({}), /127\.0\.0\.1:55432\/ramus_e2e$/);
    assert.equal(e2eDatabaseUrl({ RAMUS_E2E_DATABASE_URL: 'postgresql://x/ramus_e2e_ci' }), 'postgresql://x/ramus_e2e_ci');
  });
});

describe('apiLogPath', () => {
  it('lives under artifacts unless overridden', () => {
    assert.equal(apiLogPath('/repo', {}), '/repo/artifacts/e2e/api.log');
    assert.equal(apiLogPath('/repo', { RAMUS_E2E_API_LOG: '/tmp/api.log' }), '/tmp/api.log');
  });
});
