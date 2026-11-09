"""Executor tuning values. Immutable, with defaults; environment wiring is done by the app later."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class ExecutorConfig:
    poll_interval: timedelta = timedelta(seconds=2)
    heartbeat_interval: timedelta = timedelta(seconds=10)
    stale_after: timedelta = timedelta(seconds=60)
    max_pending_wait: timedelta = timedelta(minutes=10)
    llm_timeout: timedelta = timedelta(seconds=120)
    maintenance_interval: timedelta = timedelta(seconds=30)
    concurrency: int = 4
    recovery_batch: int = 100

    def __post_init__(self) -> None:
        durations = (
            self.poll_interval,
            self.heartbeat_interval,
            self.stale_after,
            self.max_pending_wait,
            self.llm_timeout,
            self.maintenance_interval,
        )
        if any(value <= timedelta(0) for value in durations):
            raise ValueError("Executor intervals must be positive")
        if self.stale_after <= self.heartbeat_interval:
            raise ValueError("stale_after must be longer than heartbeat_interval")
        if self.concurrency < 1 or self.recovery_batch < 1:
            raise ValueError("Executor concurrency and batch size must be positive")
