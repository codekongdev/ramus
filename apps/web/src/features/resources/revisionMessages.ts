import { formatNumber } from '../../lib/format';
import { DEFAULT_LOCALE } from '../../lib/locale';
import type { ResourceKind } from './model';
import type { RevisionField, RevisionProblem } from './revisionModel';

export const revisionMessages = {
  edit: '수정', editTitle: '새 버전 작성', save: '새 버전 저장', saving: '저장 중…',
  cancel: '취소', back: '목록', apply: '현재 대화에 적용', applying: '적용 중…',
  history: '버전 이력', latest: '최신', applied: '현재 적용',
  name: '이름', description: '설명', instructions: '지침', content: '내용', fileName: '파일 이름',
  author: '작성자', savedAt: '저장 시각', version: '버전', loading: '버전을 불러오는 중…', retry: '다시 시도',
  saveNote: '새 버전을 저장해도 대화에 적용된 버전은 유지됩니다.',
  saved: '새 버전을 저장했습니다. 적용된 버전은 유지됩니다.',
  unchanged: '내용이 같아 새 버전을 만들지 않았습니다.',
  conflict: '다른 참여자가 새 버전을 저장했습니다. 초안을 유지했습니다. 최신 버전을 확인해 주세요.',
  checkLatest: '최신 버전 확인', resumeDraft: '초안으로 돌아가기',
  draftPreserved: '저장하지 않은 초안을 유지하고 있습니다.',
  replaceFile: '파일 교체', readingFile: '파일을 읽는 중…',
  fileHint: '.md 또는 .txt 파일의 이름과 내용을 새 버전에 저장합니다.',
} as const;

export const revisionViewLabel = (number: number) => `v${number} 보기`;
export const revisionBaseLabel = (number: number) => `기준 버전 v${number}`;

export function revisionProblemMessage(field: RevisionField, problem: RevisionProblem, kind: ResourceKind): string {
  const labels: Record<RevisionField, string> = { name: '이름', description: '설명', body: kind === 'skill' ? '지침' : '내용', fileName: '파일 이름' };
  const limits: Record<RevisionField, number> = { name: 100, description: 2_000, body: 100_000, fileName: 255 };
  switch (problem) {
    case 'required': return `${labels[field]}을 입력하세요.`;
    case 'tooLong': return `${labels[field]}은 ${formatNumber(limits[field], DEFAULT_LOCALE)}자 이하로 입력하세요.`;
    case 'invalidText': return '저장할 수 없는 문자가 포함되어 있습니다.';
    case 'extension': return '.md 또는 .txt 파일 이름을 입력하세요.';
  }
}
