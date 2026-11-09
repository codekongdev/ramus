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
