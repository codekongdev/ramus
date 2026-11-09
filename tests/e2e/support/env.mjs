// Shared, side-effect-free settings for the E2E harness (used by the API launcher and fixtures).
// No `import.meta` here: Playwright loads this file from CommonJS-compiled fixtures, so callers
// pass the repository root themselves.
import path from 'node:path';

/** The API launcher appends the server's stderr here; fixtures read login codes from it. */
export function apiLogPath(repoRoot, env = process.env) {
  return env.RAMUS_E2E_API_LOG || path.join(repoRoot, 'artifacts', 'e2e', 'api.log');
}

const DEFAULT_DATABASE_URL = 'postgresql+psycopg://ramus:ramus-local@127.0.0.1:55432/ramus';
export const E2E_DATABASE_NAME = 'ramus_e2e';

/** Same server and credentials as DATABASE_URL, but the dedicated `ramus_e2e` database. */
export function e2eDatabaseUrl(env = process.env) {
  if (env.RAMUS_E2E_DATABASE_URL) return env.RAMUS_E2E_DATABASE_URL;
  const base = env.DATABASE_URL || DEFAULT_DATABASE_URL;
  const match = /^(.*\/)([^/?]+)(\?.*)?$/.exec(base);
  if (!match) throw new Error(`DATABASE_URL has no database name: ${base}`);
  return `${match[1]}${E2E_DATABASE_NAME}${match[3] ?? ''}`;
}

/** Latest login code printed for `email` by the development LoggingMailer (access/infrastructure/mailer.py). */
export function findLoginCode(log, email) {
  const escaped = email.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(`Ramus login code for ${escaped}: (\\d{6})`, 'g');
  let code = null;
  for (const match of log.matchAll(pattern)) code = match[1];
  return code;
}
