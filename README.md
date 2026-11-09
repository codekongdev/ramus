# Ramus

개발 컨벤션과 환경 설정.

- [CONVENTIONS.md](CONVENTIONS.md): 아키텍처와 공통 구현 규칙
- [AGENTS.md](AGENTS.md): 에이전트 작업 규칙
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
예시 대화·자료·결과 콘텐츠와 로그인 참여자 등록은 후속 작업에서 추가한다.

API는 `uv run --project apps/api python -m ramus_api`, 웹은 `pnpm --filter @ramus/web dev`로 띄운다.
웹 개발 서버는 `/api` 요청을 `RAMUS_API_PORT`로 넘긴다.

테스트(`uv run --project apps/api pytest`)는 `DATABASE_URL`의 개발용 DB를 쓰지 않는다.
같은 서버에 `ramus_test_<무작위>` 임시 DB를 매번 만들어 마이그레이션하고, 끝나면 지운다.
Postgres가 꺼져 있으면 통합 테스트는 실패한다. 단위 테스트만 돌릴 때는 `-m "not integration"`을 붙인다.
