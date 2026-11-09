/**
 * Pure helpers for "SKILL.md 불러오기" (WF-14, D9). Only `.md`/`.txt` UTF-8 text is accepted;
 * anything else is reported instead of being silently dropped (WF-10 예외).
 */

export const MAX_NAME_LENGTH = 100;
export const MAX_DESCRIPTION_LENGTH = 2_000;
export const MAX_INSTRUCTIONS_LENGTH = 100_000;
/** UTF-8 uses at most 4 bytes per character, so a larger file cannot fit the length limit. */
export const MAX_SKILL_FILE_BYTES = MAX_INSTRUCTIONS_LENGTH * 4;

const ALLOWED_EXTENSIONS = ['.md', '.txt'] as const;

export type SkillFileProblem = 'extension' | 'encoding' | 'tooLarge' | 'empty' | 'unreadable';

export type ParsedSkill = {
  /** From front matter `name:`; null when absent. */
  readonly name: string | null;
  /** From front matter `description:`; null when absent. */
  readonly description: string | null;
  readonly instructions: string;
};

export type SkillFileResult =
  | { readonly ok: true; readonly skill: ParsedSkill }
  | { readonly ok: false; readonly problem: SkillFileProblem };

export function hasAllowedExtension(fileName: string): boolean {
  const lower = fileName.toLowerCase();
  return ALLOWED_EXTENSIONS.some((extension) => lower.endsWith(extension));
}

/** Strict UTF-8 decode. NUL never appears in text files, so it marks binary input. */
export function decodeText(bytes: Uint8Array): string | null {
  let text: string;
  try {
    text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: false }).decode(bytes);
  } catch {
    return null;
  }
  return text.includes('\u0000') ? null : text;
}

function unquote(value: string): string {
  const trimmed = value.trim();
  const first = trimmed[0];
  if (trimmed.length >= 2 && (first === '"' || first === "'") && trimmed.endsWith(first)) {
    return trimmed.slice(1, -1).trim();
  }
  return trimmed;
}

/**
 * Splits an optional YAML-like front matter block (`---` … `---`) from the body. Only the
 * single-line `name` and `description` keys are read; the body becomes the instructions.
 */
export function parseSkillMarkdown(text: string): ParsedSkill {
  const normalized = text.replace(/\r\n?/g, '\n');
  const match = /^---\n([\s\S]*?)\n---[ \t]*(?:\n|$)/.exec(normalized);
  if (!match) return { name: null, description: null, instructions: normalized.trim() };

  let name: string | null = null;
  let description: string | null = null;
  for (const line of match[1]!.split('\n')) {
    const field = /^(name|description)\s*:(.*)$/.exec(line);
    if (!field) continue;
    const value = unquote(field[2]!);
    if (value === '') continue;
    if (field[1] === 'name') name = value;
    else description = value;
  }
  return { name, description, instructions: normalized.slice(match[0].length).trim() };
}

export function readSkillFile(fileName: string, bytes: Uint8Array): SkillFileResult {
  if (!hasAllowedExtension(fileName)) return { ok: false, problem: 'extension' };
  if (bytes.byteLength > MAX_SKILL_FILE_BYTES) return { ok: false, problem: 'tooLarge' };
  const text = decodeText(bytes);
  if (text === null) return { ok: false, problem: 'encoding' };
  const skill = parseSkillMarkdown(text);
  if (skill.instructions === '') return { ok: false, problem: 'empty' };
  if (skill.instructions.length > MAX_INSTRUCTIONS_LENGTH) return { ok: false, problem: 'tooLarge' };
  return { ok: true, skill };
}
