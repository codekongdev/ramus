import { formatNumber } from '../../lib/format';
import { DEFAULT_LOCALE } from '../../lib/locale';
import type { FieldProblem, ResourceKind, SkillField } from './model';
import type { SkillFileProblem } from './skillFile';
import { MAX_DESCRIPTION_LENGTH, MAX_INSTRUCTIONS_LENGTH, MAX_NAME_LENGTH } from './skillFile';

/** Screen text for the 스킬·자료 modal (roadmap 9.3 규칙 3). */
export const resourcesMessages = {
  menuLabel: '스킬·자료',
  modalTitle: '스킬·자료',
  registerSkill: '스킬 등록',
  searchLabel: '스킬·자료 검색',
  searchPlaceholder: '이름이나 설명으로 검색',
  selectionLabel: '선택한 스킬·자료',
  resultsLabel: '검색 결과',
  loading: '불러오는 중…',
  retry: '다시 시도',
  emptyAll: '등록된 스킬·자료가 없습니다',
  emptySearch: '검색 결과가 없습니다',
  emptySearchHint: '검색어를 바꾸거나 새 스킬을 등록하세요.',
  noConversation: '대화를 열면 선택한 스킬·자료를 그 대화에 적용할 수 있습니다.',
  appliedLoadFailed: '현재 대화에 적용된 스킬·자료를 불러오지 못했습니다.',
  apply: '적용',
  applying: '적용 중…',
  back: '목록',
  registerTitle: '스킬 등록',
  nameLabel: '이름',
  descriptionLabel: '설명',
  instructionsLabel: '지침',
  instructionsHint: 'AI가 이 스킬을 적용한 대화에서 따를 지침입니다.',
  loadSkillFile: 'SKILL.md 불러오기',
  register: '등록',
  registering: '등록 중…',
} as const;

export const kindLabel = (kind: ResourceKind): string => {
  switch (kind) {
    case 'skill':
      return '스킬';
    case 'text':
      return '자료';
    case 'file':
      return '파일';
  }
};

export const versionLabel = (number: number): string => `v${number}`;

export const chipLabel = (name: string, number: number): string => `${name} · ${versionLabel(number)}`;

/** WF-10: the latest version and the version this conversation uses, side by side. */
export function versionSummary(latest: number, applied: number | null): string {
  if (applied === null) return versionLabel(latest);
  if (applied === latest) return `${versionLabel(latest)} · 현재 적용`;
  return `최신 ${versionLabel(latest)} · 현재 적용 ${versionLabel(applied)}`;
}

export const selectedVersionNote = (number: number): string => `${versionLabel(number)} 선택됨`;

export const useLatestLabel = (number: number): string => `최신 ${versionLabel(number)}로 바꾸기`;

export const selectLabel = (name: string): string => `${name} 선택`;

const requiredMessages: Record<SkillField, string> = {
  name: '이름을 입력하세요.',
  description: '설명을 입력하세요.',
  instructions: '지침을 입력하세요.',
};

const tooLongMessages: Record<SkillField, (limit: string) => string> = {
  name: (limit) => `이름은 ${limit}자 이하로 입력하세요.`,
  description: (limit) => `설명은 ${limit}자 이하로 입력하세요.`,
  instructions: (limit) => `지침은 ${limit}자 이하로 입력하세요.`,
};

const fieldLimits: Record<SkillField, number> = {
  name: MAX_NAME_LENGTH,
  description: MAX_DESCRIPTION_LENGTH,
  instructions: MAX_INSTRUCTIONS_LENGTH,
};

export function fieldProblemMessage(field: SkillField, problem: FieldProblem): string {
  switch (problem) {
    case 'required':
      return requiredMessages[field];
    case 'tooLong':
      return tooLongMessages[field](formatNumber(fieldLimits[field], DEFAULT_LOCALE));
  }
}

export function fileProblemMessage(problem: SkillFileProblem): string {
  switch (problem) {
    case 'extension':
      return '.md 또는 .txt 파일만 불러올 수 있습니다.';
    case 'encoding':
      return 'UTF-8 텍스트 파일만 불러올 수 있습니다.';
    case 'tooLarge':
      return `지침은 ${formatNumber(MAX_INSTRUCTIONS_LENGTH, DEFAULT_LOCALE)}자 이하여야 합니다.`;
    case 'empty':
      return '파일에 지침 내용이 없습니다.';
    case 'unreadable':
      return '파일을 읽지 못했습니다. 다시 선택해 주세요.';
  }
}
