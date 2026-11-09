"""Bounded map/reduce over the model port; the executor still owns timeout and cancellation."""

import asyncio
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from ramus_api.modules.execution.application.output_schema import SummaryOutput
from ramus_api.modules.execution.application.ports import LlmGateway
from ramus_api.modules.execution.domain.models import LlmFailure, LlmRequest, RunPurpose
from ramus_api.modules.results.domain.summary_chunks import (
    PartialConclusion,
    SummaryLimitExceeded,
    SummaryLimits,
    extraction_requests,
    input_size,
    reduction_batches,
    synthesis_request,
)


class LongSummaryGateway:
    def __init__(self, gateway: LlmGateway, limits: SummaryLimits = SummaryLimits()):
        self._gateway, self._limits = gateway, limits

    async def complete(self, request: LlmRequest) -> Mapping[str, Any]:
        if request.purpose != RunPurpose.SUMMARY or input_size(request) <= self._limits.input_bytes:
            return await self._gateway.complete(request)
        try:
            requests = extraction_requests(request, self._limits)
            calls = len(requests)
            conclusions = await self._extract(requests)
            parts = tuple(PartialConclusion(index, index, text) for index, text in enumerate(conclusions))
            for round_index in range(self._limits.rounds + 1):
                final = synthesis_request(request, parts)
                if input_size(final) <= self._limits.input_bytes:
                    if calls + 1 > self._limits.calls:
                        raise SummaryLimitExceeded()
                    return MappingProxyType({"conclusion": await self._call(final)})
                if round_index == self._limits.rounds:
                    raise SummaryLimitExceeded()
                batches = reduction_batches(request, parts, self._limits)
                calls += sum(len(batch) > 1 for batch in batches)
                if calls + 1 > self._limits.calls:
                    raise SummaryLimitExceeded()
                reduced = []
                for batch in batches:
                    if len(batch) == 1:
                        reduced.append(batch[0])
                    else:
                        text = await self._call(synthesis_request(request, batch, intermediate=True), intermediate=True)
                        reduced.append(PartialConclusion(batch[0].first_part, batch[-1].last_part, text))
                parts = tuple(reduced)
        except SummaryLimitExceeded:
            raise LlmFailure("SUMMARY_LIMIT_EXCEEDED", retryable=False) from None

    async def _extract(self, requests: tuple[LlmRequest, ...]) -> list[str]:
        semaphore = asyncio.Semaphore(self._limits.concurrency)

        async def extract(request):
            async with semaphore:
                return await self._call(request, intermediate=True)

        tasks = [asyncio.create_task(extract(request)) for request in requests]
        try:
            return await asyncio.gather(*tasks)
        except (Exception, asyncio.CancelledError):
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    async def _call(self, request: LlmRequest, *, intermediate=False) -> str:
        value = await self._gateway.complete(request)
        try:
            parsed = SummaryOutput.model_validate(dict(value))
        except (ValidationError, ValueError, TypeError):
            raise LlmFailure("LLM_OUTPUT_INVALID") from None
        if intermediate and len(parsed.conclusion.encode("utf-8")) > self._limits.partial_bytes:
            raise LlmFailure("LLM_OUTPUT_INVALID", retryable=False)
        return parsed.conclusion
