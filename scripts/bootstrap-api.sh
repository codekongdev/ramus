#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  cp .env.example .env
fi
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
docker compose up -d --wait db
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
uv run --project apps/api python -m ramus_api.seed
pnpm typegen
