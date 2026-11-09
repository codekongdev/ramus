import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  AREAS,
  STEPS,
  databaseAddress,
  decide,
  formatSummary,
  missingRequirements,
  parseArgs,
  parseDotenv,
  selectSteps,
} from './plan.mjs';

describe('STEPS', () => {
  it('covers lint, typecheck, unit, integration and contract checks', () => {
    assert.deepEqual(
      STEPS.map((s) => s.id),
      ['web:typecheck', 'web:test', 'api:lint', 'api:unit', 'api:integration', 'contract', 'scripts:test'],
    );
  });

  it('has unique ids', () => {
    assert.equal(new Set(STEPS.map((s) => s.id)).size, STEPS.length);
  });

  it('separates unit and integration tests by the pytest marker', () => {
    const args = (id) => STEPS.find((s) => s.id === id).run.args;
    assert.deepEqual(args('api:unit').slice(-2), ['-m', 'not integration']);
    assert.deepEqual(args('api:integration').slice(-2), ['-m', 'integration']);
  });
});

describe('parseArgs', () => {
  it('defaults', () => {
    assert.deepEqual(parseArgs([]), { only: null, allowSkip: false, failFast: false, list: false, help: false });
  });

  it('reads flags and --only in both forms', () => {
    assert.deepEqual(parseArgs(['--only', 'web, api:lint', '--allow-skip']).only, ['web', 'api:lint']);
    assert.deepEqual(parseArgs(['--only=api']).only, ['api']);
    assert.equal(parseArgs(['--fail-fast']).failFast, true);
    assert.equal(parseArgs(['--', '--list']).list, true);
  });

  it('rejects unknown options and an empty --only', () => {
    assert.throws(() => parseArgs(['--nope']), /알 수 없는 옵션/);
    assert.throws(() => parseArgs(['--only']), /--only/);
  });
});

describe('selectSteps', () => {
  it('returns every step without a filter', () => {
    assert.equal(selectSteps(STEPS, null), STEPS);
  });

  it('selects by area and by id, keeping order', () => {
    assert.deepEqual(
      selectSteps(STEPS, ['api:lint', 'web']).map((s) => s.id),
      ['web:typecheck', 'web:test', 'api:lint'],
    );
  });

  it('fails on an unknown name instead of running nothing', () => {
    assert.throws(() => selectSteps(STEPS, ['wbe']), /알 수 없는 영역·단계: wbe/);
  });

  it('knows every area', () => {
    assert.deepEqual(AREAS, ['web', 'api', 'contract', 'scripts']);
  });
});

describe('missingRequirements', () => {
  const step = { id: 'x', requires: ['uv', 'postgres'] };
  it('lists unavailable requirements', () => {
    assert.deepEqual(missingRequirements(step, { uv: true, postgres: false }), ['postgres']);
    assert.deepEqual(missingRequirements(step, {}), ['uv', 'postgres']);
    assert.deepEqual(missingRequirements({ id: 'y' }, {}), []);
  });
});

describe('decide', () => {
  const pass = { id: 'a', status: 'pass' };
  const fail = { id: 'b', status: 'fail' };
  const skip = { id: 'c', status: 'skip' };

  it('passes only when everything passed', () => {
    assert.equal(decide([pass], { allowSkip: false }).ok, true);
    assert.equal(decide([pass, fail], { allowSkip: true }).ok, false);
  });

  it('treats a skipped check as not passed unless allowed', () => {
    assert.equal(decide([pass, skip], { allowSkip: false }).ok, false);
    assert.equal(decide([pass, skip], { allowSkip: true }).ok, true);
  });

  it('does not pass when nothing ran', () => {
    assert.equal(decide([], { allowSkip: true }).ok, false);
  });

  it('counts each status', () => {
    assert.deepEqual(decide([pass, fail, skip, skip], { allowSkip: false }).counts, { pass: 1, fail: 1, skip: 2 });
  });
});

describe('formatSummary', () => {
  it('shows every step and never calls a skip a pass', () => {
    const results = [
      { id: 'web:test', status: 'pass', ms: 1200 },
      { id: 'api:integration', status: 'skip', reason: 'DB 없음' },
    ];
    const strict = formatSummary(results, decide(results, { allowSkip: false }));
    assert.match(strict, /PASS {2}web:test/);
    assert.match(strict, /SKIP {2}api:integration .*DB 없음/);
    assert.match(strict, /미완료/);

    const relaxed = formatSummary(results, decide(results, { allowSkip: true }));
    assert.match(relaxed, /실행하지 않은 검사 1개는 통과가 아님/);
  });
});

describe('parseDotenv', () => {
  it('reads values, skips comments and treats empty values as unset', () => {
    assert.deepEqual(parseDotenv('# c\nA=1\nB=\n C = "x y" \nbad\n=v\n'), { A: '1', C: 'x y' });
  });
});

describe('databaseAddress', () => {
  it('reads host and port from a SQLAlchemy URL', () => {
    assert.deepEqual(databaseAddress('postgresql+psycopg://u:p@127.0.0.1:55432/ramus'), {
      host: '127.0.0.1',
      port: 55432,
    });
  });

  it('defaults the port to 5432', () => {
    assert.deepEqual(databaseAddress('postgresql://u@db/ramus'), { host: 'db', port: 5432 });
  });

  it('throws on a malformed URL', () => {
    assert.throws(() => databaseAddress('not a url'));
  });
});
