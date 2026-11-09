# ramus 계약 v1.3

확정일: 2026-11-09 · 작업자: 메이슨, 헤이든 · 상태: 확정

이 문서는 두 트랙이 함께 의존하는 API·실시간 이벤트·데이터·포트·화면 연결 규칙의 기준이다. `docs/roadmap.md`의 부록 A·B는 초안이며, 이 문서와 다르면 이 문서를 따른다. 기능의 의미는 `docs/spec/`의 와이어프레임 v1.4와 기획서 v1.7을 따른다.

변경은 로드맵 6.3의 계약 변경 절차로만 한다. 계약만 바꾸는 작은 PR을 먼저 올리고, 상대가 확인한 뒤 병합한다. 변경할 때마다 아래 변경 이력에 한 줄을 남긴다.

## 0. 이미 구현된 항목

계약 회의 전에 기반 작업에서 정해진 항목이다. 이 문서는 이 구현을 기준으로 삼는다.

| 항목 | 구현 위치 | 내용 |
|---|---|---|
| 오류 응답 | P0-A1 `shared/presentation/errors.py` | 모든 오류 본문은 `{"error": {"code", "message", "details"}}`이다. `message`는 사용자에게 보여 줄 한국어 문장이다. 입력 검증 실패는 422 `INVALID_INPUT`이며 `details`에 위치·유형·메시지만 담고 입력값은 돌려주지 않는다 |
| 멱등 키 | P0-A1 `shared/presentation/idempotency.py`, `receipts.py` | 변경 요청은 `Idempotency-Key` 헤더가 필수다. 1~128자, `[A-Za-z0-9._:-]`. 헤더가 없거나 형식이 틀리면 400 `IDEMPOTENCY_KEY_INVALID`, 같은 키로 다른 본문을 보내면 409 `IDEMPOTENCY_CONFLICT`, 같은 키와 같은 본문은 저장된 응답을 그대로 돌려준다 |
| 포트 설정 | P0-A1 `settings.py`, `vite.config.ts` | `RAMUS_WEB_PORT`(기본 5173), `RAMUS_API_PORT`(기본 8000). 웹 개발 서버는 `/api`를 API 서버로 프록시한다 |
| URL 구조 | P0-B1 `app/routing/route.ts` | `/login`, `/`, `/projects/:projectId`, `/projects/:projectId/conversations/:conversationId`. 작업 모달·결론 보기는 URL을 바꾸지 않는다 |
| 모달 호스트 | P0-B1 `app/modal/` | 한 번에 모달 하나만 띄운다. 새로 열면 기존 모달을 대체한다. `useModalHost().openModal({ id, render })`, 모달 안의 화면 단계는 각 기능의 상태로 관리한다 |

## 1. 공통 규칙

| 항목 | 규칙 |
|---|---|
| 경로 | 모든 API는 `/api`로 시작한다. 웹과 같은 출처에서만 호출하며 CORS는 열지 않는다 |
| 이름 기준 | 필드·타입(컴포넌트)·경로 매개변수·`operation_id`의 실제 이름은 `contracts/openapi.json`을 따른다. 이 문서의 `{id}`는 설명용이며 실제 경로는 `{conversation_id}`처럼 대상 이름을 쓴다. 이 문서에서 이름 없이 적은 작은 객체(`{status}` 등)도 OpenAPI에서는 이름 있는 타입이다. 생성 파일은 `pnpm gen:api`로 만들고 손으로 고치지 않는다 |
| 필드 이름 | JSON 필드는 `snake_case`를 쓴다. 프론트는 생성된 타입의 이름을 그대로 쓴다 |
| 식별자 | UUID 문자열. 시드 데이터는 고정 시드 키로 만든 UUIDv5를 써서 다시 실행해도 같은 ID가 나온다 |
| 시각 | ISO 8601 UTC(`2026-11-09T04:17:23Z`) |
| 성공 응답 | 감싸지 않고 리소스를 그대로 돌려준다. 성공 여부는 HTTP 상태로 판단한다 |
| 목록 응답 | `{"items": [...]}` 객체. 페이지가 필요한 목록(메시지)만 커서 필드를 더한다 |
| 변경 응답 | 모든 변경 요청은 JSON 객체를 돌려준다. 돌려줄 리소스가 없으면 `{}`를 돌려준다(멱등 receipt 저장 조건) |
| 변경 요청 | `POST`·`PUT`·`DELETE`는 `Content-Type: application/json`과 `Idempotency-Key`가 필수다. 로그인 전 요청(인증 코드 요청·확인)도 같다. 요청이 `{}`인 엔드포인트(로그아웃, 작업 중단·재시도, 결과 정리)도 빈 JSON 객체 본문을 보낸다 |
| 멱등 범위 | receipt는 (행위자, 범위, 키)로 구분한다. 로그인 전 요청의 행위자는 `anonymous`다. 프론트는 사용자 행동 하나마다 키를 하나 만들고, 그 행동을 재시도할 때 같은 키를 다시 쓴다 |
| 낙관적 잠금 | 버전이 있는 대상(결과, 공통 자료)은 기준 버전을 함께 보내고, 최신 버전과 다르면 409 `VERSION_CONFLICT`를 돌려준다. `details`에 최신 버전 정보를 담는다 |
| 권한 | 프로젝트 하위 리소스는 그 프로젝트의 참여자만 조회·변경한다. 참여자가 아니면 존재를 알리지 않도록 404 `NOT_FOUND`를 돌려준다. 로그인하지 않았으면 401 `UNAUTHORIZED` |
| 오류 문장 | 응답의 `error.message`와 `Run`·`Task`·`ResultDraft`의 `error.message`는 응답을 만들 때 오류 코드와 매개변수로 문구표에서 만든다. DB에는 사용자에게 보여 줄 문장을 저장하지 않는다(로드맵 9.3) |
| 길이 제한 | 대화·결과 제목 100자, 메시지 본문 20,000자, 결론 본문 20,000자, 공통 자료 지침·내용 100,000자, 한 번에 보낼 대상 대화 20개, 한 번에 분기할 작업 4개 |

