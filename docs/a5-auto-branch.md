# A5 자동 분기 연결

`execution.work_composition.build_work_execution_runtime`가 A4 실행기에 `work` 핸들러와 Task 상태 동기화를 등록한다. `handlers`에는 B 트랙의 `summary` 핸들러를 추가할 수 있다. 외부 서비스 호출은 주입한 `LlmGateway`에서만 수행한다.

## 앱 조립

조립 루트에서 다음 구현을 주입한다.

| 인자 | 제공 모듈 | 역할 |
| --- | --- | --- |
| `transaction` | shared | 호출마다 커밋·롤백하는 DB 트랜잭션 |
| `publisher` | realtime | 프로젝트 SSE 이벤트 발행 |
| `gateway`, `connections` | access/execution(A3) | 요청자의 키로 모델 호출, 키 연결 여부 조회 |
| `context_provider` | resources/sharing(B3) | 적용된 자료·결론의 고정 버전 조회, 자료 적용 목록 복사 |
| `writer` | conversations(A2) | `ConversationWriter`: 자식 대화와 AI·시스템 메시지 저장, 커밋 후 대화·메시지 이벤트 예약 |

반환한 runtime의 `requester`를 대화 서비스에 넘기고, 앱 수명주기에서 `runtime.worker.run_forever()`를 시작·종료한다. 대화 writer와 실행기는 같은 이벤트 발행기를 사용한다. 기본 `create_app()`은 `OpenAiGateway`를 감싼 `LongSummaryGateway`, 업무·결과 정리 핸들러, A2의 실제 대화 writer, B3의 실제 ContextProvider를 조립하고 worker를 시작한다. 앱 객체 생성은 DB에 연결하지 않지만 수명주기를 시작하면 worker가 DB를 조회한다.

게이트웨이는 access의 공개 `CredentialProvider`로 실행 요청자의 현재 키를 읽고, DB 트랜잭션을 닫은 뒤 Responses API를 호출한다. `OPENAI_MODEL`과 엄격한 JSON 스키마를 보내고 `store: false`를 지정한다. 응답 거절·불완전 응답·스키마 위반과 제공자 오류는 안전한 실행 오류로 변환하며 키나 제공자 본문을 저장하거나 로그에 남기지 않는다. API 키 등록에는 기존과 같이 `RAMUS_SECRET_KEY`가 필요하다. 가짜 응답은 `create_app(..., llm_gateway=...)`로 테스트에서만 명시적으로 주입한다.

Task 목록·상세·취소·재시도 HTTP API도 같은 runtime에 연결된다. 프로젝트 참여자는 작업을 읽을 수 있고, 변경은 Task 요청자와 현재 업무 Run 요청자가 모두 일치해야 한다. 다른 계정이 보완 요청을 실행한 동안 원 Task 요청자는 그 계정의 Run을 중단하거나 다시 실행할 수 없다. 변경 요청은 멱등 키를 사용하고, 조회·변경·receipt 재생 전에 프로젝트 권한을 검사한다.

## 입력과 분기

`conversations.application.work_inputs.WorkInputReader`는 실행의 원래 요청까지 메시지를 읽는다. 기본 SQL 구현은 `run_id`에 연결된 사람 메시지 또는 자식 시작용 시스템 메시지의 `seq`를 기준으로 자른다. 대기·실행 중 도착한 후속 메시지는 그 실행의 입력에 섞이지 않는다. 재시도도 같은 원래 요청을 사용하며 자료·결론 버전은 새 점유 시점에 다시 고정한다. 모델 요청의 `message_from_seq`·`message_to_seq`는 실제 자료·결론 버전 ID와 함께 Run 입력 스냅샷에 저장한다.

부모 대화의 모델 출력은 `answer`, `clarify`, `branch` 중 하나다. 방법 질문·작업 목록 작성·사람 간 배정은 분기하지 않도록 요청에 명시한다. 의미 판정은 모델이 수행하며 애플리케이션은 출력 스키마, 최대 4개 작업, 공백·대소문자만 다른 중복 목표·시작 입력을 검사한다. 자식 대화는 별도 스키마로 `branch`를 거부한다.

분기는 하나의 완료 트랜잭션에서 자식 대화, Task, 자료 핀, 자식 Run, 시스템 시작 입력과 부모의 짧은 안내를 저장한다. 목표는 Task에, 시작 입력은 자식 메시지에, 출처는 `source_run_id`·`source_conversation_id`에 남긴다. 자식 실행에는 Task의 목표를 시작 입력과 함께 전달한다. 중간 단계가 실패하면 모두 롤백되며 미완성 자식이나 생성 이벤트가 남지 않는다. 기존 A4 완료 상태 전이와 `(source_run_id, ordinal)` 고유 제약이 중복 생성을 막는다.

첫 자식은 분기 시점 부모의 정확한 자료 버전 ID를 복사한다. 이후 자식은 같은 트랜잭션에서 만든 앞 자식의 적용 목록을 복사하므로 부모가 동시에 적용 목록을 바꿔도 형제들의 초기 버전은 같다. 받은 결론은 자동 복사하지 않는다. 이후 부모의 새 버전 저장·적용도 자식 설정을 바꾸지 않는다.

## 작업 상태와 검증

현재 업무 Run의 `pending`·`running`·`succeeded`·`failed`·`cancelled`는 Task의 `pending`·`running`·`ready`·`failed`·`cancelled`로 같은 트랜잭션에서 반영된다. 재시도·대기 시간 초과·재시작 복구도 같은 경로를 쓴다. `current_run_id` 조건으로 예전 실행이 새 작업 상태를 덮지 않으며 결과 정리 Run은 업무 Task 상태를 바꾸지 않는다. `task.updated`는 results 모듈의 공개 조회 포트로 기존 결과 연결을 유지하고 커밋 후 발행한다.

로컬 검증:

```sh
uv run --project apps/api ruff check apps/api
uv run --project apps/api pytest
```

통합 테스트는 `conftest.py`가 만든 `ramus_test_*` 임시 DB를 사용한다. `test_live_gateway_integration.py`는 계정 키 저장·복호화, 기본 게이트웨이 조립, 자료 v1 고정, worker 완료까지 확인하고 제공자 HTTP만 대체한다. F-02의 여섯 사례는 FakeLLM에 정해 둔 출력을 통한 계약 검사이며, 실제 모델의 의미 판정 정확도 평가는 별도로 필요하다. 실제 키·모델 호출은 로컬 검증에 포함하지 않는다.

브라우저에서 응답·분기·작업 큐·중단·재시도·부모 초안 유지·새로고침 후 저장 상태를 확인한다.

```sh
pnpm exec playwright test tests/e2e/work-execution.spec.ts
```

이 테스트는 임시 DB와 실제 API·worker·SSE를 쓰고 모델 응답만 결정적으로 주입한다. 수명주기가 필요 없는 라우터 단위 테스트는 worker를 시작하지 않아 개발 DB에 접근하지 않는다.
