"""A cancel commit hook targets the captured call, even after the Run is retried."""

import asyncio
from uuid import uuid4

from ramus_api.modules.execution.application.inflight import InFlightCalls


async def test_captured_abort_cannot_cancel_a_new_attempt_of_the_same_run():
    calls, run_id = InFlightCalls(), uuid4()
    loop = asyncio.get_running_loop()
    old_call, new_call = loop.create_future(), loop.create_future()
    calls.register(run_id, old_call)
    committed_cancel = calls.capture_abort(run_id)
    calls.unregister(run_id, old_call)
    calls.register(run_id, new_call)
    assert committed_cancel()
    await asyncio.sleep(0)
    assert old_call.cancelled()
    assert not new_call.cancelled()
    assert calls.abort(run_id)
    await asyncio.sleep(0)
    assert new_call.cancelled()


async def test_capturing_no_current_call_cannot_abort_a_later_attempt():
    calls, run_id = InFlightCalls(), uuid4()
    committed_cancel = calls.capture_abort(run_id)
    call = asyncio.get_running_loop().create_future()
    calls.register(run_id, call)
    assert not committed_cancel()
    await asyncio.sleep(0)
    assert not call.cancelled()
    call.cancel()
