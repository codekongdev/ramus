from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from ramus_api.application.ports import UnitOfWork, WorkContext
from ramus_api.shared.domain import (
    BusinessError,
    new_id,
    now_iso,
    password_hash,
    password_matches,
    token_hash,
)

DEMO_PASSWORD = "ramus-demo-2026"
DEMO_USERS = (("minseo@ramus.local", "민서"), ("jihoon@ramus.local", "지훈"))
INITIAL_INSTRUCTIONS = "같은 프로젝트에서 팀의 논의를 함께 기록합니다."


def public_user(data: dict) -> dict:
    return {key: data[key] for key in ("id", "name", "email")}


class Workspace:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def ensure_demo(self) -> None:
        with self.uow.transaction() as work:
            for email, name in DEMO_USERS:
                if not work.access.credentials(email):
                    work.access.add_user(
                        {"id": new_id(), "email": email, "name": name, "password_hash": password_hash(DEMO_PASSWORD)}
                    )
            users = [work.access.credentials(email) for email, _ in DEMO_USERS]
            if not work.access.projects(users[0]["id"]):
                self._seed_project(work, "온보딩 개선", users)

    def login(self, email: str, password: str) -> tuple[dict, str]:
        with self.uow.transaction() as work:
            user = work.access.credentials(email)
            if not user or not password_matches(password, user["password_hash"]):
                raise BusinessError("INVALID_CREDENTIALS", "이메일 또는 비밀번호를 확인해 주세요.", 401)
            token = secrets.token_urlsafe(32)
            expires = (datetime.now(UTC) + timedelta(hours=12)).isoformat()
            work.access.add_session(token_hash(token), user["id"], expires)
            return public_user(user), token

    def authenticate(self, token: str | None) -> dict:
        if not token:
            raise BusinessError("UNAUTHENTICATED", "로그인이 필요합니다.", 401)
        with self.uow.transaction() as work:
            user = work.access.user_for_session(token_hash(token), now_iso())
            if not user:
                raise BusinessError("UNAUTHENTICATED", "로그인이 만료되었습니다. 다시 로그인해 주세요.", 401)
            return user

    def logout(self, token: str | None) -> None:
        if token:
            with self.uow.transaction() as work:
                work.access.delete_session(token_hash(token))

    def projects(self, user: dict) -> list[dict]:
        with self.uow.transaction() as work:
            return work.access.projects(user["id"])

    def create_project(self, user: dict, data: dict) -> dict:
        def authorize(_work: WorkContext) -> None:
            if user["email"] not in {email for email, _ in DEMO_USERS}:
                raise BusinessError("FORBIDDEN", "시연 멤버만 새 시연 사본을 만들 수 있습니다.", 403)

        def create(work: WorkContext) -> dict:
            users = [work.access.credentials(email) for email, _ in DEMO_USERS]
            if not all(users):
                raise BusinessError("DEMO_NOT_READY", "시연 계정 초기화를 먼저 실행해 주세요.", 409)
            return self._seed_project(work, data["name"].strip(), users)

        def authorize_response(work: WorkContext, project: dict) -> None:
            work.access.ensure_member(user["id"], project["id"])

        return self.uow.execute_once(
            user["id"], "create_project", data["request_id"], data, create, authorize, authorize_response
        )

    def state(self, user: dict, project_id: str | None) -> dict:
        with self.uow.transaction() as work:
            if not project_id:
                projects = work.access.projects(user["id"])
                if not projects:
                    raise BusinessError("NOT_FOUND", "참여 중인 프로젝트가 없습니다.", 404)
                project_id = projects[0]["id"]
            project = work.access.ensure_member(user["id"], project_id)
            return {
                "user": user,
                "project": project,
                "members": work.access.members(project_id),
                "conversations": work.conversations.conversations(project_id),
                "messages": work.conversations.messages(project_id),
            }

    def append_message(self, user: dict, data: dict) -> dict:
        def authorize(work: WorkContext) -> None:
            work.access.ensure_member(user["id"], data["project_id"])
            work.conversations.conversation(data["conversation_id"], data["project_id"])

        def append(work: WorkContext) -> dict:
            content = data["content"].strip()
            if not content:
                raise BusinessError("INVALID_INPUT", "메시지를 입력해 주세요.", 422)
            message = work.conversations.add_message(
                {
                    "id": new_id(),
                    "project_id": data["project_id"],
                    "conversation_id": data["conversation_id"],
                    "author_id": user["id"],
                    "author_name": user["name"],
                    "role": "user",
                    "content": content,
                    "sequence": work.access.allocate_sequence(data["project_id"]),
                    "created_at": now_iso(),
                }
            )
            return {"message": message}

        return self.uow.execute_once(user["id"], "append_message", data["request_id"], data, append, authorize)

    @staticmethod
    def _seed_project(work: WorkContext, name: str, users: list[dict]) -> dict:
        project_id = new_id()
        project = {"id": project_id, "name": name, "instructions": INITIAL_INSTRUCTIONS}
        work.access.create_project(
            {**project, "next_sequence": 0, "created_at": now_iso()},
            [{"id": new_id(), "project_id": project_id, "user_id": user["id"]} for user in users],
        )
        work.conversations.add_conversation(
            {
                "id": new_id(),
                "project_id": project_id,
                "title": "공동 논의",
                "instructions": INITIAL_INSTRUCTIONS,
                "created_at": now_iso(),
            }
        )
        return project
