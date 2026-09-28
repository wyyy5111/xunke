"""Provider shared contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProviderResponse:
    text: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    response_chars: int = 0
    retry_count: int = 0


class ProviderRequestError(RuntimeError):
    """A sanitized provider failure safe to persist in application logs."""

    def __init__(self, message: str, retry_count: int = 0):
        super().__init__(message)
        self.retry_count = retry_count
