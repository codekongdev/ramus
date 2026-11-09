# A8 프로젝트 전환과 생성

상단 프로젝트명을 누르면 참여 중인 프로젝트 목록을 연다. 이름으로 필터링하고 프로젝트를 선택하면 해당 프로젝트의 대화·작업·참여자와 SSE 연결을 사용한다. 현재 프로젝트를 선택하면 대화를 유지하고 모달만 닫는다.

`새 프로젝트`에서 이름을 입력하고 만들면 새 프로젝트로 이동한다. 새 프로젝트는 공동 샘플이 아니며 생성자만 편집 참여자로 등록된다. 다른 계정의 로그인은 기존 공동 샘플에만 자동 참여한다. 주소에 프로젝트와 대화 ID를 남겨 새로고침과 브라우저 방문 기록으로 복원한다.

## 구현 경계

- `projects.application.CreateProject`가 프로젝트·생성자 편집 권한·멱등 receipt를 하나의 트랜잭션으로 저장한다. 권한 등록은 `access.public.MembershipWriter`를 통해 처리한다.
- `POST /api/projects`는 로그인과 `Idempotency-Key`가 필요하다. 같은 계정·키·본문은 같은 프로젝트를 반환하고 다른 본문은 409를 반환한다. 계정이 다르면 같은 키를 사용할 수 있다.
- 프로젝트명은 공백뿐인 값·100자 초과·NUL·UTF-8로 저장할 수 없는 값을 거부한다. 화면은 이름 앞뒤 공백을 제거해 보낸다.
- `GET /api/projects`와 `GET /api/projects/search?q=...`는 본인이 참여한 프로젝트만 반환한다. 검색은 대소문자를 무시한 부분 문자열 검색이며 검색 결과가 없어도 프로젝트를 생성하지 않는다.
- 프론트 `features/projects`는 MVI로 구성한다. Reducer가 요청·선택·생성 상태를 관리하고 EffectHandler가 API와 경로 이동을 담당한다. 생성 실패 시 이름을 유지하며 같은 이름의 재시도는 원래 요청 키를 사용한다.
- 프로젝트가 바뀌면 기존 프로젝트의 화면과 이벤트 연결을 해제한다. 프로젝트 생성은 대화나 샘플 콘텐츠를 자동 생성하지 않는다. 기존 OpenAPI 응답 형태와 DB 스키마를 사용한다.

## 검증

```sh
uv run --project apps/api pytest apps/api/tests/test_project_creation_integration.py apps/api/tests/test_project_domain.py apps/api/tests/test_project_participants_integration.py
pnpm --filter @ramus/web test -- tests/features/projects
pnpm exec playwright test tests/e2e/projects.spec.ts
```

백엔드 통합 테스트는 임시 PostgreSQL DB에서 동시 재시도·계정 격리·멱등 충돌·권한 등록 실패 시 롤백을 확인한다. 브라우저 테스트는 두 계정의 프로젝트 접근 격리, 대화·메시지 저장, 전환·새로고침·방문 기록, 검색·키보드·포커스 복귀, 커밋 후 생성 응답 유실의 재시도를 확인한다. 실제 메일이나 모델을 호출하지 않는다.

프로젝트 관계 지도(A9)와 참여자 초대는 이 변경 범위에 포함하지 않는다. 현재 기준 커밋의 Task API는 별도 구현 중이어서 작업 큐에 기존 오류 안내가 나타날 수 있다.
