# src/lib

기능 폴더가 함께 쓰는 프론트 기반 코드(P0-B3). 기준은 `docs/contracts.md` 0·1·4·7장이다.

| 경로 | 내용 |
|---|---|
| `mvi.ts` | `Reducer`(순수, `next(state, ...effects)` 반환), `EffectHandler`, `createStore`, `useStore` |
| `api/` | `createApiClient<paths>()`(변경 요청에 `Idempotency-Key` 자동 추가), `toResult()`로 `ApiResult` 변환, 오류 봉투 `{error: {code, message, details}}` 검증, `errorMessage()`·`hasErrorCode()` |
| `events.ts` | SSE 이벤트 9종의 타입과 경계 검증(`decodeProjectEvent`). 이벤트 추가·변경은 계약 변경 |
| `realtime/` | `ProjectEventsProvider`가 프로젝트당 SSE 연결 하나를 열어 기능에 나눠 준다. 재접속 backoff, 연결 오류 시 `GET /api/me`로 세션 확인 후 401이면 중단. 연결 상태 Reducer는 MVI 예시를 겸한다 |

## 기능에서 쓰는 방법

```ts
const reducer: Reducer<State, Intent, Effect> = (state, intent) => {
  switch (intent.type) {
    case 'load': return next({ ...state, status: 'loading' }, { type: 'fetch' });
    case 'loaded': return next({ ...state, status: 'ready', items: intent.items });
    case 'failed': return next({ ...state, status: 'error', message: errorMessage(intent.error) });
    case 'serverEvent': /* intent.event.type으로 분기 */
  }
};

const handle: EffectHandler<Effect, Intent> = async (effect, dispatch, signal) => {
  const result = await toResult(api.GET('/api/...', { signal }));
  dispatch(result.ok ? { type: 'loaded', items: result.data.items } : { type: 'failed', error: result.error });
};

// 컴포넌트 안. reducer·handle은 모듈 수준에 정의한다.
const [state, dispatch] = useStore(reducer, initialState, handle);
useProjectEventListener((event) => dispatch({ type: 'serverEvent', event }));
useResyncListener(() => dispatch({ type: 'load' }));
```

- 예상 가능한 실패는 결과 Intent로 바꾼다. EffectHandler가 던진 오류는 버그로 보고 다시 던진다.
- 화면이 사라진 뒤 도착한 결과는 버린다(`signal`이 abort됨).
- 업무 오류는 `error.message`를 그대로 보여 주고 동작은 `hasErrorCode(error, 'VERSION_CONFLICT')`처럼 `code`로 분기한다. 시스템·네트워크 오류는 `errorMessage()`의 공통 문구를 쓴다.
- 사용자 행동 하나마다 `newIdempotencyKey()`로 키를 만들고, 그 행동을 재시도할 때 같은 키를 `headers`에 넣는다.
- 재접속 사이에 놓친 이벤트는 다시 오지 않는다(C4). `useResyncListener`에서 서버 상태를 다시 읽는다.
- 기능은 `EventSource`를 직접 열지 않는다. 앱(`src/app`)이 프로젝트 화면을 `ProjectEventsProvider`로 감싸고, `onUnauthorized`에서 로그인 화면으로 이동한다.

## 남은 연결

- `src/api/schema.d.ts`(P0-A3)가 생기면 `createApiClient<paths>()`로 앱 단일 클라이언트를 만든다.
