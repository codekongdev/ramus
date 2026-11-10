"""HTTP helpers shared by the login integration tests."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from ramus_api.modules.access.fakes.services import FakeMailer

EMAIL_CODE_PATH = "/api/auth/email-code"
VERIFY_PATH = "/api/auth/verify"
LOGOUT_PATH = "/api/auth/logout"
ME_PATH = "/api/me"
SESSION_COOKIE = "ramus_session"


def new_key(prefix: str = "key") -> dict[str, str]:
    return {"Idempotency-Key": f"{prefix}-{uuid4()}"}


def unique_email(label: str = "user") -> str:
    return f"{label}-{uuid4().hex[:12]}@example.test"


def request_code(client: TestClient, email: str, headers: dict[str, str] | None = None):
    return client.post(EMAIL_CODE_PATH, json={"email": email}, headers=headers or new_key("code"))


def verify(client: TestClient, email: str, code: str, headers: dict[str, str] | None = None):
    return client.post(VERIFY_PATH, json={"email": email, "code": code}, headers=headers or new_key("verify"))


def logout(client: TestClient, headers: dict[str, str] | None = None):
    return client.post(LOGOUT_PATH, json={}, headers=headers or new_key("logout"))


def latest_code(mailer: FakeMailer, email: str) -> str:
    codes = [delivery.code for delivery in mailer.deliveries if delivery.email == email]
    assert codes, f"no code was delivered to {email}"
    return codes[-1]


def wrong_code(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


TEST_PASSWORD = "synthetic-test-password-42"


def login(client: TestClient, mailer: FakeMailer, email: str):
    if client._transport.client[0] == "testclient":
        client._transport.client = (f"password-fixture-{uuid4().hex}", 50000)
    response = client.post("/api/auth/register", json={
        "email": email, "password": TEST_PASSWORD, "display_name": email.strip().split("@")[0][:100],
    }, headers=new_key("register"))
    if response.status_code == 409:
        response = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD}, headers=new_key("login"))
    assert response.status_code == 200, response.text
    return response


def legacy_login(client: TestClient, mailer: FakeMailer, email: str):
    response = request_code(client, email)
    assert response.status_code == 202, response.text
    verified = verify(client, email, latest_code(mailer, email.strip().lower()))
    assert verified.status_code == 200, verified.text
    return verified


def error_code(response) -> str:
    body = response.json()
    assert set(body["error"]) == {"code", "message", "details"}
    return body["error"]["code"]


def set_cookie_headers(response) -> list[str]:
    return response.headers.get_list("set-cookie")
