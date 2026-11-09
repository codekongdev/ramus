"""Error codes the executor stores or raises. Sentences live in the message table, never here."""

AI_CONNECTION_REQUIRED = "AI_CONNECTION_REQUIRED"
ACTIVE_RUN_EXISTS = "ACTIVE_RUN_EXISTS"
RUN_NOT_CANCELLABLE = "RUN_NOT_CANCELLABLE"
RUN_NOT_RETRYABLE = "RUN_NOT_RETRYABLE"

LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
LLM_OUTPUT_INVALID = "LLM_OUTPUT_INVALID"
LLM_TIMEOUT = "LLM_TIMEOUT"
SUMMARY_LIMIT_EXCEEDED = "SUMMARY_LIMIT_EXCEEDED"
RUN_INTERRUPTED = "RUN_INTERRUPTED"
RUN_TIMED_OUT = "RUN_TIMED_OUT"
RUN_CREDENTIAL_MISMATCH = "RUN_CREDENTIAL_MISMATCH"

# HTTP fallback codes (shared/presentation/errors.py) the executor's services also raise.
FORBIDDEN = "FORBIDDEN"
NOT_FOUND = "NOT_FOUND"


class ActiveRunConflict(Exception):
    """The database rejected a second active run for the same conversation or summary target."""
