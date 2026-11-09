export const conversationMessages = {
  aiBusy: 'AI 작업이 진행 중입니다. 완료 후 @AI로 다시 요청해 주세요.',
  aiConnection: 'AI 연결 후 @AI로 요청해 주세요. 입력한 내용은 유지됩니다.',
} as const;

export const viewMessages = {
  noConversation: '대화를 선택해 주세요',
  selectHint: '왼쪽에서 대화를 선택하거나 새 대화를 만들어 팀과 논의를 시작하세요.',
  loading: '대화를 불러오는 중',
  retry: '다시 불러오기',
  messageList: '대화 메시지',
  noMessages: '첫 메시지를 남겨 보세요.',
  emptyHint: '팀과 논의하고, AI의 도움이 필요하면 @AI를 입력하세요.',
  composer: '메시지',
  placeholder: '팀에 메시지를 보내거나 @AI에게 요청하세요',
  send: '보내기',
  sending: '보내는 중',
  hint: 'Enter로 보내기 · Shift+Enter로 줄바꿈',
  active: 'AI가 응답을 준비하고 있습니다. 팀 대화는 계속할 수 있습니다.',
  disconnected: '연결이 끊겼습니다. 다시 연결되면 새 메시지를 불러옵니다.',
  reconnecting: '다시 연결하는 중입니다. 연결되면 새 메시지를 불러옵니다.',
  example: '예시',
  ai: 'AI',
  system: '안내',
};
