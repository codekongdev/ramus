// Pure part of `pnpm verify`: which checks exist, which to run, and how to judge the outcome.
// No process, file or network access here, so it is unit-tested in plan.test.mjs.

/** Requirement ids checked before a step runs. A missing requirement makes the step SKIP, never PASS. */
export const REQUIREMENTS = {
  uv: 'uv가 PATH에 없습니다. README의 개발 환경을 따라 uv를 설치하세요.',
  postgres: 'PostgreSQL에 연결할 수 없습니다. `pnpm db:up`으로 DB를 실행하세요.',
};

const API = ['uv', 'run', '--project', 'apps/api'];

/** Ordered so that fast static checks fail first. */
export const STEPS = [
  { id: 'web:typecheck', area: 'web', run: { tool: 'pnpm', args: ['--filter', '@ramus/web', 'typecheck'] } },
  { id: 'web:test', area: 'web', run: { tool: 'pnpm', args: ['--filter', '@ramus/web', 'test'] } },
  { id: 'api:lint', area: 'api', requires: ['uv'], run: { tool: 'exec', args: [...API, 'ruff', 'check', 'apps/api'] } },
  {
    id: 'api:unit',
    area: 'api',
    requires: ['uv'],
    run: { tool: 'exec', args: [...API, 'pytest', '-m', 'not integration'] },
  },
  {
    id: 'api:integration',
    area: 'api',
    requires: ['uv', 'postgres'],
    run: { tool: 'exec', args: [...API, 'pytest', '-m', 'integration'] },
  },
  // OpenAPI drift checks from P0-A3, also part of api:unit / web:test, run here under their own name.
  {
    id: 'contract:openapi',
    area: 'contract',
    requires: ['uv'],
    run: { tool: 'exec', args: [...API, 'pytest', 'apps/api/tests/test_openapi_drift.py'] },
  },
  {
    id: 'contract:types',
    area: 'contract',
    run: { tool: 'pnpm', args: ['--filter', '@ramus/web', 'exec', 'vitest', 'run', 'tests/api/schema-drift.test.ts'] },
  },
  // roadmap 9.3 rule 3: screen text lives in each feature's messages.ts, not in .tsx files.
  { id: 'i18n:hangul', area: 'i18n', run: { tool: 'node', args: ['scripts/verify/hangul.mjs'] } },
  { id: 'scripts:test', area: 'scripts', run: { tool: 'node', args: ['--test', 'scripts/verify/*.test.mjs', 'tests/e2e/support/*.test.mjs'] } },
];

export const AREAS = [...new Set(STEPS.map((step) => step.area))];

export function parseArgs(argv) {
  const options = { only: null, allowSkip: false, failFast: false, list: false, help: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--allow-skip') options.allowSkip = true;
    else if (arg === '--fail-fast') options.failFast = true;
    else if (arg === '--list') options.list = true;
    else if (arg === '--help' || arg === '-h') options.help = true;
    else if (arg === '--only' || arg.startsWith('--only=')) {
      const value = arg === '--only' ? argv[++i] : arg.slice('--only='.length);
      if (!value) throw new Error('--only 다음에 영역이나 단계 ID를 적으세요. 예: --only web,api:lint');
      options.only = value.split(',').map((item) => item.trim()).filter(Boolean);
    } else if (arg === '--') {
      // pnpm forwards a literal `--` in some versions; ignore it.
    } else throw new Error(`알 수 없는 옵션: ${arg}`);
  }
  return options;
}

/** `only` accepts areas (`web`) and step ids (`api:lint`). Unknown names are an error, not a silent no-op. */
export function selectSteps(steps, only) {
  if (only === null) return steps;
  const known = new Set([...steps.map((s) => s.area), ...steps.map((s) => s.id)]);
  const unknown = only.filter((name) => !known.has(name));
  if (unknown.length > 0) {
    throw new Error(`알 수 없는 영역·단계: ${unknown.join(', ')}. 사용 가능: ${[...known].join(', ')}`);
  }
  return steps.filter((s) => only.includes(s.area) || only.includes(s.id));
}

/** Requirements of `step` that are not available. */
export function missingRequirements(step, available) {
  return (step.requires ?? []).filter((req) => !available[req]);
}

/**
 * Overall result. FAIL always fails. SKIP fails too unless `allowSkip`, because a check that
 * did not run must never be reported as passed (AGENTS.md).
 */
export function decide(results, { allowSkip }) {
  const counts = { pass: 0, fail: 0, skip: 0 };
  for (const r of results) counts[r.status] += 1;
  const ok = counts.fail === 0 && (allowSkip || counts.skip === 0) && results.length > 0;
  return { ok, counts };
}

const LABEL = { pass: 'PASS', fail: 'FAIL', skip: 'SKIP' };

export function formatSummary(results, decision) {
  const width = Math.max(...results.map((r) => r.id.length), 4);
  const lines = results.map((r) => {
    const seconds = r.ms === undefined ? '' : `${(r.ms / 1000).toFixed(1)}s`;
    const note = r.reason ? `  ${r.reason}` : '';
    return `  ${LABEL[r.status]}  ${r.id.padEnd(width)}  ${seconds.padStart(6)}${note}`;
  });
  const { pass, fail, skip } = decision.counts;
  const verdict = decision.ok
    ? skip > 0
      ? `통과(실행하지 않은 검사 ${skip}개는 통과가 아님)`
      : '통과'
    : fail > 0
      ? '실패'
      : '미완료(실행하지 않은 검사가 있음)';
  return ['', 'verify 결과', ...lines, '', `  ${verdict} · PASS ${pass} · FAIL ${fail} · SKIP ${skip}`, ''].join('\n');
}

/** Minimal `.env` reader: KEY=VALUE lines, `#` comments, optional quotes. Empty values mean unset. */
export function parseDotenv(text) {
  const values = {};
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (line === '' || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (value.length >= 2 && /^(['"]).*\1$/.test(value)) value = value.slice(1, -1);
    if (value !== '') values[key] = value;
  }
  return values;
}

/** Host and port of a SQLAlchemy-style URL (`postgresql+psycopg://user:pw@host:port/db`). */
export function databaseAddress(url) {
  const parsed = new URL(url.replace(/^[a-z0-9+]+:\/\//i, 'postgres://'));
  return { host: parsed.hostname || '127.0.0.1', port: Number(parsed.port || 5432) };
}
