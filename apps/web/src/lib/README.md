# src/lib

기능 폴더가 함께 쓰는 프론트 기반 코드(P0-B3). 화면 컴포넌트는 두지 않는다.

| 경로 | 내용 |
|---|---|
| `mvi.ts` | `Reducer`(순수, `next(state, ...effects)` 반환), `EffectHandler`, `createStore`, `useStore` |
| `api/` | `createApiClient<paths>()`(변경 요청에 `Idempotency-Key` 자동 추가), `toResult()`로 `ApiResult` 변환, 업무·시스템·네트워크 오류 구분 |
| `realtime/` | 프로젝트 SSE 연결(`useProjectEvents`), 재접속 backoff, 열릴 때마다 `onResync` 호출. 연결 상태 Reducer는 MVI 예시를 겸한다 |

## 기능에서 쓰는 방법

```ts
const reducer: Reducer<State, Intent, Effect> = (state, intent) => {
  switch (intent.type) {
    case 'load': return next({ ...state, status: 'loading' }, { type: 'fetch' });
    case 'loaded': return next({ ...state, status: 'ready', items: intent.items });
    case 'failed': return next({ ...state, status: 'error', error: intent.error });
  }
};

const handle: EffectHandler<Effect, Intent> = async (effect, dispatch, signal) => {
  const result = await toResult(api.GET('/api/...', { signal }));
  dispatch(result.ok ? { type: 'loaded', items: result.data } : { type: 'failed', error: result.error });
};

const [state, dispatch] = useStore(reducer, initialState, handle); // reducer·handle은 모듈 수준에 정의
```

- 예상 가능한 실패는 결과 Intent로 바꾼다. EffectHandler가 던진 오류는 버그로 보고 다시 던진다.
- 화면이 사라진 뒤 도착한 결과는 버린다(`signal`이 abort됨).
- 같은 사용자 동작을 재시도할 때는 `newIdempotencyKey()`로 키를 한 번 만들어 매 시도의 `headers`에 넣는다.
- 재접속 사이에 놓친 이벤트는 다시 오지 않는다. `onResync`에서 서버 상태를 다시 읽는다.

## 계약 확정 후 할 일

- `src/api/schema.d.ts`(P0-A3)가 생기면 `createApiClient<paths>()`로 앱 단일 클라이언트를 만든다.
- `src/lib/events.ts`에 이벤트 타입과 경계 검증을 정의하고 `useProjectEvents`의 `eventTypes`·`decode`로 넘긴다(부록 B, 계약 변경 대상).
- 오류 응답 형식(P0-A1)이 정해지면 `api/result.ts`의 `readErrorBody`를 그 형식 하나로 줄인다.
