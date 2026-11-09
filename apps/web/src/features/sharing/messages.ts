export const sharingMessages = {
  action: '다른 대화에 보내기', back: '결론으로 돌아가기', search: '대화 검색', searchHint: '대화 제목으로 검색하세요.',
  send: '보내기', sending: '보내는 중', targets: '보낼 대화', selected: '선택한 대화',
  noTargets: '검색 결과가 없습니다.', loading: '대화를 불러오고 있습니다.', retry: '다시 불러오기',
  selectionLimit: '한 번에 최대 20개 대화에 보낼 수 있습니다.', top: '최상위 대화',
  remove: (title: string) => `${title} 선택 해제`,
  received: '공유받은 결과', empty: '공유받은 결과가 없습니다.', loadingInputs: '공유받은 결과를 불러오고 있습니다.',
  loadingRevision: '결론을 불러오고 있습니다.', newer: '새 버전', version: (version: number) => `v${version}`,
  source: '출처 정보', sourceRange: (from: number, to: number) => `원문 메시지 ${from}–${to}`,
  savedConclusion: '저장된 결론',
  sent: (count: number) => `${count}개 대화에 보냈습니다.`,
  unchanged: '이미 연결된 결론입니다.', keptNewer: '대화에 연결된 더 새 버전을 유지했습니다.',
} as const;
