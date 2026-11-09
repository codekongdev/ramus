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

반환한 runtime의 `requester`를 대화 서비스에 넘기고, 앱 수명주기에서 `runtime.worker.run_forever()`를 시작·종료한다. 대화 writer와 실행기는 같은 이벤트 발행기를 사용한다. `create_app(..., llm_gateway=...)`는 A2의 실제 대화 writer와 B3의 실제 ContextProvider를 조립하고 worker를 시작한다. 실제 A3 게이트웨이가 아직 연결되지 않은 기본 앱은 실행기를 시작하지 않는다. FakeLLM은 테스트에서만 명시적으로 주입하며 기본 모델로 쓰지 않는다. Task 조회·취소·재시도 HTTP 스텁의 교체는 별도 작업이다.

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

통합 테스트는 `conftest.py`가 만든 `ramus_test_*` 임시 DB를 사용한다. F-02의 여섯 사례는 FakeLLM에 정해 둔 출력을 통한 계약 검사이며, 실제 모델의 의미 판정 정확도 평가는 별도로 필요하다. 실제 키·모델 호출과 브라우저 E2E는 이 로컬 검증에 포함하지 않는다.
