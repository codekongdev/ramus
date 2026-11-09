"""Verify the current API milestone; real PostgreSQL HTTP checks are opt-in."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres", action="store_true", help="Check two HTTP sessions and DB persistence")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    uv = ["uv", "run", "--project", "apps/api"]

    def run(command: list[str]) -> None:
        print("Running:", " ".join(command), flush=True)
        subprocess.run(command, cwd=root, check=True)

    run([*uv, "ruff", "check", "apps/api", "scripts"])
    run(["pnpm", "typegen"])
    pure_files = sorted(str(path.relative_to(root)) for path in (root / "apps/api/tests").glob("*domain*.py"))
    if pure_files:
        run([*uv, "pytest", *pure_files, "-q"])
    run([*uv, "pytest", "apps/api/tests", *[f"--ignore={path}" for path in pure_files], "-q"])
    run(["pnpm", "--dir", "apps/web", "exec", "tsc", "--noEmit", "--skipLibCheck", "--lib", "ES2022,DOM", "src/api/schema.d.ts"])
    if args.postgres:
        run([*uv, "python", "scripts/check_foundation.py"])


if __name__ == "__main__":
    main()
