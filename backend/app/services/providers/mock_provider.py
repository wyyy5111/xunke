"""Offline provider used for complete local demonstrations and safe fallback."""
from __future__ import annotations

from collections.abc import Iterator

from app.services.builtin_generator import BuiltinGenerator
from app.services.providers.base import ProviderResponse


class MockProvider:
    name = "mock"
    model = "local-course-engine"

    def __init__(self) -> None:
        self._generator = BuiltinGenerator()

    def generate(self, prompt: str, system: str = "", **_: object) -> ProviderResponse:
        text = self._generator.chat(prompt, system)
        return ProviderResponse(
            text=text,
            prompt_tokens=max(1, len(prompt) // 4),
            completion_tokens=max(1, len(text) // 4),
            response_chars=len(text),
        )

    def stream(self, prompt: str, system: str = "", **_: object) -> Iterator[str]:
        yield from self._generator.stream(prompt, system)
