# 실행 제어와 MVP 흐름 통합

2026-11-09 · 기준: A9가 병합된 `origin/main`의 `fa44ffa`.

## 변경

- 작업 조회·취소·재시도를 `TaskService`와 `SqlTaskRepository`로 통합했다. 기존 결과 링크를 유지하며 프로젝트 참여자는 조회할 수 있다. 제어는 작업과 현재 업무 Run의 요청자가 모두 일치해야 한다.
- 취소·재시도는 멱등 키와 현재 Run 포인터를 검증한다. Run → 활성 실행 고유 인덱스 → Task 순서로 잠가 새 요청과 재시도 사이의 교착을 피한다. 취소 훅은 해당 Future를 미리 캡처해 다음 시도를 취소하지 않는다.
- 계정별 Responses 어댑터를 `summary_gateway.py`의 `OpenAiGateway` 하나로 정리했다. 엄격한 응답 검증, 출력 상한, 오류별 재시도 가능 여부, 자격 증명 보호와 취소 전파를 적용했다. [공식 출력 계약](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)을 기준으로 한다.
- 최신 main의 `default_gateway` 조립, `LongSummaryGateway`, `SummaryPurposeHandler`, A8·B7 참여자 주입과 A9 관계 지도를 유지했다. 모델을 사용하는 테스트는 명시적으로 어댑터를 주입하며 나머지 API 테스트는 기본 worker를 끈다.

## 검증

`pnpm verify`: 9개 단계 모두 통과, 실패·건너뜀 없음.

- 웹 타입 검사와 499개 테스트
- API lint, 단위 테스트 661개, PostgreSQL 통합 테스트 293개
- OpenAPI·생성 타입 일치, 기능 문구 검사, 검증 스크립트 검사

추가된 검사:

- `test_task_routes_integration.py`: 권한·중복 요청·실행 제어 이벤트·summary Run 제어 거부·포인터 교체·새 요청과 재시도 경합·늦은 응답 폐기
- `test_inflight.py`: 이전 취소 훅이 다음 시도를 중단하지 않는지 확인
- `test_live_gateway_integration.py`: 실제 키 암호화·계정별 게이트웨이 조립·고정 자료 버전, 공유/후속 대화의 구버전 결론이 실제 제공자 요청 본문과 Run 스냅샷에 반영되는지 확인. 외부 HTTP는 메모리 transport로 대체
- `work-execution.spec.ts`: 응답·자동 분기·작업 큐·중단·재시도·부모 초안 보존·새로고침
- `mvp-workflow.spec.ts`: 자료 적용 → 분기 → 정리·승인 → 공유 → 받은 결론으로 AI 요청·정리 → 새 대화 → 결과 목록·관계 지도. 자료와 결론의 원본이 v2로 바뀌어도 적용된 v1과 출처가 유지되는지 확인

`pnpm test:e2e`: 전체 브라우저 검사 39개 통과(약 2분). 다중 계정 로그인·공동 대화·재접속과 각 기능 검사, 새 MVP 연결 검사를 포함한다. 모델 응답은 결정적으로 주입하며, 세 계정이 전체 시연을 함께 수행하는 리허설과 실제 모델 검증은 아래의 남은 확인에 포함한다. 모든 자동 검사는 임시 DB와 합성 키·메일러·모델 경계를 사용하며 기존 개발 데이터는 초기화하지 않는다.

## 남은 확인

- 실제 계정 키로 모델 응답·자료 반영·분기·장문 정리 품질 확인
- BL-02·BL-03은 후속 [운영 메일러 구현](mail-delivery.md)에서 처리했다. 실제 SMTP 계정 연결·메일 도착 확인은 남아 있다.
- 배포 환경·운영 비밀값·HTTPS 설정, 세 계정 시연 리허설

실제 OpenAI 호출, 실제 메일 발송, 공유 데이터 리셋과 배포는 이번 작업에서 실행하지 않았다.
