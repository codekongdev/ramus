"""B3 pure part: pinned revisions and received conclusions -> ConversationContext."""

from uuid import UUID, uuid4

import pytest

from ramus_api.modules.execution.domain.models import ConversationContext
from ramus_api.modules.resources.application.context import (
    PinnedContextProvider,
    PinnedRevision,
    ReceivedConclusion,
    build_context,
    resource_inputs,
    result_inputs,
)
from ramus_api.modules.resources.domain.models import ResourceKind


def pin(
    name: str, kind: ResourceKind = ResourceKind.SKILL, resource_id: UUID | None = None
) -> PinnedRevision:
    instructions = f"{name} 지침" if kind is ResourceKind.SKILL else None
    content = None if kind is ResourceKind.SKILL else f"{name} 내용"
    return PinnedRevision(resource_id or uuid4(), uuid4(), kind, name, instructions, content)


def conclusion(title: str, version: int = 1) -> ReceivedConclusion:
    return ReceivedConclusion(uuid4(), uuid4(), version, title, f"{title} 결론 v{version}")


def test_resources_keep_the_pinned_revision_and_its_content() -> None:
    skill, text = pin("벤치마킹", ResourceKind.SKILL), pin("반품 정책", ResourceKind.TEXT)
    by_name = {item.name: item for item in resource_inputs([skill, text])}
    assert by_name["벤치마킹"].revision_id == skill.revision_id
    assert (by_name["벤치마킹"].kind, by_name["벤치마킹"].instructions) == ("skill", "벤치마킹 지침")
    assert (by_name["반품 정책"].kind, by_name["반품 정책"].content) == ("text", "반품 정책 내용")


def test_order_is_deterministic_by_name_then_id() -> None:
    a, b, c = pin("b"), pin("A"), pin("c")
    assert [r.name for r in resource_inputs([a, b, c])] == ["A", "b", "c"]
    assert [r.name for r in resource_inputs([c, a, b])] == ["A", "b", "c"]
    same_name = sorted([pin("같음"), pin("같음")], key=lambda p: str(p.resource_id))
    assert [r.resource_id for r in resource_inputs(reversed(same_name))] == [p.resource_id for p in same_name]


def test_results_use_the_received_snapshot() -> None:
    received = conclusion("경쟁사 분석", version=2)
    (item,) = result_inputs([received])
    assert (item.result_revision_id, item.version, item.conclusion) == (
        received.result_revision_id,
        2,
        "경쟁사 분석 결론 v2",
    )


def test_build_context_combines_both_and_handles_empty() -> None:
    context = build_context([pin("스킬")], [conclusion("결론")])
    assert (len(context.resources), len(context.results)) == (1, 1)
    assert build_context([], []) == ConversationContext()


def test_two_pins_of_one_resource_are_rejected_by_the_context() -> None:
    resource_id = uuid4()
    with pytest.raises(ValueError, match="one revision per resource"):
        build_context([pin("v1", resource_id=resource_id), pin("v2", resource_id=resource_id)], [])


class FakeSources:
    def __init__(self) -> None:
        self.pins: dict[UUID, list[PinnedRevision]] = {}
        self.inputs: dict[UUID, list[ReceivedConclusion]] = {}

    def pinned(self, session: object, conversation_id: UUID) -> list[PinnedRevision]:
        return self.pins.get(conversation_id, [])

    def copy_pins(self, session: object, source: UUID, target: UUID) -> None:
        self.pins[target] = list(self.pins.get(source, []))

    def received(self, session: object, conversation_id: UUID) -> list[ReceivedConclusion]:
        return self.inputs.get(conversation_id, [])


def test_provider_copies_resources_but_not_received_conclusions() -> None:
    sources = FakeSources()
    provider = PinnedContextProvider(resources=sources, conclusions=sources)
    parent, child = uuid4(), uuid4()
    sources.pins[parent] = [pin("스킬")]
    sources.inputs[parent] = [conclusion("부모가 받은 결론")]
    provider.copy_resources(None, parent, child)
    context = provider.snapshot(None, child)
    assert [r.name for r in context.resources] == ["스킬"]
    assert context.results == ()


def test_provider_rejects_copying_onto_itself() -> None:
    sources = FakeSources()
    provider = PinnedContextProvider(resources=sources, conclusions=sources)
    same = uuid4()
    with pytest.raises(ValueError):
        provider.copy_resources(None, same, same)
