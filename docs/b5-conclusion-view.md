# B5 결론 보기

## 구현

- `features/results/ConclusionView`를 작업 결과 탭과 `ResultRevisionDialog`에서 함께 사용한다. 사용자 본문은 `conclusion` 하나이며, 모달은 결과 제목과 결론만 보여 준다. B4의 버전 이력·출처·편집 기능은 결과 탭에서 유지한다.
- 작업 결과 탭의 ‘결론 보기’는 `result:<resultRevisionId>` 모달을 연다. 기존 작업 모달은 숨겨 보존하고 닫으면 원래 탭·초안·포커스로 돌아온다. 부모 대화와 URL은 유지한다.
- 모달의 MVI reader는 `GET /api/result-revisions/{id}`만 호출한다. 응답을 스키마와 요청 ID로 검증하고, 대상 전환 시 이전 본문을 비우며, 늦은 응답과 닫힌 화면의 응답을 무시한다. 읽기 실패는 같은 버전으로 재시도한다.
- 선택한 과거 버전은 실시간 갱신에도 유지한다. 새 버전 저장이나 명시적인 ‘최신 버전 확인’은 과거 조회 요청을 무효화한다. 과거 버전 조회 실패의 재시도도 같은 버전을 대상으로 한다.
- ‘새 대화 만들기’와 ‘다른 대화에 보내기’는 같은 강조·너비로 나란히 배치한다. `ConclusionActions` 콜백은 클릭할 때 화면에 표시된 정확한 `ResultRevision`을 전달한다. 열기·닫기는 콜백을 실행하지 않는다.

## 후속 연결 범위

- B6의 받은 결론 목록은 `ResultRevisionDialog`를 `result:<id>`로 열면 된다. `GET /conversations/{id}/inputs`와 우측 목록·검색·보내기는 B6에 남아 있다.
- B6/B7이 실제 전송·새 대화 화면을 연결하기 전에는 두 버튼을 비활성화한다. 현재 미구현 API를 호출하거나 성공으로 표시하지 않는다. 같은 모달 본문 전환은 후속 기능이 담당한다.
- 현재 revision 조회 권한은 원본 프로젝트 참여자를 기준으로 한다. 원본 프로젝트에 접근할 수 없는 다른 프로젝트의 참여자가 스냅샷을 읽는 경로는 B7에서 별도 연결해야 한다.

## 검증 (2026-11-09)

- `pnpm verify`: 9개 검사 PASS, FAIL/SKIP 없음. API 단위 621개·통합 238개와 OpenAPI/생성 타입 계약 검사 포함.
- 후속 UI 보완 뒤 `pnpm verify --only web,i18n`: 타입 검사·프론트 45파일/448테스트·문구 검사 통과. 마지막 충돌 안내 보완 뒤 관련 5파일/39테스트도 통과.
- `pnpm --filter @ramus/web build`: 프로덕션 빌드 통과.
- `pnpm test:e2e tests/e2e/results.spec.ts`: 8개 통과. 실제 격리 DB의 저장·재열람, 열기·닫기의 변경 요청 부재, 부모 초안·스크롤·URL·포커스 유지, 실시간 갱신 중 과거 버전 유지, 375px 긴 본문·동일 너비 버튼 확인.
- 별도 로컬 Vite 서버를 지정한 `RAMUS_WEB_PORT=5185 pnpm test:e2e tests/e2e/task-ui.spec.ts`: 기존 작업 모달 3개 통과. 이 파일은 서버 fixture를 사용하지 않으므로 먼저 개발 서버를 실행해야 한다.
- `git diff --check` 통과. 데스크톱·모바일 캡처는 로컬 `artifacts/b5-conclusion-{desktop,mobile}.png`에서 확인했다.
- 기존 React `act` 및 Starlette deprecation 경고가 있다. 실제 모델 호출과 B6/B7 이후의 받은 결과 전체 흐름은 검증하지 않았다.
