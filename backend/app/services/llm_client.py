"""Unified LLM client with DeepSeek Flash enforcement and safe local fallback."""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections.abc import Iterator
from typing import Any

from app.core.config import DEEPSEEK_FLASH_MODEL, settings, validate_deepseek_model
from app.core.database import SessionLocal
from app.models.system import LLMCallLog
from app.services.providers import DeepSeekProvider, MockProvider, ProviderResponse
from app.services.providers.base import ProviderRequestError
from app.utils.logger import logger
from app.utils.redaction import redact_sensitive


_log_lock = threading.Lock()


def _persist_call(
    *,
    provider: str,
    model: str,
    purpose: str,
    trace_id: str,
    response: ProviderResponse | None,
    duration_ms: int,
    success: bool,
    error: str = "",
    fallback_used: bool = False,
) -> None:
    """Persist observability data without ever persisting credentials."""
    try:
        with _log_lock:
            db = SessionLocal()
            try:
                row = LLMCallLog(
                    provider=provider,
                    model=model,
                    purpose=purpose,
                    trace_id=trace_id,
                    prompt_tokens=response.prompt_tokens if response else 0,
                    completion_tokens=response.completion_tokens if response else 0,
                    duration_ms=duration_ms,
                    success=success,
                    error=redact_sensitive(
                        error,
                        secrets=(settings.DEEPSEEK_API_KEY, settings.JWT_SECRET),
                    )[:500],
                )
                # New columns are guarded for compatibility with an older SQLite file.
                if hasattr(row, "response_chars"):
                    row.response_chars = response.response_chars if response else 0
                if hasattr(row, "retry_count"):
                    row.retry_count = response.retry_count if response else 0
                if hasattr(row, "fallback_used"):
                    row.fallback_used = fallback_used
                db.add(row)
                db.commit()
            finally:
                db.close()
    except Exception as exc:
        logger.warning("AI 调用日志写入失败：%s", type(exc).__name__)


