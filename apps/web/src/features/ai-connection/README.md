# AI 연결

`AiConnectionProvider`를 `ModalHostProvider` 위에 두고, 호스트 안에 `AiConnectionModalHost`를 한 번 마운트한다. 계정 변경 시 Provider를 새로 마운트해 이전 계정의 연결 표시와 대기 요청을 버린다. 워크스페이스의 `AiConnectionButton`은 연결 상태 조회·키 입력·교체·해제를 연다.

AI 실행 직전에 앱 조립 계층에서 `useAiConnection().ensure()`를 호출한다. 연결이 확인되면 `true`, 연결 취소·다른 모달로 교체·Provider 해제 시 `false`를 반환한다. 동시에 확인한 호출은 하나의 연결 모달을 공유한다. 연결 여부는 요청마다 서버에서 확인하므로 다른 탭에서 해제된 키를 캐시만 보고 사용하지 않는다.

작업 모달에는 앱에서 `ensure`를 주입한다. 연결 화면을 여는 동안 원래 작업 모달의 컴포넌트·본문 DOM·초안·진행 중 효과를 보존하고, 연결 성공이나 취소 시 같은 모달로 돌아온다. 화면에는 열린 native dialog 하나만 표시한다.

기능끼리 import하지 않도록 앱에서 `ensure`를 입력창·결과 정리 액션에 주입한다. 호출자는 실행 전에 원래 대상 대화·본문·첨부를 캡처하고, 중복 전송을 막으며, `false`일 때 초안을 유지해야 한다.

```ts
const { ensure } = useAiConnection();

async function submitAi(request: CapturedAiRequest) {
  if (await ensure()) await submitCapturedRequest(request);
}
```

연결 모듈은 요청 초안을 저장하거나 메시지를 전송하지 않는다. 연결이 필요한 호출만 `ensure`를 사용하며, 일반 메시지 작성과 공동 열람에는 연결을 요구하지 않는다. 키는 모달의 입력 상태와 API 호출에만 존재하고 공유 State·브라우저 저장소에는 넣지 않는다.

브라우저 회귀 테스트는 로컬 Vite 서버를 띄운 뒤 실행한다. 테스트는 가짜 HTTP 응답과 테스트용 문자열을 사용한다.

```sh
RAMUS_WEB_PORT=5193 pnpm --filter @ramus/web dev
RAMUS_WEB_PORT=5193 pnpm exec playwright test tests/e2e/ai-connection.spec.ts
```

`pnpm exec playwright test tests/e2e/ai-connection-api.spec.ts`는 실제 로그인·연결 API와 임시 PostgreSQL을 사용한다. 테스트 서버의 키 검증만 가짜 구현으로 주입하므로 OpenAI 호출 비용은 발생하지 않는다.
