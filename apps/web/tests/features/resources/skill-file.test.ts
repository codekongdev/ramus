import { describe, expect, it } from 'vitest';
import {
  MAX_INSTRUCTIONS_LENGTH,
  MAX_SKILL_FILE_BYTES,
  hasAllowedExtension,
  parseSkillMarkdown,
  readSkillFile,
} from '../../../src/features/resources/skillFile';

const bytes = (text: string) => new TextEncoder().encode(text);

describe('hasAllowedExtension (D9)', () => {
  it('accepts .md and .txt in any case', () => {
    expect(hasAllowedExtension('SKILL.md')).toBe(true);
    expect(hasAllowedExtension('notes.TXT')).toBe(true);
    expect(hasAllowedExtension('report.pdf')).toBe(false);
    expect(hasAllowedExtension('md')).toBe(false);
  });
});

describe('parseSkillMarkdown', () => {
  it('reads name and description from front matter and keeps the body as instructions', () => {
    const text = '---\nname: 타사 벤치마킹\ndescription: "기능·정책 조사"\nlicense: MIT\n---\n\n# 지침\n고객 흐름을 정리합니다.\n';
    expect(parseSkillMarkdown(text)).toEqual({
      name: '타사 벤치마킹',
      description: '기능·정책 조사',
      instructions: '# 지침\n고객 흐름을 정리합니다.',
    });
  });

  it('uses the whole text when there is no front matter', () => {
    expect(parseSkillMarkdown('  각 항목에 출처를 남깁니다.\n')).toEqual({
      name: null,
      description: null,
      instructions: '각 항목에 출처를 남깁니다.',
    });
  });

  it('normalizes CRLF line endings', () => {
    expect(parseSkillMarkdown('---\r\nname: A\r\n---\r\nbody\r\nline')).toEqual({
      name: 'A',
      description: null,
      instructions: 'body\nline',
    });
  });

  it('ignores empty front matter values', () => {
    expect(parseSkillMarkdown('---\nname:\ndescription: \n---\nbody').name).toBeNull();
  });
});

describe('readSkillFile', () => {
  it('parses a UTF-8 markdown file and strips the BOM', () => {
    const result = readSkillFile('SKILL.md', bytes('﻿---\nname: A\n---\nbody'));
    expect(result).toEqual({ ok: true, skill: { name: 'A', description: null, instructions: 'body' } });
  });

  it('rejects other extensions without reading', () => {
    expect(readSkillFile('skill.pdf', bytes('body'))).toEqual({ ok: false, problem: 'extension' });
  });

  it('rejects invalid UTF-8 and binary content', () => {
    expect(readSkillFile('a.md', new Uint8Array([0xff, 0xfe, 0x00]))).toEqual({ ok: false, problem: 'encoding' });
    expect(readSkillFile('a.txt', bytes('a\u0000b'))).toEqual({ ok: false, problem: 'encoding' });
  });

  it('rejects a file without instructions', () => {
    expect(readSkillFile('a.md', bytes('---\nname: A\n---\n   \n'))).toEqual({ ok: false, problem: 'empty' });
  });

  it('rejects files over the length limit', () => {
    expect(readSkillFile('a.md', new Uint8Array(MAX_SKILL_FILE_BYTES + 1))).toEqual({ ok: false, problem: 'tooLarge' });
    expect(readSkillFile('a.md', bytes('a'.repeat(MAX_INSTRUCTIONS_LENGTH + 1)))).toEqual({
      ok: false,
      problem: 'tooLarge',
    });
  });
});
