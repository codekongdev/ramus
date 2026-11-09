export const taskQueueMessages = {
  title: '작업',
  count: (count: number) => `작업 ${count}개`,
  loading: '작업을 불러오는 중입니다.',
  reload: '다시 불러오기',
  empty: '아직 작업이 없습니다. 대화에서 @AI에게 조사를 맡겨 보세요.',
  listLabel: '이 대화의 작업',
} as const;