### 1.1 인증과 세션

| 항목 | 규칙 |
|---|---|
| 인증 코드 | 숫자 6자리, 해시로 저장, 10분 후 만료, 코드당 5회까지 확인, 같은 이메일 재요청은 60초 간격 |
| 메일 발송 | `Mailer` 포트. 개발 환경은 서버 로그에 코드를 출력하고, 시연 환경은 실제 발송 서비스를 쓴다(로드맵 D3) |
| 세션 | 쿠키 `ramus_session`. `HttpOnly`, `SameSite=Lax`, `Path=/`, HTTPS 환경에서는 `Secure`. 14일 후 만료. DB에는 토큰 해시만 저장한다 |
| 공동 샘플 | 로그인에 성공하면 고정 ID의 공동 샘플 프로젝트에 편집 참여자로 등록한다. 이미 참여 중이면 그대로 둔다 |
| CSRF | 같은 출처 호출만 허용하고, 변경 요청에 JSON 본문과 사용자 정의 헤더(`Idempotency-Key`)를 요구해 다른 사이트의 폼 전송을 막는다 |

### 1.2 업무 오류 코드

HTTP 상태별 기본 코드(`BAD_REQUEST`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT` 등)는 P0-A1 구현을 따른다. 기능별 코드는 아래와 같다. 프론트는 `code`로 분기하고 화면에는 `message`를 보여 준다.

| 코드 | 상태 | 상황 |
|---|---|---|
| `INVALID_INPUT` | 422 | 요청 본문 검증 실패 |
| `NOT_IMPLEMENTED` | 501 | 아직 구현하지 않은 엔드포인트(P0-A3 스텁) |
| `IDEMPOTENCY_KEY_INVALID` | 400 | 멱등 키 없음·형식 오류 |
| `IDEMPOTENCY_CONFLICT` | 409 | 같은 키로 다른 본문 |
| `AUTH_CODE_INVALID` | 422 | 인증 코드 불일치 |
| `AUTH_CODE_EXPIRED` | 422 | 인증 코드 만료·확인 횟수 초과 |
| `AUTH_RATE_LIMITED` | 429 | 인증 코드 재요청 간격 위반 |
| `AI_CONNECTION_REQUIRED` | 409 | 키가 연결되지 않은 계정이 AI 실행을 요청함. 메시지는 저장하지 않는다 |
| `AI_KEY_INVALID` | 422 | 키 확인 호출 실패 |
| `ACTIVE_RUN_EXISTS` | 409 | 같은 대화에 활성 AI 실행이 있음. 메시지는 저장하지 않는다 |
| `RUN_NOT_CANCELLABLE` | 409 | 이미 끝난 작업의 중단 요청 |
| `RUN_NOT_RETRYABLE` | 409 | failed·cancelled가 아닌 작업의 재시도 요청 |
| `TASK_NOT_READY` | 409 | 실행이 끝나지 않은 작업의 결과 정리 요청 |
| `VERSION_CONFLICT` | 409 | 기준 버전이 최신 버전과 다름 |
| `FILE_TYPE_UNSUPPORTED` | 422 | `.md`·`.txt`가 아니거나 UTF-8 텍스트가 아님(D9) |
| `SHARE_TARGET_INVALID` | 422 | 보낼 대상이 없음(`conversation_ids`가 빈 목록이어도 `INVALID_INPUT`이 아니라 이 코드), 다른 프로젝트, 결과의 출처 대화 |
| `PROJECT_CREATE_FORBIDDEN` | 403 | 대상 프로젝트에 대화를 만들 권한이 없음 |

### 1.3 실행 실패 코드

`Run`의 `error.code`로 내려가는 코드다. HTTP 응답의 오류 코드가 아니다. 실행기는 코드를 `run.error_code`에 저장하고, 응답을 만들 때 문구표로 `error.message`를 만든다. 게이트웨이가 아래 표에 없는 코드를 돌려주면 `LLM_UNAVAILABLE`로 저장한다.

| 코드 | 상황 |
|---|---|
| `LLM_UNAVAILABLE` | 모델 호출 실패, 결과 반영 중 오류처럼 원인을 사용자에게 구분해 알릴 필요가 없는 실패 |
| `LLM_OUTPUT_INVALID` | 모델 출력이 6.1의 스키마와 맞지 않음 |
| `LLM_TIMEOUT` | 모델 응답이 제한 시간 안에 오지 않음 |
| `RUN_INTERRUPTED` | running 상태에서 heartbeat가 끊김(서버 재시작 등). 자동으로 다시 실행하지 않는다(C8) |
| `RUN_TIMED_OUT` | pending 상태로 너무 오래 대기함(F-03) |
| `RUN_CREDENTIAL_MISMATCH` | 핸들러가 만든 모델 요청의 키 계정이 실행의 `credential_account_id`와 다름. 모델을 호출하지 않는다(ON-AC-08) |

재시도할 수 있는지는 실패 코드가 아니라 상태로만 판단한다. failed·cancelled 실행은 코드와 관계없이 요청자가 재시도할 수 있다. `RunError.retryable`은 핸들러에 넘기는 값이며 DB에는 저장하지 않는다.

## 2. 공통 데이터 형태

응답 예시가 아니라 필드 목록이다. 선택 필드는 `| null`로 표시한다.

| 이름 | 필드 |
|---|---|
| `Account` | `id`, `email`, `display_name` |
| `Me` | `account: Account`, `default_project_id`, `ai_connection: {status: "none" \| "connected" \| "invalid"}` |
| `Project` | `id`, `name`, `is_shared_sample` |
| `Conversation` | `id`, `project_id`, `parent_id \| null`, `task_id \| null`, `title`, `path: string[]`(상위 대화 제목, 동명 대화 구분용), `created_by`, `created_at` |
| `Message` | `id`, `conversation_id`, `seq`, `author: {kind: "human" \| "ai" \| "system", account_id \| null, display_name}`, `body`, `requested_by \| null`, `run_id \| null`, `is_example`, `created_at` |
| `Run` | `id`, `conversation_id`, `task_id \| null`, `purpose: "work" \| "summary"`, `status: "pending" \| "running" \| "succeeded" \| "failed" \| "cancelled"`, `requested_by`, `created_at`, `started_at \| null`, `finished_at \| null`, `error: {code, message} \| null` |
| `Task` | `id`, `source_conversation_id`, `child_conversation_id`, `title`, `goal`, `status: "pending" \| "running" \| "ready" \| "failed" \| "cancelled"`, `requested_by`, `result_id \| null`, `created_at`, `started_at \| null`, `finished_at \| null`, `error: {code, message} \| null` |
| `ResourceSummary` | `id`, `kind: "skill" \| "text" \| "file"`, `latest: {revision_id, number, name, description}`, `applied: {revision_id, number} \| null`(요청한 대화에 적용된 버전) |
| `ResourceRevision` | `id`, `resource_id`, `number`, `name`, `description`, `instructions \| null`(skill), `content \| null`(text·file), `file_name \| null`, `created_by`, `created_at` |
| `ResourceDetail` | `id`, `kind`, `latest_revision_id`, `revisions: [{id, number, name, created_by, created_at}]`, `revision: ResourceRevision`(선택한 버전, 기본은 최신) |
| `AppliedResource` | `resource_id`, `revision_id`, `number`, `name`, `kind` |
| `ResultDraft` | `status: "generating" \| "ready" \| "failed"`, `conclusion \| null`, `base_version`(최신 승인 버전, 없으면 0), `run_id`, `error: {code, message} \| null`, `updated_at` |
| `Result` | `id`, `project_id`, `title`, `source_conversation_id`, `source_task_id`, `latest_version \| null`, `latest_revision_id \| null`, `draft: ResultDraft \| null`, `revisions: [{id, version, saved_by, created_at}]` |
| `ResultRevision` | `id`, `result_id`, `version`, `title`, `conclusion`, `source: {conversation_id, message_from_seq, message_to_seq, resource_revision_ids, input_result_revision_ids, run_id}`, `saved_by`, `created_at` |
| `ConversationInput` | `id`, `conversation_id`, `result_id`, `result_revision_id`, `version`, `title`, `latest_version`(원본 결과의 현재 최신 버전), `origin: "share" \| "new_conversation"`, `created_by`, `created_at` |

## 3. 엔드포인트

### 3.1 트랙 A

| 메서드·경로 | 요청 | 응답 | 비고 |
|---|---|---|---|
| `POST /api/auth/email-code` | `{email}` | 202 `{resend_available_at}` | 코드 발송. 계정 존재 여부를 알리지 않는다 |
| `POST /api/auth/verify` | `{email, code}` | `Me` + 세션 쿠키 | 계정이 없으면 만들고 공동 샘플에 참여시킨다 |
| `POST /api/auth/logout` | `{}` | `{}` | 세션 폐기 |
| `GET /api/me` | | `Me` | 프론트는 `/` 진입 시 `default_project_id`로 이동한다 |
| `GET /api/me/ai-connection` | | `{status}` | |
| `PUT /api/me/ai-connection` | `{api_key}` | `{status: "connected"}` | 저비용 호출로 키를 확인한 뒤 암호화해 저장. 실패 시 `AI_KEY_INVALID` |
| `DELETE /api/me/ai-connection` | | `{status: "none"}` | 이후 새 실행 불가. 이미 접수한 실행은 키 조회 시점에 실패 처리 |
| `GET /api/projects` | | `{items: Project[]}` | 참여 중인 프로젝트 |
| `POST /api/projects` | `{name}` | `Project` | 만든 사람을 편집 참여자로 등록 |
| `GET /api/projects/search?q=` | | `{items: Project[]}` | 대화를 만들 권한이 있는 프로젝트. 현재 프로젝트 포함 |
| `GET /api/projects/{project_id}/conversations` | | `{items: Conversation[]}` | 트리 전체. `parent_id`로 구성 |
| `POST /api/projects/{project_id}/conversations` | `{title}` | `Conversation` | 최상위 대화 |
| `GET /api/projects/{project_id}/conversations/search?q=&exclude_id=` | | `{items: Conversation[]}` | 제목 검색. 보내기 화면에서 사용 |
| `GET /api/conversations/{id}` | | `Conversation` + `active_run: Run \| null` | |
| `GET /api/conversations/{id}/messages?after_seq=&limit=` | | `{items: Message[], next_after_seq \| null}` | `limit` 기본 100, 최대 200 |
| `POST /api/conversations/{id}/messages` | `{body}` | `{message: Message, run: Run \| null}` | 서버가 본문에서 `@AI`(대소문자 무시)를 찾아 실행을 등록한다. 키가 없거나 활성 실행이 있으면 저장하지 않고 409 |
| `GET /api/conversations/{id}/tasks` | | `{items: Task[]}` | 이 대화에서 분기된 작업(오른쪽 큐) |
| `GET /api/tasks/{id}` | | `Task` | |
| `POST /api/tasks/{id}/cancel` | `{}` | `Task` | 요청자만 가능, 아니면 403 |
| `POST /api/tasks/{id}/retry` | `{}` | `Task` | 요청자만 가능. 요청자의 키로 다시 실행 |
| `GET /api/projects/{project_id}/events` | | SSE | 4장 |
| `GET /api/projects/{project_id}/graph` | | `{nodes: [{conversation_id, title, parent_id \| null, task_status \| null}], edges: [{kind: "branch" \| "uses_result", from, to}]}` | 관계 보기(A9). 조회 전용 |

### 3.2 트랙 B

| 메서드·경로 | 요청 | 응답 | 비고 |
|---|---|---|---|
| `GET /api/projects/{project_id}/resources?q=&conversation_id=` | | `{items: ResourceSummary[]}` | 이름·설명 검색. `conversation_id`를 주면 `applied`를 채운다 |
| `POST /api/projects/{project_id}/resources` | `{kind, name, description, instructions \| null, content \| null, file_name \| null}` | `ResourceDetail` | v1 생성. SKILL.md 등 파일은 프론트가 텍스트로 읽어 보낸다(D9) |
| `GET /api/resources/{id}?revision_id=` | | `ResourceDetail` | 상세·이력(WF-17) |
| `POST /api/resources/{id}/revisions` | `{base_revision_id, name, description, instructions \| null, content \| null, file_name \| null}` | `{revision: ResourceRevision, created: boolean}` | 새 버전 저장(WF-18). 기준이 최신이 아니면 `VERSION_CONFLICT`. 최신과 내용이 같으면 새 버전을 만들지 않고 `created: false` |
| `GET /api/conversations/{id}/resources` | | `{items: AppliedResource[]}` | 대화에 적용한 버전 |
| `PUT /api/conversations/{id}/resources` | `{revision_ids: string[]}` | `{items: AppliedResource[]}` | 적용 목록 전체 교체. 자원당 버전 하나. 같은 프로젝트의 버전만 허용 |
| `POST /api/tasks/{task_id}/summaries` | `{}` | `Result` | 결과 정리 실행 등록. 요청한 계정의 키 사용. 작업이 ready가 아니면 `TASK_NOT_READY`. 이미 정리 중이면 기존 실행을 돌려준다 |
| `GET /api/results/{id}` | | `Result` | |
| `GET /api/result-revisions/{id}` | | `ResultRevision` | 결론 보기 |
| `POST /api/results/{id}/revisions` | `{base_version, conclusion}` | `ResultRevision` | 승인 저장. `base_version`이 최신이 아니면 `VERSION_CONFLICT` |
| `GET /api/projects/{project_id}/results` | | `{items: [{result_id, title, latest_version, latest_revision_id, source_conversation_title, updated_at}]}` | 결과물 목록(조회 전용). 저장된 결과만 |
| `POST /api/result-revisions/{id}/shares` | `{conversation_ids: string[]}` | `{items: [{conversation_id, outcome: "linked" \| "replaced" \| "unchanged" \| "kept_newer"}]}` | 대상별로 Share와 ConversationInput을 함께 만든다. 새 버전이면 교체(D8), 같은 버전이면 변경 없음, 대상에 더 새 버전이 이미 있으면 유지 |
| `GET /api/conversations/{id}/inputs` | | `{items: ConversationInput[]}` | 오른쪽 공유받은 결과 목록. 이 대화의 AI 입력과 같다 |
| `POST /api/projects/{project_id}/conversations/from-result` | `{result_revision_id, title}` | `Conversation` | 대상 프로젝트 최상위에 생성하고 결론 버전 스냅샷을 입력으로 연결(origin `new_conversation`) |

## 4. 실시간 이벤트(SSE)

| 항목 | 규칙 |
|---|---|
| 연결 | `GET /api/projects/{project_id}/events`. 세션 쿠키로 인증하고 참여자만 연결한다 |
| 형식 | `event: <이벤트 이름>` + `data: <JSON>`. `data`에는 항상 `occurred_at`이 들어간다 |
| 유지 | 서버는 15초마다 주석 줄(`: ping`)을 보낸다 |
| 재접속 | 서버는 지난 이벤트를 다시 보내지 않는다. 클라이언트는 연결이 열릴 때마다 필요한 상태를 다시 조회한다 |
| 세션 만료 | `EventSource`는 HTTP 상태를 알 수 없으므로, 연결 오류가 나면 클라이언트가 `GET /api/me`를 호출한다. 401이면 재접속을 멈추고 로그인 화면으로 이동한다 |
| 내용 | 식별자와 바뀐 상태만 담는다. 메시지·결론·자료 본문, API 키, 다른 계정의 자격증명 정보는 넣지 않는다 |

| 이벤트 | `data` 필드 | 발행 | 클라이언트 동작 |
|---|---|---|---|
| `member.joined` | `project_id`, `account: {id, display_name}` | A | 참여자 목록 갱신 |
| `conversation.created` | `project_id`, `conversation: Conversation` | A·B | 트리에 추가 |
| `message.created` | `conversation_id`, `message_id`, `seq` | A | 열려 있는 대화면 `after_seq`로 조회 |
| `run.updated` | `conversation_id`, `run: {id, purpose, status, task_id \| null, requested_by}` | A | 진행 표시, 입력 대기 안내 |
| `task.updated` | `source_conversation_id`, `task: {id, title, status, child_conversation_id, result_id \| null}` | A | 큐 갱신. ready가 되어도 모달을 열지 않는다 |
| `resource.updated` | `project_id`, `resource_id`, `latest_revision_id`, `latest_number` | B | 스킬·자료 목록의 최신 버전 표시 갱신 |
| `conversation_resources.updated` | `conversation_id` | B | 적용 목록 다시 조회 |
| `result.updated` | `result_id`, `task_id`, `draft_status \| null`, `latest_version \| null` | B | 결과 탭·결론 보기 갱신 |
| `conversation_inputs.updated` | `conversation_id` | B | 공유받은 결과 목록 다시 조회 |

프론트의 이벤트 타입과 경계 검증은 `apps/web/src/lib/events.ts` 한 곳에 둔다.

## 5. 테이블 스키마

`request_receipt`는 P0-A1에서 이미 만들었다. 나머지는 P0-A2의 마이그레이션 하나로 만든다. 모든 테이블은 `created_at`을 가지며 아래 표에서는 생략한다.

| 테이블 | 모듈 | 주요 컬럼 | 제약·인덱스 |
|---|---|---|---|
| `project` | projects | `id`, `name`, `is_shared_sample`, `seed_key \| null` | `seed_key` 고유 |
| `account` | access | `id`, `email`(소문자 정규화), `display_name` | `email` 고유 |
| `membership` | access | `account_id`, `project_id`, `role`(`editor`) | PK(`account_id`, `project_id`) |
| `email_code` | access | `id`, `email`, `code_hash`, `expires_at`, `attempts`, `consumed_at \| null` | (`email`, `created_at`) 인덱스 |
| `session` | access | `id`, `account_id`, `token_hash`, `expires_at`, `revoked_at \| null` | `token_hash` 고유 |
| `ai_connection` | access | `account_id`, `provider`(`openai`), `ciphertext`, `status`, `verified_at` | PK(`account_id`). 키 원문·끝자리는 저장하지 않는다 |
| `conversation` | conversations | `id`, `project_id`, `parent_id \| null`, `task_id \| null`, `title`, `origin`(`top` \| `branch` \| `from_result`), `created_by`, `seed_key \| null` | (`project_id`, `title`) 인덱스 |
| `message` | conversations | `id`, `conversation_id`, `seq`, `author_kind`, `author_account_id \| null`, `example_author_label \| null`, `body`, `requested_by \| null`, `run_id \| null` | (`conversation_id`, `seq`) 고유 |
| `task` | execution | `id`, `source_conversation_id`, `child_conversation_id`, `source_run_id`, `ordinal`, `title`, `goal`, `status`, `current_run_id`, `requested_by`, `started_at`, `finished_at`, `error_code`, `error_params`(JSONB) | `child_conversation_id` 고유, (`source_run_id`, `ordinal`) 고유(분기 중복 방지) |
| `run` | execution | `id`, `project_id`, `conversation_id`, `task_id \| null`, `purpose`, `target_id \| null`(summary면 `result_id`), `status`, `requested_by`, `credential_account_id`, `input_snapshot`(JSONB), `attempt`, `heartbeat_at`, `started_at`, `finished_at`, `error_code`, `error_params`(JSONB) | 부분 고유: (`conversation_id`) where `purpose='work'` and `status in (pending, running)`. 부분 고유: (`target_id`) where `purpose='summary'` and `status in (pending, running)`. (`status`, `created_at`) 인덱스 |
| `resource` | resources | `id`, `project_id`, `kind`, `latest_revision_id`, `created_by`, `seed_key \| null` | |
| `resource_revision` | resources | `id`, `resource_id`, `number`, `name`, `description`, `instructions \| null`, `content \| null`, `file_name \| null`, `content_hash`, `base_revision_id \| null`, `created_by` | (`resource_id`, `number`) 고유. 저장 후 수정하지 않는다 |
| `conversation_resource` | resources | `conversation_id`, `resource_id`, `revision_id`, `applied_by`, `applied_at` | PK(`conversation_id`, `resource_id`). 최신 버전으로 자동 해석하지 않는다 |
| `result` | results | `id`, `project_id`, `source_conversation_id`, `source_task_id`, `title`, `latest_revision_id \| null`, `latest_version`(없으면 0) | `source_task_id` 고유 |
| `result_draft` | results | `result_id`, `status`, `conclusion \| null`, `base_version`, `run_id`, `message_from_seq`, `message_to_seq`, `error_code`, `error_params`(JSONB), `updated_at` | PK(`result_id`). 생성된 초안만 저장하고 편집 중 내용은 클라이언트에 둔다 |
| `result_revision` | results | `id`, `result_id`, `version`, `title`, `conclusion`, `source`(JSONB), `saved_by` | (`result_id`, `version`) 고유. 저장 후 수정하지 않는다 |
| `share` | sharing | `id`, `result_revision_id`, `target_conversation_id`, `shared_by` | (`result_revision_id`, `target_conversation_id`) 고유 |
| `conversation_input` | sharing | `id`, `conversation_id`, `result_id`, `result_revision_id`, `version`, `title_snapshot`, `conclusion_snapshot`, `source_snapshot`(JSONB), `origin`, `created_by`, `updated_at` | (`conversation_id`, `result_id`) 고유. 새 버전을 보내면 이 행을 갱신한다(D8) |
| `seed_marker` | seed | `key`, `version`, `applied_at` | PK(`key`) |

실패 정보는 `error_code`와 `error_params`로만 저장한다. `error_params`는 문구에 들어갈 값(예: 실패한 자료 이름)만 담고, 문장은 응답을 만들 때 요청 언어의 문구표로 만든다. 모델 제공자의 원문 오류 같은 운영용 상세 원인은 DB에 저장하지 않고 서버 로그에만 남긴다.

`run.input_snapshot`에는 실행에 실제로 쓴 메시지 범위(`message_from_seq`, `message_to_seq`), 자원 버전 ID 목록, 결론 버전 ID 목록을 기록한다. 스냅샷은 실행기가 실행을 점유하는 트랜잭션에서 만들고, 같은 트랜잭션에서 그 컨텍스트로 모델 요청을 만든다. 그래서 기록된 버전 ID와 실제 입력이 항상 같다. 등록할 때는 빈 스냅샷을 저장한다. 실행이 시작된 뒤에는 설정이 바뀌어도 그 실행의 입력이 바뀌지 않는다. 재시도하면 새 시도를 점유할 때 다시 기록한다. 메시지 범위는 work 핸들러를 만들 때(A2) 넘기는 방법을 정하며, 그전까지는 null이다.

`run.heartbeat_at`은 running 상태에서는 실행기가 마지막으로 보낸 생존 신호의 시각이다. 재시도로 pending에 돌아간 실행에서는 다시 대기열에 들어간 시각이다. pending 장기 대기는 `COALESCE(heartbeat_at, created_at)`을 기준으로 판정한다.

## 6. 백엔드 포트

트랙 사이의 호출은 아래 포트로만 한다. 구현이 병합되기 전에는 각 트랙이 가짜 구현으로 개발한다. 모든 메서드는 호출한 UseCase의 트랜잭션 안에서 실행된다.

```python
# resources·sharing(B)가 구현하고 execution(A)이 사용한다.
class ContextProvider(Protocol):
    def snapshot(self, session: Session, conversation_id: UUID) -> ConversationContext: ...
    def copy_resources(self, session: Session, source_conversation_id: UUID, target_conversation_id: UUID) -> None: ...

@dataclass(frozen=True)
class ResourceInput:
    resource_id: UUID
    revision_id: UUID
    kind: str
    name: str
    instructions: str | None
    content: str | None

@dataclass(frozen=True)
class ResultInput:
    result_id: UUID
    result_revision_id: UUID
    version: int
    title: str
    conclusion: str

@dataclass(frozen=True)
class ConversationContext:
    resources: tuple[ResourceInput, ...]
    results: tuple[ResultInput, ...]


# execution(A)이 구현하고 conversations(A)·results(B)가 사용한다.
class RunRequester(Protocol):
    def request(self, session: Session, request: RunRequest) -> RunRef: ...
    # 키가 없으면 AI_CONNECTION_REQUIRED, 같은 대상의 활성 실행이 있으면 ACTIVE_RUN_EXISTS를 던진다.

@dataclass(frozen=True)
class RunRequest:
    project_id: UUID
    conversation_id: UUID
    task_id: UUID | None
    purpose: Literal["work", "summary"]
    target_id: UUID | None      # summary면 result_id
    requested_by: UUID          # 키 소유 계정. 분기된 하위 작업은 최초 요청자를 그대로 쓴다

@dataclass(frozen=True)
class RunRef:
    run_id: UUID
    status: str


# 실행 목적별로 구현해 실행기에 등록한다. work는 A, summary는 B가 구현한다.
class RunPurposeHandler(Protocol):
    purpose: str
    def build_request(self, session: Session, run: RunView, context: ConversationContext) -> LlmRequest: ...
    def complete(self, session: Session, run: RunView, output: Mapping[str, Any]) -> None: ...
    def fail(self, session: Session, run: RunView, error: RunError) -> None: ...


# sharing(B)이 구현하고 관계 보기(A9)가 사용한다.
class ResultUsageQuery(Protocol):
    def list_usages(self, session: Session, project_id: UUID) -> tuple[ResultUsage, ...]: ...
    # ResultUsage: source_conversation_id, target_conversation_id, result_id
```

실행기는 대기 중인 실행을 점유한 뒤 `RunPurposeHandler.build_request`로 모델 요청을 만들고, 트랜잭션 밖에서 `LlmGateway`를 호출한다. 결과는 새 트랜잭션에서 `complete` 또는 `fail`로 넘긴다. `RunView`, `RunError`, `LlmRequest`, `LlmGateway`는 execution 모듈의 공개 타입이다.

핸들러를 구현할 때 아래 동작을 전제로 한다.

- `ContextProvider.snapshot`은 점유 트랜잭션에서 한 번 호출되고, 그 결과가 `build_request`의 `context`로 그대로 넘어간다(5장).
- `fail`은 실행 상태를 failed로 바꾸는 트랜잭션 안에서 호출된다. 시작하지 않은 실행(`RUN_TIMED_OUT`)과 heartbeat가 끊긴 실행(`RUN_INTERRUPTED`)에도 호출된다. `fail`이 예외를 던지면 핸들러의 쓰기만 롤백되고 실행은 failed로 남는다.
- 취소할 때는 핸들러를 호출하지 않고 `run.updated`만 발행한다.
- 취소되었거나 복구 처리된 실행에 늦게 도착한 모델 결과는 버리며, 이때 `complete`는 호출되지 않는다.

### 6.1 모델 출력 스키마

모델 출력은 JSON 스키마로 받고 경계에서 검증한다. 검증에 실패하면 실행을 failed로 처리하고 재시도할 수 있게 한다.

| 목적 | 스키마 | 규칙 |
|---|---|---|
| `work`(부모 대화) | `{mode: "answer" \| "clarify" \| "branch", reply: string, tasks: [{title, goal, start_input}]}` | `branch`일 때만 `tasks` 1~4개. 방법 질문·목록 작성·사람 간 배정에는 `branch`를 쓰지 않는다(F-02) |
| `work`(하위 작업 대화) | `{mode: "answer" \| "clarify", reply: string}` | 재귀 분기를 막기 위해 `branch`가 없다 |
| `summary` | `{conclusion: string}` | 결론 본문 하나. 근거·미결·다음 행동 필드는 없다(D1) |

### 6.2 트랙 A 내부 인터페이스(참고)

트랙 A 안에서 병렬로 작업할 때 쓰는 인터페이스다. 트랙 B는 사용하지 않는다.

| 인터페이스 | 제공 | 사용 | 내용 |
|---|---|---|---|
| `CredentialProvider.get_api_key(account_id)` | access | execution | 실행 직전에만 키를 복호화해 돌려준다. 로그·이벤트에 남기지 않는다 |
| `ConversationWriter.append_message(...)`, `create_child(...)` | conversations | execution | AI 답변 저장, 분기 시 자식 대화 생성 |
| `AiConnectionQuery.is_connected(session, account_id)` | access | execution | 실행을 등록하거나 재시도할 때 키 연결 여부만 확인한다. execution은 `ai_connection` 테이블을 직접 읽지 않는다 |

## 7. 프론트엔드 연결 규칙

| 항목 | 규칙 |
|---|---|
| API 호출 | `src/lib/api`의 클라이언트와 `toResult`를 쓴다. 생성 타입은 `contracts/openapi.json`에서 만든 `src/api/schema.d.ts` 하나다 |
| 오류 표시 | 업무 오류는 `error.message`를 그대로 보여 주고, 동작 분기는 `error.code`로 한다. 시스템 오류·네트워크 오류는 공통 문구를 쓴다 |
| 모달 ID | `task:<taskId>`, `result:<resultRevisionId>`, `resources:<conversationId>`, `ai-connection` |
| 작업 모달 | A의 `TaskModal`이 틀과 대화 탭을 그리고, 결과 탭과 헤더 액션은 아래 props로 받는다. 조립은 `app/pages/WorkspacePage`에서 하며 기능 폴더끼리 서로 import하지 않는다 |
| 결론 보기 | B의 결론 보기 컴포넌트를 작업 모달 결과 탭과 받은 결론 모달(`result:<id>`)에서 함께 쓴다 |
| AI 연결 확인 | A의 `useAiConnection().ensure(): Promise<boolean>`. 키가 없으면 연결 모달을 열고 연결 결과를 돌려준다. 입력창(A)과 결과 정리 액션(B)이 AI 요청 직전에 호출한다 |
| 실시간 | `src/lib/realtime`과 `src/lib/events.ts`를 쓰고, 연결이 열릴 때마다 각 기능이 자기 상태를 다시 조회한다 |

```ts
// A: src/features/task-modal
export type TaskModalProps = {
  readonly taskId: string;
  readonly onClose: () => void;
  /** 헤더의 기능 액션. B가 '결과 정리'를 넣는다. 닫기 버튼은 TaskModal이 그린다. */
  readonly renderHeaderActions: (task: Task) => ReactNode;
  /** 결과 탭 내용. B의 결론 보기·편집·보내기·새 대화 화면. */
  readonly renderResultTab: (task: Task, nav: { readonly closeModal: () => void }) => ReactNode;
};
```

## 8. 확정한 결정

| ID | 내용 |
|---|---|
| D1 | 결과 정리는 결론 본문 하나. 원문 범위·자료 버전은 `source` 메타데이터로 저장 |
| D2 | 보내기를 완료하면 대상 대화의 AI 입력에 결론 버전이 바로 연결된다. 열기·닫기는 입력을 바꾸지 않는다 |
| D4 | 결과물 목록은 조회 전용. 새 대화는 결론 보기에서 결론 하나로 만든다 |
| D8 | 같은 결과의 새 버전을 다시 보내면 대상 대화의 입력을 새 버전으로 교체한다 |
| D9 | 첨부 자료는 `.md`·`.txt` UTF-8 텍스트만 받고, 원본과 추출 내용을 버전 행에 저장한다 |
| D10 | 프로젝트 관계 보기(WF-13)를 MVP에 포함한다 |
| C1 | 성공 응답은 감싸지 않고, 목록은 `{items}`, 변경 응답은 항상 JSON 객체 |
| C2 | JSON 필드는 `snake_case` |
| C3 | 실행 입력 스냅샷은 실행기가 실행을 점유하는 시점에 만든다(v1.3에서 등록 시점을 변경) |
| C4 | SSE는 지난 이벤트를 다시 보내지 않고, 클라이언트가 연결마다 상태를 다시 조회한다 |
| C5 | 결과 초안은 생성된 내용만 서버에 저장하고, 편집 중 내용은 저장 버튼을 누를 때 기준 버전과 함께 보낸다 |
| C6 | AI 실행 요청이 거절되면(키 없음, 활성 실행 있음) 메시지를 저장하지 않고 클라이언트가 입력 초안을 유지한다 |
| C7 | 작업 중단·재시도는 그 작업을 요청한 계정만 할 수 있다 |
| C8 | heartbeat가 끊긴 실행은 자동으로 다시 실행하지 않고 재시도할 수 있는 failed로 둔다. 사용자 동의 없이 요청자의 키로 비용이 다시 나가지 않게 하기 위해서다 |

## 변경 이력

| 날짜 | 버전 | 내용 |
|---|---|---|
| 2026-11-09 | v1 | 최초 확정. P0-A1·P0-B1에서 정해진 항목을 반영 |
| 2026-11-09 | v1.2 | P0-A3 구현에 맞춰 보완: 실제 이름은 `contracts/openapi.json` 기준, 빈 본문 변경 요청, `NOT_IMPLEMENTED`, 빈 보낼 대상 목록의 오류 코드 |
| 2026-11-09 | v1.1 | `task`·`run`의 `error_message`를 `error_params`(JSONB)로 바꾸고 `result_draft`에도 추가. 사용자에게 보여 줄 문장을 DB에 저장하지 않는 규칙 추가(로드맵 9.3-1) |
| 2026-11-09 | v1.3 | A4 실행기 구현에 맞춰 보완: 실행 실패 코드(1.3), 입력 스냅샷 기록 시점을 점유 시점으로 변경(C3), pending 상태의 `heartbeat_at` 의미, 핸들러 호출 조건(6장), `AiConnectionQuery`(6.2), 자동 재실행 금지(C8) |
