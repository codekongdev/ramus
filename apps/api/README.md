# Ramus API

현재 범위는 서버 세션 로그인·프로젝트 소속·공동 대화다. HTTP Router와 DTO, UseCase/Port, 저장 어댑터를 분리한다. `access`, `conversations` 모듈은 공개 Repository 인터페이스를 통해 접근한다.

저장소 루트에서 실행한다.

```sh
uv sync --project apps/api --locked
pnpm db:up
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
uv run --project apps/api python -m ramus_api.seed
pnpm dev:api
```

서버 실행(`pnpm dev:api`)을 제외한 준비 명령은 [루트 최초 준비](../../README.md)의 `pnpm bootstrap:api`에도 포함되어 있다. 루트 `.env`의 `DATABASE_URL`을 읽으며 기본값은 전용 PostgreSQL `127.0.0.1:55433`이다. Alembic이 스키마를 관리하고, 앱 시작은 DB 이관·자료 초기화를 하지 않는다. seed는 없는 데모 사용자와 프로젝트만 추가한다.

`create_app(Settings(...))`로 DB 설정을 주입할 수 있다. 테스트는 별도 SQLite 파일을 만들고, 실제 PostgreSQL HTTP 검증은 `pnpm verify --postgres`로 구분한다. 이 검증 전에 DB 이관과 seed가 필요하다.

데모 사용자는 `minseo@ramus.local`, `jihoon@ramus.local`이며 비밀번호는 `ramus-demo-2026`이다. 서버 세션은 12시간 동안 유효하며 DB에는 토큰의 해시만 저장한다. HttpOnly 쿠키를 사용하고 로그아웃하면 서버에서도 세션을 폐기한다. HTTPS 환경의 Secure 쿠키는 `RAMUS_COOKIE_SECURE=true`로 설정한다.

메시지 요청은 프로젝트 소속과 대화 범위를 확인한 뒤, 서버가 작성자·순서를 정한다. 요청 영수증·순서 할당·메시지는 같은 트랜잭션으로 저장한다. 이미 처리한 요청도 현재 권한을 확인하며, 같은 요청 ID의 다른 입력은 409로 거부한다. 준비된 AI 응답이나 기억·문서·분기 기능은 포함하지 않는다.

API 계약은 `pnpm typegen`으로 실제 앱에서 추출한다. 생성된 JSON과 TypeScript 타입을 직접 수정하지 않는다.
