# Ramus

Development conventions and environment setup.

- [CONVENTIONS.md](CONVENTIONS.md): Architecture and shared implementation rules
- [AGENTS.md](AGENTS.md): Agent workflow rules
- [A5 automatic branching integration](docs/a5-auto-branch.md): Work executor assembly, input scope and version inheritance, and local verification
- [A8 project switching and creation](docs/a8-projects.md): Project access, idempotent creation, navigation, and local verification
- [B1 shared skills and resources](docs/b1-resources-ui.md): Register, import, search, and apply pinned resource versions
- [B2 resource revision management](docs/b2-resource-revisions.md): Resource history, editing, conflicts, and explicit version application
- [B6 conclusion sharing](docs/b6-sharing.md): Send pinned conclusions to multiple conversations, receive and forward them, and explicitly replace input versions
- [B8 results library](docs/b8-results-library.md): Read-only project library of saved conclusions, sources, and latest approved versions
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
After applying migrations, prepare the shared sample projects and fictional content:

```sh
uv run --project apps/api python -m ramus_api.modules.seed
```

The command prints `project_id` as JSON and uses stable UUIDv5 identities with a separate content version marker.
On a fresh database, it creates two sample projects, four example authors, the unfinished “멤버십 기능 설계”
assignment and three A/B/C research conversations, ten messages, three resources at v1, three saved conclusions,
and three shares with pinned conclusion inputs. The three ready tasks and four succeeded runs are fictional historical
examples; preparation does not call a model or add pending/running work.
Repeated or concurrent preparation preserves existing content, user work, and project names.
Sign-in adds editing memberships to the sample projects without preparing or resetting their content.
Before preparation, sign-in creates only the default project, with no sample content or follow-up project.

Reset is an operator-only CLI operation, authorized by server and database access. Stop the API and workers and confirm
that existing work has been backed up or may be removed before running it:

```sh
uv run --project apps/api python -m ramus_api.modules.seed --reset \
  --confirm-project-id 52ca4f3a-7913-510c-9e52-064b3f1db1a4 --work-preserved
```

Reset removes user-created content in both fixed sample projects and restores the examples. It preserves accounts,
sessions, AI connections, memberships, project names, and unrelated projects. Active runs, conflicting database use,
or another project's references to the sample conclusions prevent reset and roll back changes.
There is no HTTP endpoint or product button for reset. See [B9 sample preparation](docs/b9-seed-content.md) for scope
and local verification. B6 conclusion sharing is connected to the product UI and pinned AI inputs.
Follow-up conversation creation remains dependent on B7 integration for the full product E2E.
The left **결과물** menu lists the current project's saved conclusions with their source conversation,
latest approved version, and save time. Unsaved drafts are excluded.

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

## Project switching and creation (A8)

Use the project name in the top bar to search your projects, switch workspaces, or create a new project.
Creation selects the new workspace and grants its creator editing access. Other accounts continue to join
the shared sample on sign-in; they do not automatically join newly created projects.
Project and conversation URLs survive reloads and browser history navigation. A creation retry after a lost
response reuses its idempotency key, so it selects the already created project without creating a duplicate.

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
