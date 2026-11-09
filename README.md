# Ramus

Development conventions and environment setup.

- [CONVENTIONS.md](CONVENTIONS.md): Architecture and shared implementation rules
- [AGENTS.md](AGENTS.md): Agent workflow rules
- [A5 automatic branching integration](docs/a5-auto-branch.md): Work executor assembly, input scope and version inheritance, and local verification
- `apps/web/`: React · TypeScript · Vite · Vitest setup
- `apps/api/`: Python · FastAPI · Ruff · pytest setup
- `compose.yaml`: Local PostgreSQL configuration
- `playwright.config.ts`: Browser test configuration

## Development environment

Use Node.js, pnpm 11.3.0, Python 3.12+, and uv.
Docker Compose is required to run PostgreSQL locally.

Install dependencies:

```sh
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
```

Configure environment variables in a local `.env` file using `.env.example` as a reference.
Do not commit real keys or local data.

Connecting a personal AI key requires `RAMUS_SECRET_KEY`. Generate a value with `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'` and set it in your local `.env` file. The server uses this value to encrypt each account's key. If you change or lose it, existing keys cannot be decrypted and must be reconnected through the account. Connection validation sends a short request with at most 16 output tokens to the model configured in `OPENAI_MODEL`, which may incur a small API charge. Tests inject a validation adapter and do not call the real API.

## Per-worktree configuration

Set a unique database name and both ports in each worktree's root `.env` file. Worktrees share the PostgreSQL server (`pnpm db:up`).

```sh
DATABASE_URL=postgresql+psycopg://ramus:ramus-local@127.0.0.1:55432/ramus_wt2
RAMUS_WEB_PORT=5183
RAMUS_API_PORT=8010
```

Create the development database and apply migrations from the repository root:

```sh
docker compose exec db createdb -U ramus ramus_wt2
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
```

The [schema contract](docs/contracts.md#5-테이블-스키마) is the source of truth for all tables, columns, and constraints.
After applying migrations, initialize the shared sample project:

```sh
uv run --project apps/api python -m ramus_api.modules.seed
```

This command derives a UUIDv5 from a fixed seed key and prints `project_id` as JSON.
Repeated or concurrent runs create only one project and seed marker, preserving existing names and data.
Sample conversations, resources, and result content will be added in later work.
Users are automatically added to the shared sample project as editing participants when they sign in. The project is created on the first sign-in even if the seed command has not been run.

## Conversation and message backend (A2)

Participants can view a project's conversation tree and conversation details, search by title, and create top-level conversations.
Message authors are determined from the session, and message order is assigned by the server. Use `after_seq` and `limit`
to retrieve messages. Mutation requests use `Idempotency-Key` to prevent duplicate creation.

`/api/projects/{project_id}/events` sends SSE events to project participants.
Every 15 seconds, the stream sends a keepalive and checks the session and project membership. Event history is not replayed,
so clients must refetch state when a connection opens and retrieve messages after the last `seq`.
The current broker runs within a single API process. Running multiple processes requires a shared transport adapter.

Messages containing `@AI` are saved together with a registered run. If the requester has no AI connection or the same conversation
already has an active run, the API returns 409 without saving the message. The app currently supports registering pending runs;
actual model calls require wiring together the AI connection, input assembly, purpose-specific handlers, and worker.

## Running the servers

Start the API with `uv run --project apps/api python -m ramus_api` and the web app with `pnpm --filter @ramus/web dev`.
The web development server forwards `/api` requests to `RAMUS_API_PORT`.

No email is sent in development. Sign-in verification codes appear in the API server's terminal logs on a `[DEV MAIL - not sent]` line.
When serving over HTTPS, set `RAMUS_COOKIE_SECURE=true` to add the `Secure` attribute to session cookies.
In deployed environments, set `RAMUS_AUTH_SECRET` to a stable secret of at least 32 characters. It is used for the HMAC of verification codes and sign-in receipts. If left empty, a new temporary value is generated each time the development server restarts, invalidating outstanding codes and retry receipts.

Tests (`uv run --project apps/api pytest`) do not use the development database specified by `DATABASE_URL`.
Each run creates and migrates a temporary `ramus_test_<random>` database on the same server, then removes it when finished.
Integration tests fail if PostgreSQL is not running. Add `-m "not integration"` to run unit tests only.

Run the sign-in browser tests with `pnpm test:e2e`. Before the first run, install the browser with `pnpm exec playwright install chromium`.
The tests create and migrate a temporary database, start the API and web servers on available ports, and clean up the servers and temporary database when finished.
Codes printed by the development mailer are read only within the fixture; no real email is sent. Resend tests wait for the actual 60-second rate limit to expire.

## Full verification

```sh
pnpm verify                     # Run web type checks and tests, API lint and unit/integration tests, OpenAPI contract checks, and Korean text checks
pnpm verify --only web,api:lint # Run selected areas (web, api, contract, i18n, scripts) or step IDs
pnpm verify --list              # List verification steps
```

Verification continues through all steps even if some fail, then reports PASS, FAIL, or SKIP for each step.
`i18n:hangul` fails if Korean text appears in `.tsx` files under `apps/web/src/features`. Keep UI text in each feature folder's `messages.ts` (roadmap 9.3).
Steps that require uv or PostgreSQL are marked SKIP if uv is unavailable or PostgreSQL is not running.
SKIP is not a pass, so verification exits with code 1. Add `--allow-skip` only when you intentionally accept that some checks could not run.
