"""DeepSeek OpenAI-compatible Chat Completions provider.

The outbound model value is a constant. It is intentionally impossible for a
request-level argument or an environment variable to switch it to a Pro model.
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

import httpx

from app.core.config import DEEPSEEK_FLASH_MODEL, settings
from app.services.providers.base import ProviderRequestError, ProviderResponse
from app.utils.logger import logger
from app.utils.redaction import redact_sensitive


class DeepSeekProvider:
    name = "deepseek"
    model = DEEPSEEK_FLASH_MODEL

    def __init__(self) -> None:
        self.base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")
        self.api_key = settings.DEEPSEEK_API_KEY.strip()
        self.timeout = settings.LLM_TIMEOUT
        self.max_retries = settings.LLM_MAX_RETRIES
        self.last_retry_count = 0

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ProviderRequestError("DEEPSEEK_API_KEY 未配置")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _messages(prompt: str, system: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system.strip():
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _payload(
        self,
        prompt: str,
        system: str,
        temperature: float | None,
        max_tokens: int | None,
        json_mode: bool,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": DEEPSEEK_FLASH_MODEL,
            "messages": self._messages(prompt, system),
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            "stream": stream,
        }
        if max_tokens:
            payload["max_tokens"] = max(64, min(int(max_tokens), 8192))
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    @staticmethod
    def _safe_http_error(exc: httpx.HTTPStatusError) -> str:
        status = exc.response.status_code
        try:
            body = exc.response.json()
            detail = body.get("error", {}).get("message") or body.get("message") or ""
        except Exception:
            detail = exc.response.text
        detail = redact_sensitive(
            " ".join(str(detail).split()),
            secrets=(settings.DEEPSEEK_API_KEY,),
        )[:240]
        return f"HTTP {status}: {detail or '远端服务拒绝请求'}"

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ProviderResponse:
        payload = self._payload(prompt, system, temperature, max_tokens, json_mode, False)
        last_error = "未知错误"
        retries = 0
        timeout = httpx.Timeout(self.timeout, connect=min(10.0, float(self.timeout)))

        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                text = str(data["choices"][0]["message"]["content"] or "")
                if not text.strip():
                    raise ProviderRequestError("远端返回空内容", retries)
                usage = data.get("usage") or {}
                return ProviderResponse(
                    text=text,
                    prompt_tokens=int(usage.get("prompt_tokens") or max(1, len(prompt) // 4)),
                    completion_tokens=int(usage.get("completion_tokens") or max(1, len(text) // 4)),
                    response_chars=len(text),
                    retry_count=retries,
                )
            except httpx.HTTPStatusError as exc:
                last_error = self._safe_http_error(exc)
                if exc.response.status_code in {400, 401, 403, 404, 422}:
                    raise ProviderRequestError(last_error, retries) from exc
            except httpx.TimeoutException as exc:
                last_error = f"请求超时（{self.timeout}s）"
            except httpx.RequestError as exc:
                last_error = f"网络连接失败：{type(exc).__name__}"
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = f"远端响应格式异常：{type(exc).__name__}"
            except ProviderRequestError:
                raise
            except Exception as exc:
                last_error = f"远端调用异常：{type(exc).__name__}"

            if attempt < self.max_retries:
                retries += 1
                delay = min(2 ** attempt, 4)
                logger.warning(
                    "AI 远端调用未完成，准备重试 %s/%s：%s",
                    retries,
                    self.max_retries,
                    last_error,
                )
                time.sleep(delay)

        raise ProviderRequestError(last_error, retries)

    def stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        payload = self._payload(prompt, system, temperature, max_tokens, False, True)
        timeout = httpx.Timeout(self.timeout, connect=min(10.0, float(self.timeout)))
        last_error = "未知错误"
        retries = 0
        self.last_retry_count = 0

        for attempt in range(self.max_retries + 1):
            emitted = False
            try:
                with httpx.Client(timeout=timeout) as client:
                    with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    ) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            raw = line[6:].strip()
                            if raw == "[DONE]":
                                break
                            try:
                                data = json.loads(raw)
                                delta = data["choices"][0].get("delta", {}).get("content", "")
                            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
                                continue
                            if delta:
                                emitted = True
                                yield str(delta)
                if not emitted:
                    last_error = "远端返回空内容"
                else:
                    self.last_retry_count = retries
                    return
            except httpx.HTTPStatusError as exc:
                last_error = self._safe_http_error(exc)
                if exc.response.status_code in {400, 401, 403, 404, 422}:
                    self.last_retry_count = retries
                    raise ProviderRequestError(last_error, retries) from exc
            except httpx.TimeoutException:
                last_error = f"请求超时（{self.timeout}s）"
            except httpx.RequestError as exc:
                last_error = f"网络连接失败：{type(exc).__name__}"
            except ProviderRequestError:
                raise
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = f"流式响应异常：{type(exc).__name__}"

            # Retrying after text has already reached the browser would repeat
            # content. Connection/status/empty-response failures before the
            # first token are retried with the same policy as normal calls.
            if emitted:
                self.last_retry_count = retries
                raise ProviderRequestError(last_error, retries)
            if attempt < self.max_retries:
                retries += 1
                delay = min(2 ** attempt, 4)
                logger.warning(
                    "AI 流式调用未完成，准备重试 %s/%s：%s",
                    retries,
                    self.max_retries,
                    last_error,
                )
                time.sleep(delay)

        self.last_retry_count = retries
        raise ProviderRequestError(last_error, retries)
