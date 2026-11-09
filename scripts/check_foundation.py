"""Check a migrated PostgreSQL database through two real, independent HTTP sessions.

Only adds an isolated demo project. Never resets data or invokes a model.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import httpx
from ramus_api.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18110)
    parser.add_argument("--output", help="Defaults to a unique file under artifacts/")
    args = parser.parse_args()
    if not Settings().database_url.startswith("postgresql"):
        parser.error("This check requires PostgreSQL; it cannot provide SQLite acceptance evidence.")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    root = Path(__file__).resolve().parents[1]
    artifact_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = Path(args.output) if args.output else root / "artifacts" / f"foundation-postgres-{artifact_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = root / "artifacts" / f"foundation-server-{artifact_id}.log"
    log_path.parent.mkdir(exist_ok=True)
    base = f"http://127.0.0.1:{args.port}"
    process: subprocess.Popen | None = None

    with log_path.open("w") as log:
        def start() -> subprocess.Popen:
            server = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "ramus_api.main:app", "--host", "127.0.0.1", "--port", str(args.port)],
                cwd=root, env=os.environ.copy(), stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError(f"Server exited; inspect {log_path.name}")
                    try:
                        if httpx.get(base + "/api/health", timeout=1).status_code == 200:
                            return server
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                raise RuntimeError(f"Server startup timed out; inspect {log_path.name}")
            except BaseException:
                if server.poll() is None:
                    server.terminate()
                server.wait(timeout=15)
                raise

        try:
            process = start()
            with httpx.Client(base_url=base) as first, httpx.Client(base_url=base) as second:
                def login(client: httpx.Client, email: str) -> dict:
                    response = client.post("/api/auth/login", json={"email": email, "password": "ramus-demo-2026"})
                    response.raise_for_status()
                    assert "HttpOnly" in response.headers["set-cookie"]
                    return response.json()

                a = login(first, "minseo@ramus.local")
                b = login(second, "jihoon@ramus.local")
                assert a["id"] != b["id"]
                assert first.cookies.get("ramus_session") != second.cookies.get("ramus_session")
                response = first.post("/api/projects", json={"name": "공동 대화 시험 " + uuid.uuid4().hex[:8], "request_id": str(uuid.uuid4())})
                response.raise_for_status()
                project_id = response.json()["id"]
                state_response = first.get("/api/state", params={"project_id": project_id})
                state_response.raise_for_status()
                state = state_response.json()
                payload = {
                    "project_id": project_id,
                    "conversation_id": state["conversations"][0]["id"],
                    "content": "실제 PostgreSQL에서 공유하고 재시작 후 복원할 시험 메시지",
                    "request_id": str(uuid.uuid4()),
                }
                barrier = Barrier(2)

                def simultaneous_post() -> dict:
                    with httpx.Client(base_url=base, cookies=second.cookies) as retry_client:
                        barrier.wait(timeout=10)
                        response = retry_client.post("/api/messages", json=payload)
                        response.raise_for_status()
                        return response.json()

                with ThreadPoolExecutor(max_workers=2) as workers:
                    results = list(workers.map(lambda _: simultaneous_post(), range(2)))
                assert results[0] == results[1]
                saved = results[0]
                assert saved["message"]["author_id"] == b["id"]
                shared = first.get("/api/state", params={"project_id": project_id})
                shared.raise_for_status()
                assert shared.json()["messages"] == [saved["message"]]
                assert saved["message"]["sequence"] == 1
                replay = second.post("/api/messages", json=payload)
                replay.raise_for_status()
                assert replay.json() == saved
                conflict = second.post("/api/messages", json={**payload, "content": "동일 ID의 다른 입력"})
                assert conflict.status_code == 409
                process.terminate()
                process.wait(timeout=15)
                process = start()
                restored = first.get("/api/state", params={"project_id": project_id})
                restored.raise_for_status()
                matches = [message for message in restored.json()["messages"] if message["id"] == saved["message"]["id"]]
                assert len(matches) == 1 and matches[0] == saved["message"]
                report = {
                    "unit": "U08", "milestone": "step1", "database": "PostgreSQL 17", "transport": "actual HTTP",
                    "distinct_authenticated_users": True, "server_author_verified": True,
                    "shared_message_verified": True, "replayed_request_no_duplicate": True,
                    "concurrent_same_request_commits_once": True,
                    "same_id_different_input_status": 409, "server_restart_persists_data_and_sessions": True,
                    "paid_model_calls": 0,
                    "acceptance_scope": {"A01": "message portion only", "A11": "message storage, restart and replay only"},
                    "not_run": ["browser UI", "live AI", "remaining P0 acceptance"],
                }
                with output.open("x") as target:
                    target.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
                print(f"PostgreSQL two-session checks passed. Evidence: {output.relative_to(root) if output.is_relative_to(root) else output}")
        finally:
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=15)


if __name__ == "__main__":
    main()
