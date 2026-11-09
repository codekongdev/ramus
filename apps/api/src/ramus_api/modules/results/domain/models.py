from enum import StrEnum


class ResultDraftStatus(StrEnum):
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
