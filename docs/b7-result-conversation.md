# B7 결과로 새 대화

저장한 결론의 결과 탭 또는 대화 오른쪽의 연결된 결론에서 시작한다. 보고 있는 버전 하나를 고정한 뒤 같은 모달에서 프로젝트를 검색·선택하고 제목을 입력한다. 성공하면 모달을 닫고 선택한 프로젝트의 최상위 대화로 이동한다.

## 동작과 경계

- 프로젝트 검색은 현재 참여 권한이 있는 프로젝트를 반환한다. 생성 시 원본 결론 사용 권한과 대상 프로젝트 권한을 다시 확인한다.
- 대화와 `conversation_input` 스냅샷은 멱등 receipt와 같은 트랜잭션으로 저장한다. 응답을 잃은 재시도는 같은 키를 사용하며, 중복 대화와 이벤트를 만들지 않는다.
- 과거 버전을 선택해도 그 버전의 제목·본문·출처가 고정된다. 다른 프로젝트에 원본 메시지·스킬·자료를 복사하지 않으며 생성만으로 AI를 실행하지 않는다.
- 원본 접근 권한이 없는 수신자도 자신이 받은 결론 버전은 열고 새 대화의 입력으로 사용할 수 있다. 상세 조회는 수신 대화와 입력 ID를 함께 확인하며 저장된 스냅샷만 반환한다. 원본의 다른 버전·대화·자료 접근 권한은 부여하지 않는다.
- 생성 실패 시 제목과 결론을 유지한다. 대상 권한이 바뀌면 프로젝트를 다시 선택하도록 안내한다. 뒤로가기는 결론 보기로 돌아간다.
- 다른 프로젝트에서 가져온 결론도 받은 프로젝트 안의 다른 대화에 고정 버전 그대로 보낼 수 있다. 받지 않은 최신 버전이나 새로운 프로젝트로의 직접 전송 권한은 부여하지 않는다.

## API

| 경로 | 역할 |
|---|---|
| `GET /api/projects/search?q=...` | 대화를 생성할 수 있는 프로젝트 검색 |
| `POST /api/projects/{project_id}/conversations/from-result` | `{result_revision_id, title}`로 최상위 대화와 고정 입력 생성 |
| `GET /api/conversations/{conversation_id}/inputs` | 대화에 연결된 결론 제목·고정 버전 조회 |
| `GET /api/conversations/{conversation_id}/inputs/{input_id}` | 정확한 수신 입력의 본문·출처 스냅샷 조회 |

## 검증

| 기준 | 검증 파일 |
|---|---|
| AC-11, ON-AC-12: 프로젝트 검색·권한 변경 | `apps/api/tests/test_result_followups_integration.py`, `apps/web/tests/result-conversation-model.test.ts`, `tests/e2e/result-conversation.spec.ts` |
| AC-12: 최상위 생성·성공 후 이동·멱등 재시도 | 같은 API 통합 테스트, `apps/web/tests/result-conversation-effects.test.ts`, B7 E2E |
| AC-13: 선택 버전 하나·다른 자원 복사 없음·AI 자동 실행 없음 | API 통합 테스트의 DB·ContextProvider 검증, 실제 서버 B7 E2E |
| 받은 결론 재사용·원본 접근 격리 | API 통합 테스트의 수신자 권한·저장 스냅샷 검증, `apps/web/tests/sharing-received.test.ts`, 수신자 B7 E2E |

API 통합·E2E는 `ramus_test_*` 임시 DB와 FakeLLM을 사용한다. 실제 모델 호출이나 운영 데이터 변경은 하지 않는다. 실행 결과는 PR에 기록한다.
