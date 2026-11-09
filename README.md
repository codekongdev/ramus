# Ramus

팀 AI 워크스페이스 Ramus를 단계적으로 구현한다. 현재 반영 범위는 **서버 실행 기반·로그인·공동 대화 API**다.

두 데모 사용자가 독립된 서버 세션으로 같은 프로젝트의 메시지를 읽고 작성할 수 있다. 작성자·메시지 순서는 서버에서 정하며, 요청 ID로 재시도 중복을 막는다. PostgreSQL에 저장한 메시지와 세션은 서버 재시작 후에도 유지된다.

분기·AI 실행·자동 기억·문서 수정·웹 화면은 다음 반영 범위다. 현재 `@AI`도 일반 메시지 텍스트로 저장하며 모델을 호출하지 않는다. 전체 P0나 A01~A12를 완료한 상태로 표시하지 않는다.

- [CONVENTIONS.md](CONVENTIONS.md): 아키텍처와 공통 구현 규칙
- [AGENTS.md](AGENTS.md): 에이전트 작업 규칙
- `apps/web/`: React · TypeScript · Vite · Vitest 설정
- `apps/api/`: Python · FastAPI · Ruff · pytest 설정
- `contracts/openapi.json`: 실제 FastAPI에서 생성한 API 계약
- `apps/web/src/api/schema.d.ts`: 계약에서 생성한 프론트 타입
- `compose.yaml`: 로컬 PostgreSQL 설정
- `playwright.config.ts`: 브라우저 테스트 설정
- [반영 기록](docs/iterations.md) · [단위 검증](docs/verification/units.json)

## 개발 환경

Node.js 24+, pnpm 11.3.0, Python 3.12+, uv를 사용한다.
로컬 PostgreSQL을 실행할 때는 Docker Compose가 필요하다.

저장소 루트에서 최초 준비:

```sh
pnpm bootstrap:api
pnpm dev:api
```

`bootstrap:api`는 없는 경우에만 `.env.example`을 `.env`로 복사하고 의존성 설치 → 전용 DB 시작 → Alembic 이관 → 데모 seed → API 타입 생성을 실행한다. 기존 `.env`와 DB 자료는 유지한다. 서버 시작과 seed 명령은 스키마를 생성하거나 이관하지 않는다.

- API와 수동 시험 화면: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json
- PostgreSQL: `127.0.0.1:55433`, Compose 프로젝트 `ramus-setup-local`의 전용 볼륨
- 데모 계정: `minseo@ramus.local`, `jihoon@ramus.local` / 비밀번호 `ramus-demo-2026`

개발 원본 `ramus`의 DB(55432)와 분리한다. 두 API 서버는 기본 포트 8000이 같으므로 동시에 띄울 때는 하나의 포트를 변경한다. 데모 계정은 로컬 시험용이며 가입·초대는 이번 범위에 없다. 실제 키와 로컬 데이터는 커밋하지 않는다.

## API 흐름

1. `POST /api/auth/login`으로 로그인하면 HttpOnly 세션 쿠키를 받는다. `GET /api/auth/me`로 확인하고 `POST /api/auth/logout`으로 폐기한다.
2. `GET /api/projects`와 `GET /api/state?project_id=...`로 프로젝트·멤버·대화·메시지를 조회한다.
3. `POST /api/messages`에 `project_id`, `conversation_id`, `content`, `request_id`를 보낸다. 작성자는 쿠키의 사용자로 결정한다.
4. 같은 `request_id`와 입력을 재전송하면 저장한 결과를 돌려준다. 같은 ID에 다른 입력은 409, 프로젝트 접근 권한이 없으면 404다.

`POST /api/projects`는 기존 프로젝트를 지우지 않고 두 데모 사용자의 새 시험 사본을 만든다. 다른 브라우저 프로필이나 독립 HTTP 클라이언트로 로그인해야 두 사용자 세션을 시험할 수 있다.

## 검증

```sh
pnpm verify
pnpm verify --postgres
```

기본 검증은 Ruff → 실제 API 계약/타입 생성 → Domain Unit → 서버 Integration → 생성 타입의 TypeScript 검사 순서다. `--postgres`는 위 준비 명령으로 이관·seed한 DB에서 실제 HTTP 두 세션과 서버 재시작 후 영속성을 추가 확인한다. 기존 데이터를 초기화하지 않고 새 시험 프로젝트를 추가한다. 실행마다 새 근거를 `artifacts/`에 저장한다.

현재 단계의 웹 앱·브라우저 E2E·실제 AI 검증은 포함하지 않는다. 자세한 서버 명령은 [API README](apps/api/README.md), 실제 실행 결과는 [U08 근거](docs/verification/U08-step1.json)를 따른다.
