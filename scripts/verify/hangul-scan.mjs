// Pure scanner for i18n:hangul. Reports Hangul outside comments: string and template
// literals, JSX text and attributes. Comments are skipped by a small lexer that knows
// about strings, so `"//"` inside a string is not mistaken for a comment.
const HANGUL = /[ᄀ-ᇿ㄰-㆏가-힣]/;

/** Source with comments replaced by spaces; newlines are kept so line numbers stay correct. */
export function stripComments(source) {
  let out = '';
  let i = 0;
  let quote = null; // ', " or ` while inside a literal
  while (i < source.length) {
    const ch = source[i];
    const next = source[i + 1];
    if (quote) {
      out += ch;
      if (ch === '\\') {
        out += next ?? '';
        i += 2;
        continue;
      }
      if (ch === quote) quote = null;
      i += 1;
      continue;
    }
    if (ch === '/' && next === '/') {
      while (i < source.length && source[i] !== '\n') {
        out += ' ';
        i += 1;
      }
      continue;
    }
    if (ch === '/' && next === '*') {
      const end = source.indexOf('*/', i + 2);
      const stop = end === -1 ? source.length : end + 2;
      for (; i < stop; i += 1) out += source[i] === '\n' ? '\n' : ' ';
      continue;
    }
    if (ch === "'" || ch === '"' || ch === '`') quote = ch;
    out += ch;
    i += 1;
  }
  return out;
}

/** `[{ line, text }]` for each line that still contains Hangul after comments are removed. */
export function findHangul(source) {
  return stripComments(source)
    .split('\n')
    .flatMap((text, index) => (HANGUL.test(text) ? [{ line: index + 1, text: text.trim() }] : []));
}
