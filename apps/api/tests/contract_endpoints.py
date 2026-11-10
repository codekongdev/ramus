"""The endpoint table of docs/contracts.md section 3, as data shared by the contract tests.

Path parameter names are normalised to ``{}`` because the contract uses ``{id}`` and the API uses
descriptive names such as ``{conversation_id}``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEALTH_ENDPOINT = ("get", "/api/health")
_PARAMETER = re.compile(r"\{[^}]+\}")


def normalise_path(path: str) -> str:
    return _PARAMETER.sub("{}", path)


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str
    module: str
    operation_id: str
    status: int = 200

    @property
    def key(self) -> tuple[str, str]:
        return (self.method, normalise_path(self.path))

    @property
    def is_change(self) -> bool:
        return self.method in {"post", "put", "delete"}


CONTRACT_ENDPOINTS: tuple[Endpoint, ...] = (
    # 3.1 track A
    Endpoint("post", "/api/auth/register", "access", "registerAccount"),
    Endpoint("post", "/api/auth/login", "access", "loginWithPassword"),
    Endpoint("post", "/api/auth/email-code", "access", "requestEmailCode", 202),
    Endpoint("post", "/api/auth/verify", "access", "verifyEmailCode"),
    Endpoint("post", "/api/auth/logout", "access", "logout"),
    Endpoint("get", "/api/me", "access", "getMe"),
    Endpoint("get", "/api/me/password", "access", "getPasswordStatus"),
    Endpoint("put", "/api/me/password", "access", "setInitialPassword"),
    Endpoint("get", "/api/me/ai-connection", "access", "getAiConnection"),
    Endpoint("put", "/api/me/ai-connection", "access", "connectAi"),
    Endpoint("delete", "/api/me/ai-connection", "access", "disconnectAi"),
    Endpoint("get", "/api/projects", "projects", "listProjects"),
    Endpoint("post", "/api/projects", "projects", "createProject"),
    Endpoint("get", "/api/projects/{project_id}/participants", "projects", "listProjectParticipants"),
    Endpoint("get", "/api/projects/search", "projects", "searchProjects"),
    Endpoint("get", "/api/projects/{project_id}/conversations", "conversations", "listConversations"),
    Endpoint("post", "/api/projects/{project_id}/conversations", "conversations", "createConversation"),
    Endpoint(
        "get", "/api/projects/{project_id}/conversations/search", "conversations", "searchConversations"
    ),
    Endpoint("get", "/api/conversations/{conversation_id}", "conversations", "getConversation"),
    Endpoint("get", "/api/conversations/{conversation_id}/messages", "conversations", "listMessages"),
    Endpoint("post", "/api/conversations/{conversation_id}/messages", "conversations", "postMessage"),
    Endpoint("get", "/api/conversations/{conversation_id}/tasks", "execution", "listConversationTasks"),
    Endpoint("get", "/api/tasks/{task_id}", "execution", "getTask"),
    Endpoint("post", "/api/tasks/{task_id}/cancel", "execution", "cancelTask"),
    Endpoint("post", "/api/tasks/{task_id}/retry", "execution", "retryTask"),
    Endpoint("get", "/api/projects/{project_id}/events", "realtime", "streamProjectEvents"),
    Endpoint("get", "/api/projects/{project_id}/graph", "projects", "getProjectGraph"),
    # 3.2 track B
    Endpoint("get", "/api/projects/{project_id}/resources", "resources", "listResources"),
    Endpoint("post", "/api/projects/{project_id}/resources", "resources", "createResource"),
    Endpoint("get", "/api/resources/{resource_id}", "resources", "getResource"),
    Endpoint("post", "/api/resources/{resource_id}/revisions", "resources", "createResourceRevision"),
    Endpoint("get", "/api/conversations/{conversation_id}/resources", "resources", "listAppliedResources"),
    Endpoint("put", "/api/conversations/{conversation_id}/resources", "resources", "replaceAppliedResources"),
    Endpoint("post", "/api/tasks/{task_id}/summaries", "results", "createTaskSummary"),
    Endpoint("get", "/api/results/{result_id}", "results", "getResult"),
    Endpoint("get", "/api/result-revisions/{result_revision_id}", "results", "getResultRevision"),
    Endpoint("post", "/api/results/{result_id}/revisions", "results", "saveResultRevision"),
    Endpoint("get", "/api/projects/{project_id}/results", "results", "listProjectResults"),
    Endpoint("post", "/api/result-revisions/{result_revision_id}/shares", "sharing", "shareResultRevision"),
    Endpoint("get", "/api/conversations/{conversation_id}/inputs", "sharing", "listConversationInputs"),
    Endpoint("get", "/api/conversations/{conversation_id}/inputs/{input_id}", "sharing", "getConversationInput"),
    Endpoint(
        "post",
        "/api/projects/{project_id}/conversations/from-result",
        "sharing",
        "createConversationFromResult",
    ),
)
