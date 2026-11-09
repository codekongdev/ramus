#!/usr/bin/env node
// i18n:hangul — roadmap 9.3 rule 3. Feature `.tsx` files must not contain Korean screen text;
// it belongs in the feature's `messages.ts`. Comments are allowed.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { findHangul } from './hangul-scan.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const FEATURES = join(ROOT, 'apps', 'web', 'src', 'features');

function tsxFiles(dir) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch (error) {
    if (error.code === 'ENOENT') return [];
    throw error;
  }
  return entries.flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return tsxFiles(path);
    return name.endsWith('.tsx') ? [path] : [];
  });
}

const files = tsxFiles(FEATURES);
const findings = files.flatMap((file) =>
  findHangul(readFileSync(file, 'utf8')).map((hit) => ({ file: relative(ROOT, file), ...hit })),
);

for (const { file, line, text } of findings) process.stdout.write(`${file}:${line}  ${text}\n`);
if (findings.length > 0) {
  process.stdout.write(
    `\n기능 .tsx 파일에 한글 문구 ${findings.length}곳이 있습니다. 같은 기능 폴더의 messages.ts로 옮기세요(로드맵 9.3).\n`,
  );
  process.exitCode = 1;
} else {
  process.stdout.write(`기능 .tsx 파일 ${files.length}개에 한글 문구 없음\n`);
}
