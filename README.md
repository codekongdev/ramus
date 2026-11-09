# Ramus

개발 컨벤션과 환경 설정.

- [CONVENTIONS.md](CONVENTIONS.md): 아키텍처와 공통 구현 규칙
- [AGENTS.md](AGENTS.md): 에이전트 작업 규칙
- [A5 자동 분기 연결](docs/a5-auto-branch.md): work 실행기 조립, 입력 범위·버전 상속, 로컬 검증
- `apps/web/`: React · TypeScript · Vite · Vitest 설정
- `apps/api/`: Python · FastAPI · Ruff · pytest 설정
- `compose.yaml`: 로컬 PostgreSQL 설정
- `playwright.config.ts`: 브라우저 테스트 설정

## 개발 환경

Node.js, pnpm 11.3.0, Python 3.12+, uv를 사용한다.
로컬 PostgreSQL을 실행할 때는 Docker Compose가 필요하다.

의존성 설치:

```sh
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
```

환경변수는 `.env.example`을 참고해 로컬 `.env`에 설정한다.
실제 키와 로컬 데이터는 커밋하지 않는다.

개인 AI 키 연결에는 `RAMUS_SECRET_KEY`가 필요하다. `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`로 생성한 값을 로컬 `.env`에 설정한다. 서버는 이 값으로 계정별 키를 암호화한다. 값을 바꾸거나 잃으면 기존 키를 복호화할 수 없으므로 계정에서 다시 연결해야 한다. 연결 검증은 `OPENAI_MODEL`에 설정한 모델에 최대 16 출력 토큰의 짧은 요청을 보내므로 소액의 API 사용료가 발생할 수 있다. 테스트는 검증 어댑터를 주입하므로 실제 API를 호출하지 않는다.

## 워크트리별 설정

워크트리마다 루트 `.env`에서 DB 이름과 두 포트를 다르게 지정한다. Postgres 서버(`pnpm db:up`)는 함께 쓴다.

```sh
DATABASE_URL=postgresql+psycopg://ramus:ramus-local@127.0.0.1:55432/ramus_wt2
RAMUS_WEB_PORT=5183
RAMUS_API_PORT=8010
```

개발용 DB를 만들고 마이그레이션을 적용한다(저장소 루트에서 실행).

```sh
docker compose exec db createdb -U ramus ramus_wt2
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
```

전체 테이블·컬럼·제약의 기준은 [스키마 계약](docs/contracts.md#5-테이블-스키마)이다.
마이그레이션 후 공동 샘플 프로젝트를 준비한다.

```sh
uv run --project apps/api python -m ramus_api.modules.seed
```

이 명령은 고정 시드 키에서 UUIDv5를 만들고 `project_id`를 JSON으로 출력한다.
여러 번 또는 동시에 실행해도 프로젝트와 시드 표식은 하나만 생성하며, 기존 이름과 데이터를 유지한다.
예시 대화·자료·결과 콘텐츠는 후속 작업에서 추가한다.
로그인하면 공동 샘플 프로젝트에 편집 참여자로 자동 등록된다. 시드 명령을 실행하지 않았어도 첫 로그인 때 프로젝트가 만들어진다.

## 대화·메시지 백엔드 (A2)

참여자는 프로젝트의 대화 트리·제목 검색·상세를 조회하고 최상위 대화를 만들 수 있다.
메시지 작성자는 세션에서, 순서는 서버에서 결정한다. 메시지 목록은 `after_seq`와 `limit`으로
조회하며, 변경 요청은 `Idempotency-Key`로 중복 생성을 막는다.

`/api/projects/{project_id}/events`는 프로젝트 참여자에게 SSE 이벤트를 보낸다.
15초마다 연결 유지와 세션·참여 권한을 확인한다. 이벤트 이력은 재전송하지 않으므로
클라이언트는 연결이 열릴 때 상태를 다시 조회하고, 메시지는 마지막 `seq` 이후를 조회한다.
현재 브로커는 API 프로세스 하나에서 동작한다. 여러 프로세스로 실행하려면 공유 전송 어댑터가 필요하다.

`@AI`가 포함된 메시지는 실행 등록과 함께 저장한다. 요청자의 AI 연결이 없거나 같은 대화에
활성 실행이 있으면 메시지를 저장하지 않고 409를 반환한다. 현재 앱 연결은 pending 실행 등록까지이며,
실제 모델 호출은 AI 연결·입력 조립·목적별 핸들러와 워커를 연결한 뒤 동작한다.

## 서버 실행

API는 `uv run --project apps/api python -m ramus_api`, 웹은 `pnpm --filter @ramus/web dev`로 띄운다.
웹 개발 서버는 `/api` 요청을 `RAMUS_API_PORT`로 넘긴다.

개발 환경에서는 메일을 보내지 않는다. 로그인 인증 코드는 API 서버 터미널 로그에 `[DEV MAIL - not sent]` 줄로 출력된다.
HTTPS로 서비스하는 환경에서는 `RAMUS_COOKIE_SECURE=true`로 세션 쿠키에 `Secure`를 붙인다.
배포 환경에서는 `RAMUS_AUTH_SECRET`에 32자 이상의 고정 비밀값을 설정한다. 인증 코드와 로그인 receipt의 HMAC에 사용하며, 비워 두면 개발 서버를 다시 시작할 때마다 임시값이 바뀌어 발급 중인 코드와 재시도 receipt가 무효화된다.

테스트(`uv run --project apps/api pytest`)는 `DATABASE_URL`의 개발용 DB를 쓰지 않는다.
같은 서버에 `ramus_test_<무작위>` 임시 DB를 매번 만들어 마이그레이션하고, 끝나면 지운다.
Postgres가 꺼져 있으면 통합 테스트는 실패한다. 단위 테스트만 돌릴 때는 `-m "not integration"`을 붙인다.

로그인 브라우저 테스트는 `pnpm test:e2e`로 실행한다. 처음 실행할 때는 `pnpm exec playwright install chromium`으로 브라우저를 설치한다.
테스트가 임시 DB를 만들고 마이그레이션한 뒤 API·웹 서버를 빈 포트에서 실행하며, 종료 시 서버와 임시 DB를 정리한다.
개발 메일러가 출력한 코드를 fixture 내부에서만 읽고 실제 메일은 보내지 않는다. 재전송 테스트는 실제 60초 제한이 끝날 때까지 기다린다.

## 전체 검증

```sh
pnpm verify                     # 웹 타입·테스트, API lint·단위·통합, 계약(OpenAPI) 검사, 한글 문구 검사를 한 번에 실행
pnpm verify --only web,api:lint # 영역(web·api·contract·i18n·scripts) 또는 단계 ID만 실행
pnpm verify --list              # 단계 목록
```

실패한 단계가 있어도 나머지를 끝까지 실행하고 마지막에 단계별 PASS·FAIL·SKIP을 보여 준다.
`i18n:hangul`은 `apps/web/src/features`의 `.tsx`에 한글 문구가 있으면 실패한다. 화면 문구는 기능 폴더의 `messages.ts`에 둔다(로드맵 9.3).
uv가 없거나 Postgres가 꺼져 있으면 그 단계는 SKIP이다.
SKIP은 통과가 아니므로 종료 코드 1을 돌려준다. 실행하지 못한 것을 알고 넘어갈 때만 `--allow-skip`을 붙인다.
