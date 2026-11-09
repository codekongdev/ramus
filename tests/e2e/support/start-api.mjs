#!/usr/bin/env node
// Playwright webServer command for the API: prepare the E2E database, then serve the API with its
// stderr copied to API_LOG so fixtures can read the development login codes.
import { spawn, spawnSync } from 'node:child_process';
import { createWriteStream, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { apiLogPath, e2eDatabaseUrl } from './env.mjs';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const API_LOG = apiLogPath(REPO_ROOT);

const env = { ...process.env, DATABASE_URL: e2eDatabaseUrl() };
const uv = ['run', '--project', 'apps/api', 'python'];

const prepared = spawnSync('uv', [...uv, 'tests/e2e/support/prepare_db.py'], {
  cwd: REPO_ROOT,
  env,
  stdio: 'inherit',
});
if (prepared.error || prepared.status !== 0) {
  console.error('E2E database preparation failed. Is Postgres running (`pnpm db:up`) and uv installed?');
  process.exit(prepared.status ?? 1);
}

mkdirSync(path.dirname(API_LOG), { recursive: true });
writeFileSync(API_LOG, ''); // one log per run, so a stale code from an earlier run is never reused
const log = createWriteStream(API_LOG, { flags: 'a' });

const api = spawn('uv', [...uv, '-m', 'ramus_api'], { cwd: REPO_ROOT, env, stdio: ['ignore', 'pipe', 'pipe'] });
api.stdout.on('data', (chunk) => process.stdout.write(chunk));
api.stderr.on('data', (chunk) => {
  log.write(chunk);
  process.stderr.write(chunk);
});

const stop = (signal) => api.kill(signal);
process.on('SIGINT', () => stop('SIGINT'));
process.on('SIGTERM', () => stop('SIGTERM'));
api.on('exit', (code, signal) => {
  log.end();
  process.exit(code ?? (signal ? 1 : 0));
});
