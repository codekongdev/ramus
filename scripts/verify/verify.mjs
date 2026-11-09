#!/usr/bin/env node
// `pnpm verify`: runs lint, typecheck, unit, integration and contract checks in one go.
// Usage: pnpm verify [--only web,api:lint] [--allow-skip] [--fail-fast] [--list]
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { connect } from 'node:net';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  AREAS,
  REQUIREMENTS,
  STEPS,
  databaseAddress,
  decide,
  formatSummary,
  missingRequirements,
  parseArgs,
  parseDotenv,
  selectSteps,
} from './plan.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
// Same default as apps/api/src/ramus_api/settings.py.
const DEFAULT_DATABASE_URL = 'postgresql+psycopg://ramus:ramus-local@127.0.0.1:55432/ramus';

const HELP = `pnpm verify [옵션]

  --only <목록>   영역(${AREAS.join(', ')}) 또는 단계 ID만 실행. 쉼표로 구분
  --allow-skip    실행하지 못한 검사(SKIP)가 있어도 종료 코드 0. 결과에는 SKIP으로 남음
  --fail-fast     첫 실패에서 멈춤
  --list          단계 목록만 출력
`;

function hasCommand(command) {
  const result = spawnSync(command, ['--version'], { stdio: 'ignore' });
  return result.error === undefined && result.status === 0;
}

function databaseUrl() {
  if (process.env.DATABASE_URL) return process.env.DATABASE_URL;
  const envFile = join(ROOT, '.env');
  if (existsSync(envFile)) {
    const fromFile = parseDotenv(readFileSync(envFile, 'utf8')).DATABASE_URL;
    if (fromFile) return fromFile;
  }
  return DEFAULT_DATABASE_URL;
}

function canConnect({ host, port }, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const socket = connect({ host, port });
    const done = (ok) => {
      socket.destroy();
      resolve(ok);
    };
    socket.setTimeout(timeoutMs, () => done(false));
    socket.once('connect', () => done(true));
    socket.once('error', () => done(false));
  });
}

function hasRootScript(name) {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
  return typeof pkg.scripts?.[name] === 'string';
}

/** Only probes what the selected steps need. */
async function probe(steps) {
  const needed = new Set(steps.flatMap((s) => s.requires ?? []));
  const available = {};
  if (needed.has('uv')) available.uv = hasCommand('uv');
  if (needed.has('postgres')) {
    let address = null;
    try {
      address = databaseAddress(databaseUrl());
    } catch {
      address = null;
    }
    available.postgres = address !== null && (await canConnect(address));
  }
  if (needed.has('contract-script')) available['contract-script'] = hasRootScript('contract:check');
  return available;
}

/** pnpm sets npm_execpath when it runs a script; reuse that exact pnpm instead of relying on PATH. */
function commandFor({ tool, args }) {
  if (tool === 'node') return [process.execPath, args];
  if (tool === 'pnpm') {
    const execpath = process.env.npm_execpath;
    if (execpath && /pnpm/.test(execpath)) {
      return /\.(c?js|mjs)$/.test(execpath) ? [process.execPath, [execpath, ...args]] : [execpath, args];
    }
    return ['pnpm', args];
  }
  return [args[0], args.slice(1)];
}

function runStep(step) {
  const [command, args] = commandFor(step.run);
  process.stdout.write(`\n▶ ${step.id}\n`);
  const started = Date.now();
  return new Promise((resolve) => {
    const child = spawn(command, args, { cwd: ROOT, stdio: 'inherit', env: process.env });
    child.once('error', (error) =>
      resolve({ id: step.id, status: 'fail', ms: Date.now() - started, reason: `실행할 수 없음: ${error.message}` }),
    );
    child.once('close', (code, signal) => {
      const ok = code === 0;
      const reason = ok ? undefined : signal ? `신호 ${signal}로 종료` : `종료 코드 ${code}`;
      resolve({ id: step.id, status: ok ? 'pass' : 'fail', ms: Date.now() - started, reason });
    });
  });
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    process.stdout.write(HELP);
    return 0;
  }
  const steps = selectSteps(STEPS, options.only);
  if (options.list) {
    for (const s of steps) process.stdout.write(`${s.id}\t${(s.requires ?? []).join(',')}\n`);
    return 0;
  }

  const available = await probe(steps);
  const results = [];
  for (const step of steps) {
    const missing = missingRequirements(step, available);
    if (missing.length > 0) {
      results.push({ id: step.id, status: 'skip', reason: missing.map((m) => REQUIREMENTS[m]).join(' ') });
      continue;
    }
    const result = await runStep(step);
    results.push(result);
    if (result.status === 'fail' && options.failFast) break;
  }

  const decision = decide(results, { allowSkip: options.allowSkip });
  process.stdout.write(formatSummary(results, decision));
  return decision.ok ? 0 : 1;
}

main().then(
  (code) => {
    process.exitCode = code;
  },
  (error) => {
    process.stderr.write(`verify: ${error.message}\n`);
    process.exitCode = 2;
  },
);
