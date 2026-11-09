import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { findHangul, stripComments } from './hangul-scan.mjs';

describe('findHangul', () => {
  it('finds Korean in strings, templates, JSX text and attributes', () => {
    const source = [
      "const a = '저장';", // 1
      'const b = `총 ${n}개`;', // 2
      '<button aria-label="닫기">x</button>', // 3
      '<p>결과가 없습니다</p>', // 4
      'const ok = messages.save;', // 5
    ].join('\n');
    assert.deepEqual(
      findHangul(source).map((hit) => hit.line),
      [1, 2, 3, 4],
    );
  });

  it('ignores Korean in line and block comments, keeping line numbers', () => {
    const source = ['// 설명 주석', '/* 여러 줄', '   주석 */ const x = 1;', "const y = '값';"].join('\n');
    assert.deepEqual(findHangul(source), [{ line: 4, text: "const y = '값';" }]);
  });

  it('does not treat // or /* inside a string as a comment', () => {
    assert.deepEqual(findHangul("const u = 'http://x' + '한글';").map((h) => h.line), [1]);
    assert.deepEqual(findHangul('const u = "/* 한글 */";').map((h) => h.line), [1]);
  });

  it('handles escaped quotes inside strings', () => {
    assert.deepEqual(findHangul("const s = 'it\\'s'; // 주석").length, 0);
  });

  it('returns nothing for clean source', () => {
    assert.deepEqual(findHangul('export const A = () => <div>{t.title}</div>;'), []);
  });
});

describe('stripComments', () => {
  it('keeps length of lines and newlines', () => {
    const source = 'a // b\n/* c\nd */e';
    const stripped = stripComments(source);
    assert.equal(stripped.split('\n').length, source.split('\n').length);
    assert.equal(stripped.trimEnd().endsWith('e'), true);
  });
});
