/**
 * Client-side fallback messages for errors the server did not phrase (roadmap 9.3 규칙 3).
 * Business errors show the server's `error.message`, already in the request language.
 */
export const apiMessages = {
  systemError: '요청을 처리하는 중에 문제가 생겼습니다. 잠시 후 다시 시도해 주세요.',
  networkError: '서버에 연결할 수 없습니다. 네트워크 연결을 확인해 주세요.',
} as const;
