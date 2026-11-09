from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from uuid import UUID

import pytest

from ramus_api.modules.access.application.ports import CredentialProvider, Mailer
from ramus_api.modules.access.fakes.services import FakeCredentialProvider, FakeMailer
from ramus_api.modules.conversations.application.ports import ConversationWriter
from ramus_api.modules.conversations.domain.models import AuthorKind, NewChildConversation, NewMessage
from ramus_api.modules.conversations.fakes.writer import FakeConversationWriter
from ramus_api.modules.execution.application.ports import RunPurposeHandler
from ramus_api.modules.execution.domain.models import (
    ConversationContext,
    LlmMessage,
    LlmRequest,
    RunError,
    RunInputSnapshot,
    RunPurpose,
    RunStatus,
    RunView,
)
from ramus_api.modules.execution.fakes.llm import FakeLLM
from ramus_api.modules.sharing.application.ports import ResultUsageQuery
from ramus_api.modules.sharing.domain.models import ResultUsage
from ramus_api.modules.sharing.fakes.usages import FakeResultUsageQuery
from ramus_api.shared.domain.errors import BusinessError

ACCOUNT, PROJECT, CONVERSATION, TASK, RUN = (UUID(int=n) for n in range(1, 6))


async def test_mail_and_credentials_are_injectable_without_external_calls() -> None:
    mailer: Mailer = FakeMailer()
    await mailer.send_code("tester@example.test", "123456")
    assert mailer.deliveries[0].code == "123456"
    assert "123456" not in repr(mailer.deliveries[0])
    provider: CredentialProvider = FakeCredentialProvider({ACCOUNT: "fixture-only-credential"})
    assert provider.get_api_key(ACCOUNT) == "fixture-only-credential"
    assert "fixture-only-credential" not in repr(provider)
    with pytest.raises(BusinessError) as caught:
        provider.get_api_key(UUID(int=99))
    assert caught.value.code == "AI_CONNECTION_REQUIRED"


def test_writer_and_usage_query_hide_other_modules_storage() -> None:
    writer: ConversationWriter[object] = FakeConversationWriter()
    message = NewMessage(CONVERSATION, AuthorKind.AI, "AI 응답", ACCOUNT, RUN)
    child = NewChildConversation(PROJECT, CONVERSATION, TASK, "자식 작업", ACCOUNT)
    message_id = writer.append_message(None, message)
    child_id = writer.create_child(None, child)
    assert writer.messages == ((message_id, message),)
    assert writer.children == ((child_id, child),)
    usage = ResultUsage(CONVERSATION, child_id, UUID(int=99))
    mutable_items = [usage]
    query: ResultUsageQuery[object] = FakeResultUsageQuery({PROJECT: mutable_items})
    mutable_items.clear()
    assert query.list_usages(None, PROJECT) == (usage,)
    assert query.list_usages(None, UUID(int=98)) == ()


async def test_purpose_handler_contract_can_consume_fake_gateway_success_and_failure() -> None:
    class SummaryHandler:
        purpose = "summary"

        def __init__(self):
            self.completed = []
            self.failed = []

        def build_request(self, session: object, run: RunView, context: ConversationContext) -> LlmRequest:
            return LlmRequest(
                run.purpose, (LlmMessage("user", "정리해주세요"),), run.credential_account_id, context
            )

        def complete(self, session: object, run: RunView, output: Mapping[str, Any]) -> None:
            self.completed.append((run.id, output))

        def fail(self, session: object, run: RunView, error: RunError) -> None:
            self.failed.append((run.id, error))

    handler: RunPurposeHandler[object] = SummaryHandler()
    run = RunView(
        RUN,
        PROJECT,
        CONVERSATION,
        TASK,
        RunPurpose.SUMMARY,
        UUID(int=99),
        RunStatus.RUNNING,
        ACCOUNT,
        ACCOUNT,
        RunInputSnapshot(1, 2),
    )
    request = handler.build_request(None, run, ConversationContext())
    output = await FakeLLM().complete(request)
    handler.complete(None, run, output)
    handler.fail(None, replace(run, status=RunStatus.FAILED), RunError("LLM_TIMEOUT", "다시 시도해 주세요."))
    assert handler.completed[0][0] == run.id
    assert set(handler.completed[0][1]) == {"conclusion"}
    assert handler.failed[0][1].retryable
