"""JSON boundary DTOs for model outputs (contracts.md §6.1)."""

import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ramus_api.modules.execution.domain.models import LlmFailure, LlmRequest, RunPurpose

Text = Annotated[str, Field(min_length=1, max_length=20_000)]
Title = Annotated[str, Field(min_length=1, max_length=100)]


class OutputDto(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class BranchTaskOutput(OutputDto):
    title: Title
    goal: Text
    start_input: Text


class ParentWorkOutput(OutputDto):
    mode: Literal["answer", "clarify", "branch"]
    reply: Text
    tasks: Annotated[list[BranchTaskOutput], Field(max_length=4)]

    @model_validator(mode="after")
    def validate_tasks(self) -> "ParentWorkOutput":
        if (self.mode == "branch") != bool(self.tasks):
            raise ValueError("Only branch output has one to four tasks")
        return self


class ChildWorkOutput(OutputDto):
    mode: Literal["answer", "clarify"]
    reply: Text


class SummaryOutput(OutputDto):
    conclusion: Text


def output_model(request: LlmRequest) -> type[OutputDto]:
    if request.purpose == RunPurpose.SUMMARY:
        return SummaryOutput
    return ChildWorkOutput if request.is_child else ParentWorkOutput


def output_json_schema(request: LlmRequest) -> dict[str, Any]:
    return output_model(request).model_json_schema()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("Non-JSON number")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def validate_output(request: LlmRequest, raw_json: str) -> Mapping[str, Any]:
    """Reject malformed/ambiguous JSON and hide untrusted payloads in gateway errors."""

    try:
        value = json.loads(raw_json, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        output = output_model(request).model_validate(value)
    except (ValueError, TypeError, ValidationError):
        raise LlmFailure("LLM_OUTPUT_INVALID") from None
    return _freeze(output.model_dump())
