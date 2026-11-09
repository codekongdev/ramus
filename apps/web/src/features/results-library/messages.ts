export const resultsLibraryMessages = {
  menu: '결과물',
  title: '결과물',
  description: '현재 프로젝트에서 저장한 최신 결론을 모아 봅니다.',
  list: '저장된 결과물',
  loading: '결과물을 불러오는 중입니다.',
  refresh: '새로고침',
  retry: '다시 시도',
  empty: '아직 저장된 결과물이 없습니다.',
  emptyHint: '작업의 결과 탭에서 결론을 검토하고 저장하면 여기에 표시됩니다.',
  source: '출처 대화',
  savedAt: '저장 시각',
  version: (version: number): string => `v${version}`,
} as const;
