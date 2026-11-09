# B4 결과 정리와 버전

`b/B4-results`는 `main`의 `c91b75d`에서 만든 별도 워크트리다. 기존 `ramus-setup`의 진행 중인 변경은 포함하지 않는다.

작업이 준비되면 모달 헤더의 **결과 정리**로 별도 summary 실행을 등록한다. 결과 탭에서 생성된 결론을 검토·수정해 v1으로 저장하고, 승인 결론 수정 또는 **다시 정리**로 후속 버전을 만든다. 본문은 `conclusion` 하나이며 출처와 입력 버전은 별도 메타데이터다. 정리 중 모달을 닫아도 실행은 계속되고, 실패해도 승인 버전과 작업의 ready 상태는 유지된다.

주요 변경은 다음과 같다.

- `modules/results/`: 정리 등록·조회·승인 UseCase, SQL 저장소, summary handler와 순수 프롬프트, 권한 및 이벤트 처리.
- `modules/conversations/*/summary_inputs.py`, `modules/execution/*/summary_tasks.py`: 상대 모듈 테이블에 직접 접근하지 않는 조회 인터페이스.
- `modules/execution/*/task_queries.py`: 작업 큐·모달 진입에 필요한 인증된 Task 조회. 중단·재시도 API는 별도 작업 범위다.
- `modules/execution/infrastructure/summary_gateway.py`, `main.py`: 계정의 자격증명으로 실행하는 OpenAI Responses 어댑터와 기본 worker 조립. 모델 응답은 스키마로 검증하고 provider 오류·키 원문은 노출하지 않는다. 어댑터는 [공식 구조화 출력 문서](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)를 기준으로 작성했다.
- `features/results/`, `WorkspacePage.tsx`, `TaskModal.tsx`: 결과 탭 MVI, 연결 확인, 초안 편집·저장·이력, 재연결 조회, 충돌 비교 및 복구.
- `contracts/openapi.json`, 생성된 웹 타입, `docs/contracts.md` v1.6: 승인 저장의 필수 `source_run_id` 추가. 같은 승인 버전에서 초안만 재생성되어도 과거 편집 본문을 새 출처로 저장하지 않게 한다.

마이그레이션 `c84f15b694e2`는 `result_draft.context_snapshot`을 추가한다. 정리를 요청할 때 메시지 범위와 자료·결론 버전 내용을 고정하고 worker가 그 입력을 사용한다. 재정리는 이전 승인 결론과 그 이후 메시지를 사용한다. 승인 저장은 기준 버전의 조건부 변경과 불변 버전 추가를 같은 트랜잭션에서 처리한다.

저장 충돌이나 SSE 갱신은 편집 중인 본문과 기준 출처를 자동으로 덮지 않는다. 최신 승인 결론 또는 새로 정리된 초안을 비교한 뒤 사용자가 명시적으로 편집 기준을 갱신할 수 있다. 네트워크 오류 후 같은 저장을 재시도할 때는 같은 멱등 키를 사용한다.

검증은 PostgreSQL의 임시 테스트 DB와 FakeLLM 또는 메모리 HTTP 전송으로 실행했다. 개발·공유 DB를 초기화하거나 실제 AI를 호출하지 않았다.

- 최종 `pnpm verify` 9개 검사 모두 통과(실패·생략 없음). API 단위 테스트 587개와 통합 테스트 190개, 총 777개 통과.
- 웹 전체 테스트 323개 통과. 결과 기능 단위 테스트 20개를 포함한다.
- 브라우저 B4 시나리오 5개: v1/v2와 실패 보존, 승인 충돌과 SSE 초안 보존, 재생성 출처 충돌 복구, AI 연결 취소·재개, 실제 서버 저장·재조회.
- 기존 작업 모달·AI 연결 브라우저 회귀 시나리오 5개도 통과했다. 이 테스트들은 자체 서버 fixture가 없어 별도로 실행한 Vite 서버를 사용했다.
- API 정적 검사, OpenAPI·타입 생성 및 계약 검사 188개, 웹 타입 검사·프로덕션 빌드·한글 문구 검사 통과. 1440px 결과 화면 스크린샷도 확인했다.

후속 B5 결론 보기의 보내기·새 대화 액션, B6·B7·B8, 실제 키를 사용한 수동 모델 검증은 이 작업에 포함하지 않는다.
