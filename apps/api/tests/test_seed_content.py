"""The sample remains fictional, comparable, attributable and open for real collaboration."""

from uuid import UUID

import pytest

from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.domain.rules import content_hash, normalize_content
from ramus_api.modules.seed.domain.content import (
    AUTHORS,
    DESIGN_MESSAGES,
    DESIGN_TITLE,
    RESEARCH,
    RESOURCES,
    sample_id,
)


def test_sample_identity_matches_the_existing_fixed_project() -> None:
    assert sample_id("project") == UUID("52ca4f3a-7913-510c-9e52-064b3f1db1a4")
    assert sample_id("project").version == 5
    assert sample_id("mall-a") != sample_id("mall-b")


def test_every_example_message_has_a_known_explicit_example_author() -> None:
    authors = {author.key: author.label for author in AUTHORS}
    assert len(authors) == len(AUTHORS)
    assert all(label.startswith("예시·") for label in authors.values())
    messages = (*DESIGN_MESSAGES, *(message for item in RESEARCH for message in item.messages))
    assert all(message.author_key in authors for message in messages)
    assert all(item.author_key in authors for item in RESEARCH)
    assert all(0 < len(message.body) <= 20_000 for message in messages)


def test_sample_entities_use_distinct_keys() -> None:
    keys = [item.key for item in (*AUTHORS, *RESOURCES, *RESEARCH)]
    assert len(set(keys)) == len(keys)
    assert len({sample_id(key) for key in keys}) == len(keys)


@pytest.mark.parametrize("resource", RESOURCES, ids=lambda resource: resource.key)
def test_resource_content_is_accepted_by_the_real_resource_rules(resource) -> None:
    kind = ResourceKind(resource.kind)
    content = normalize_content(
        kind,
        name=resource.name,
        description=resource.description,
        instructions=resource.body if kind is ResourceKind.SKILL else None,
        content=resource.body if kind is not ResourceKind.SKILL else None,
        file_name=None,
    )
    assert len(content_hash(content)) == 64
    assert "가상" in resource.body


def test_skill_and_research_use_the_same_comparison_dimensions() -> None:
    skill = next(item for item in RESOURCES if item.key == "benchmark-skill")
    checklist = next(item for item in RESOURCES if item.key == "research-checklist")
    for dimension in ("고객 흐름", "등급", "실적", "혜택", "예외"):
        assert dimension in skill.body
        assert dimension in checklist.body
        assert all(f"{dimension}:" in item.conclusion for item in RESEARCH)
    assert {item.key for item in RESEARCH} == {"mall-a", "mall-b", "mall-c"}
    assert all("가상 예시" in item.conclusion and "미확인" in item.conclusion for item in RESEARCH)
    assert all("반품" in item.conclusion for item in RESEARCH)


def test_design_starts_with_only_the_leaders_unfinished_assignment() -> None:
    assert DESIGN_TITLE == "멤버십 기능 설계"
    assert len(DESIGN_MESSAGES) == 1
    assert DESIGN_MESSAGES[0].author_key == "leader"
    assert "미확정" in DESIGN_MESSAGES[0].body
    assert "통합 기획은 아직 확정하지 않았습니다" in DESIGN_MESSAGES[0].body
