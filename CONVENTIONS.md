# Ramus 개발 컨벤션

## 아키텍처

| 영역 | 채택 패턴 | 구현 규칙 |
| --- | --- | --- |
| 프론트엔드 | **MVI** | 기능별로 Intent·State·Reducer·EffectHandler·View를 분리한다. View는 Intent를 보내고 State를 렌더링한다. |
| 백엔드 | **Clean Architecture** | Router/Controller는 입출력, UseCase는 업무 흐름, Domain은 업무 규칙, Repository는 저장 접근을 담당한다. |
| Python 처리 | **Functional Core / Imperative Shell** | 파싱·변환·판단은 순수 함수로 작성하고 파일·DB·모델 호출은 Adapter로 분리한다. Python이 메인 서버이면 백엔드 구조도 동일하게 적용한다. |
| 배포·모듈 | **Modular Monolith** | 하나의 백엔드에서 시작하고 대화·기억·문서·AI 실행을 기능 모듈로 나눈다. 별도 Worker는 독립 실행이 필요한 작업에 도입한다. |

### 프론트엔드 흐름

```text
View → Intent → Reducer → 새 State → View
외부 작업: EffectHandler → 결과 Intent → Reducer
```

- Reducer는 순수 함수이며 API·DB·타이머를 호출하지 않는다.
- EffectHandler가 비동기 작업을 실행하고 성공·실패를 결과 Intent로 전달한다.
- 공유 데이터는 서버를 원본으로 삼고, 클라이언트 캐시는 같은 갱신 경로로 반영한다.
- 패널 열림·포커스 같은 단순 UI 상태는 컴포넌트 내부에 둔다.

근거: [React Reducer](https://react.dev/learn/extracting-state-logic-into-a-reducer), [Redux 단방향 데이터 흐름](https://redux.js.org/tutorials/fundamentals/part-2-concepts-data-flow).

### 백엔드 의존성

```text
Presentation → Application → Domain
Infrastructure → Application/Domain이 정의한 인터페이스
```

- **DIP + DI:** DB·AI·외부 API 구현을 주입한다. Domain에서 프레임워크·ORM·모델 SDK를 import하지 않는다.
- **Repository Pattern:** 저장 접근은 Repository 구현으로 모은다. UseCase가 트랜잭션 범위를 결정한다.
- **모듈 은닉화:** 다른 모듈은 공개 인터페이스로만 접근한다. 내부 상태·테이블을 직접 수정하지 않는다.
- **순환 의존 금지:** 양방향 import가 생기면 공통 계약을 분리하거나 책임을 재배치한다.

근거: [Repository와 의존성 역전](https://www.cosmicpython.com/book/chapter_02_repository), [Dependency Injection](https://www.martinfowler.com/articles/injection.html).

## 공통 구현 규칙

| 항목 | 규칙 |
| --- | --- |
| 타입·계약 | **DTO + Schema Validation.** API·파일·AI 응답은 경계에서 검증한다. ORM 모델을 API 응답으로 직접 노출하지 않는다. |
| API 공유 | **OpenAPI 기준 계약.** 프론트 타입·클라이언트는 계약에서 생성하고 수동으로 중복 정의하지 않는다. |
| 상태 변경 | **Immutable State.** 프론트 State를 직접 수정하지 않고 Reducer에서 새 상태를 만든다. |
| 동시 수정 | **Optimistic Locking.** 기준 버전을 포함한 조건부 갱신과 변경 이력 저장을 하나의 트랜잭션으로 처리한다. |
| 중복 실행 | **Idempotency.** 재시도 가능한 변경 요청에 요청 ID를 두고 같은 요청의 효과가 중복되지 않게 한다. |
| 비동기 | 작업 ID·진행 상태·실패·취소를 명시한다. 늦게 도착한 결과는 원래 대상에 연결하고 최신 상태를 덮지 않는다. |
| 오류 | 예상 가능한 업무 오류와 시스템 오류를 구분한다. 오류를 삼키거나 성공 응답으로 바꾸지 않는다. |
| 테스트 | **Unit → Integration → E2E.** Reducer·Domain은 단위 테스트, 저장·외부 연결은 통합 테스트, 핵심 공동 작업은 E2E로 검증한다. |

근거: [OpenAPI](https://spec.openapis.org/oas/v3.1.1.html), [PostgreSQL 동시성](https://www.postgresql.org/docs/current/transaction-iso.html).