class LLMClient:
    """Business-facing AI client.

    ``chat`` remains a string-returning compatibility API. Callers can inspect
    ``last_call_info`` immediately afterwards to show real/demo/degraded state.
    """

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.requested_provider = (provider or settings.LLM_PROVIDER).strip().lower()
        if self.requested_provider not in {"mock", "deepseek"}:
            raise ValueError("provider 当前只允许 mock 或 deepseek")
        self.requested_model = validate_deepseek_model(model or settings.LLM_MODEL)
        self._mock = MockProvider()
        self._deepseek = DeepSeekProvider()
        self._last_call_lock = threading.Lock()
        self._calls_by_trace: dict[str, dict[str, Any]] = {}
        self._last_call: dict[str, Any] = {
            "ok": True,
            "provider": "mock",
            "model": self._mock.model,
            "mode": "demo",
            "fallback_used": False,
            "duration_ms": 0,
            "retry_count": 0,
            "trace_id": "",
            "purpose": "",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "response_chars": 0,
            "error": "",
        }

    @property
    def model(self) -> str:
        return DEEPSEEK_FLASH_MODEL

    @property
    def provider(self) -> str:
        return self.requested_provider

    @property
    def effective_provider(self) -> str:
        if self.requested_provider == "deepseek" and settings.deepseek_key_configured:
            return "deepseek"
        return "mock"

    @property
    def is_mock(self) -> bool:
        return self.effective_provider == "mock"

    @property
    def mode(self) -> str:
        return "demo" if self.is_mock else "real"

    @property
    def last_call_info(self) -> dict[str, Any]:
        with self._last_call_lock:
            return dict(self._last_call)

    def call_info(self, trace_id: str) -> dict[str, Any]:
        """Return observability for one trace instead of another concurrent run.

        The global client is shared by FastAPI worker threads. Agent logs must
        not read a different request's latest provider/model/fallback state.
        """
        if not trace_id:
            return {}
        with self._last_call_lock:
            return dict(self._calls_by_trace.get(trace_id, {}))

    def status(self) -> dict[str, Any]:
        return {
            "requested_provider": self.requested_provider,
            "active_provider": self.effective_provider,
            "model": DEEPSEEK_FLASH_MODEL,
            "api_key_configured": settings.deepseek_key_configured,
            "mode": self.mode,
            "pro_models_allowed": False,
            "policy_warning": settings.MODEL_POLICY_WARNING,
            "last_call": self.last_call_info,
        }

    def _set_last(
        self,
        *,
        provider: str,
        model: str,
        purpose: str,
        trace_id: str,
        response: ProviderResponse,
        duration_ms: int,
        success: bool,
        mode: str,
        fallback_used: bool = False,
        error: str = "",
    ) -> None:
        call_info = {
            "ok": success,
            "provider": provider,
            "model": model,
            "mode": mode,
            "fallback_used": fallback_used,
            "duration_ms": duration_ms,
            "retry_count": response.retry_count,
            "trace_id": trace_id,
            "purpose": purpose,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "response_chars": response.response_chars,
            "error": redact_sensitive(
                error,
                secrets=(settings.DEEPSEEK_API_KEY, settings.JWT_SECRET),
            ),
        }
        with self._last_call_lock:
            self._last_call = call_info
            if trace_id:
                # Dict insertion order provides a small bounded LRU-like audit
                # cache without retaining prompts or generated content.
                self._calls_by_trace.pop(trace_id, None)
                self._calls_by_trace[trace_id] = call_info
                while len(self._calls_by_trace) > 512:
                    self._calls_by_trace.pop(next(iter(self._calls_by_trace)))

    def _run_mock(
        self,
        prompt: str,
        system: str,
        purpose: str,
        trace_id: str,
        *,
        fallback_used: bool = False,
        fallback_error: str = "",
        fallback_retry_count: int = 0,
    ) -> str:
        started = time.perf_counter()
        response = self._mock.generate(prompt, system)
        response.retry_count = fallback_retry_count
        duration_ms = int((time.perf_counter() - started) * 1000)
        _persist_call(
            provider="mock",
            model=self._mock.model,
            purpose=purpose,
            trace_id=trace_id,
            response=response,
            duration_ms=duration_ms,
            success=True,
            error=fallback_error,
            fallback_used=fallback_used,
        )
        self._set_last(
            provider="mock",
            model=self._mock.model,
            purpose=purpose,
            trace_id=trace_id,
            response=response,
            duration_ms=duration_ms,
            success=not fallback_used,
            mode="degraded" if fallback_used else "demo",
            fallback_used=fallback_used,
            error=fallback_error,
        )
        return response.text

    def chat(
        self,
        prompt: str,
        system: str = "",
        purpose: str = "general",
        trace_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        trace_id = trace_id or uuid.uuid4().hex[:16]
        if self.effective_provider != "deepseek":
            return self._run_mock(prompt, system, purpose, trace_id)

        started = time.perf_counter()
        try:
            response = self._deepseek.generate(
                prompt,
                system,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            _persist_call(
                provider="deepseek",
                model=DEEPSEEK_FLASH_MODEL,
                purpose=purpose,
                trace_id=trace_id,
                response=response,
                duration_ms=duration_ms,
                success=True,
            )
            self._set_last(
                provider="deepseek",
                model=DEEPSEEK_FLASH_MODEL,
                purpose=purpose,
                trace_id=trace_id,
                response=response,
                duration_ms=duration_ms,
                success=True,
                mode="real",
            )
            logger.info(
                "AI 调用成功 provider=deepseek model=%s purpose=%s trace_id=%s duration_ms=%s",
                DEEPSEEK_FLASH_MODEL,
                purpose,
                trace_id,
                duration_ms,
            )
            return response.text
        except ProviderRequestError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            failed = ProviderResponse(retry_count=exc.retry_count)
            _persist_call(
                provider="deepseek",
                model=DEEPSEEK_FLASH_MODEL,
                purpose=purpose,
                trace_id=trace_id,
                response=failed,
                duration_ms=duration_ms,
                success=False,
                error=str(exc),
            )
            logger.warning(
                "真实 AI 服务调用失败，已切换本地生成 purpose=%s trace_id=%s error=%s",
                purpose,
                trace_id,
                str(exc)[:200],
            )
            return self._run_mock(
                prompt,
                system,
                purpose,
                trace_id,
                fallback_used=True,
                fallback_error=str(exc),
                fallback_retry_count=exc.retry_count,
            )

    def chat_json(
        self,
        prompt: str,
        system: str = "",
        purpose: str = "json_task",
        trace_id: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        trace_id = trace_id or uuid.uuid4().hex[:16]
        text = self.chat(
            prompt,
            system=system,
            purpose=purpose,
            trace_id=trace_id,
            max_tokens=max_tokens,
            json_mode=True,
        )
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
        try:
            data = json.loads(cleaned)
            return data if isinstance(data, dict) else {"items": data}
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.S)
            if match:
                try:
                    data = json.loads(match.group(0))
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError as exc:
                    logger.debug("结构化响应中的 JSON 片段仍无法解析：%s", exc)

        # A syntactically invalid JSON response is a failed structured task.
        # Preserve the remote call log, then produce a deterministic local result.
        if self.effective_provider == "deepseek":
            fallback_text = self._run_mock(
                prompt,
                system,
                purpose,
                trace_id,
                fallback_used=True,
                fallback_error="远端返回内容无法解析为任务所需 JSON",
            )
            fallback_clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", fallback_text.strip(), flags=re.I | re.S)
            try:
                data = json.loads(fallback_clean)
                return data if isinstance(data, dict) else {"items": data}
            except json.JSONDecodeError:
                return {}
        return {}

    def stream(
        self,
        prompt: str,
        system: str = "",
        purpose: str = "general",
        trace_id: str | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        trace_id = trace_id or uuid.uuid4().hex[:16]
        if self.effective_provider != "deepseek":
            yield from self._stream_mock(prompt, system, purpose, trace_id)
            return

        started = time.perf_counter()
        parts: list[str] = []
        try:
            for chunk in self._deepseek.stream(prompt, system, max_tokens=max_tokens):
                parts.append(chunk)
                yield chunk
            text = "".join(parts)
            response = ProviderResponse(
                prompt_tokens=max(1, len(prompt) // 4),
                completion_tokens=max(1, len(text) // 4),
                response_chars=len(text),
                retry_count=self._deepseek.last_retry_count,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            _persist_call(
                provider="deepseek",
                model=DEEPSEEK_FLASH_MODEL,
                purpose=purpose,
                trace_id=trace_id,
                response=response,
                duration_ms=duration_ms,
                success=True,
            )
            self._set_last(
                provider="deepseek",
                model=DEEPSEEK_FLASH_MODEL,
                purpose=purpose,
                trace_id=trace_id,
                response=response,
                duration_ms=duration_ms,
                success=True,
                mode="real",
            )
        except ProviderRequestError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            failed = ProviderResponse(retry_count=exc.retry_count)
            _persist_call(
                provider="deepseek",
                model=DEEPSEEK_FLASH_MODEL,
                purpose=purpose,
                trace_id=trace_id,
                response=failed,
                duration_ms=duration_ms,
                success=False,
                error=str(exc),
            )
            yield "\n\n> 真实 AI 服务暂时不可用，以下内容由本地课程引擎生成。\n\n"
            yield from self._stream_mock(
                prompt,
                system,
                purpose,
                trace_id,
                fallback_used=True,
                fallback_error=str(exc),
                fallback_retry_count=exc.retry_count,
            )

    def _stream_mock(
        self,
        prompt: str,
        system: str,
        purpose: str,
        trace_id: str,
        *,
        fallback_used: bool = False,
        fallback_error: str = "",
        fallback_retry_count: int = 0,
    ) -> Iterator[str]:
        """Stream local content while keeping the same audit record as chat()."""
        started = time.perf_counter()
        parts: list[str] = []
        for chunk in self._mock.stream(prompt, system):
            parts.append(chunk)
            yield chunk
        text = "".join(parts)
        response = ProviderResponse(
            text=text,
            prompt_tokens=max(1, len(prompt) // 4),
            completion_tokens=max(1, len(text) // 4),
            response_chars=len(text),
            retry_count=fallback_retry_count,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        _persist_call(
            provider="mock",
            model=self._mock.model,
            purpose=purpose,
            trace_id=trace_id,
            response=response,
            duration_ms=duration_ms,
            success=True,
            error=fallback_error,
            fallback_used=fallback_used,
        )
        self._set_last(
            provider="mock",
            model=self._mock.model,
            purpose=purpose,
            trace_id=trace_id,
            response=response,
            duration_ms=duration_ms,
            success=not fallback_used,
            mode="degraded" if fallback_used else "demo",
            fallback_used=fallback_used,
            error=fallback_error,
        )


llm_client = LLMClient()
