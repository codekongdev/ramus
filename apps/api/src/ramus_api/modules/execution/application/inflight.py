"""Model calls running in this process, so a committed cancel can stop them early."""

import asyncio
import logging
import threading
from uuid import UUID

logger = logging.getLogger(__name__)


class InFlightCalls:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: dict[UUID, tuple[asyncio.AbstractEventLoop, asyncio.Future[object]]] = {}

    def register(self, run_id: UUID, call: asyncio.Future[object]) -> None:
        """Call from the loop that owns ``call``."""
        loop = asyncio.get_running_loop()
        with self._lock:
            self._calls = {**self._calls, run_id: (loop, call)}

    def unregister(self, run_id: UUID, call: asyncio.Future[object]) -> None:
        with self._lock:
            if self._calls.get(run_id, (None, None))[1] is call:
                self._calls = {key: value for key, value in self._calls.items() if key != run_id}

    def abort(self, run_id: UUID) -> bool:
        """Thread-safe. Cancels the call for ``run_id`` if this process is running one."""
        with self._lock:
            entry = self._calls.get(run_id)
        if entry is None:
            return False
        loop, call = entry
        try:
            loop.call_soon_threadsafe(call.cancel)
        except RuntimeError:
            logger.warning("Model call abort dropped because its event loop is closed: run_id=%s", run_id)
            return False
        return True
