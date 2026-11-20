"""A minimal chat client: send messages, get text back.

Deliberately small (ADR-003): one POST to `{base_url}/chat/completions`, an explicit timeout on
every call, and one domain error for everything that can go wrong. Callers depend on the
`LLMClient` protocol, so tests substitute a fake and a native provider adapter could replace this
class later without touching them.

The API key is only ever placed in the Authorization header. It is not logged, not part of any
error message, and not shown by `repr()`.
"""

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx2

from kanon.settings import Settings

logger = logging.getLogger("kanon.llm")

DEFAULT_TIMEOUT_SECONDS = 60.0
_MAX_ERROR_DETAIL = 300


class LLMError(Exception):
    """A model call failed: not configured, unreachable, timed out, rejected or unusable reply."""


@dataclass(frozen=True)
class Message:
    role: str  # "system", "user" or "assistant"
    content: str


class LLMClient(Protocol):
    """What the rest of Kanon needs from a model."""

    def chat(
        self,
        messages: Sequence[Message],
        *,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Send the conversation and return the model's text reply. Raises `LLMError`."""
        ...


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        if not (base_url and api_key and model):
            raise LLMError("the model endpoint is not fully configured")
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self.model = model
        self.timeout = timeout
        # One bound for connect, write, read and pool wait alike: no call can hang forever.
        self._http = httpx2.Client(timeout=httpx2.Timeout(timeout), transport=transport)

    def __repr__(self) -> str:  # never include the key
        return f"OpenAICompatibleClient(url={self._url!r}, model={self.model!r})"

    def close(self) -> None:
        self._http.close()

    def chat(
        self,
        messages: Sequence[Message],
        *,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if response_format is not None:
            body["response_format"] = response_format

        started = time.monotonic()
        try:
            response = self._http.post(
                self._url, json=body, headers={"Authorization": f"Bearer {self._api_key}"}
            )
        except httpx2.TimeoutException:
            self._log("timeout", started)
            raise LLMError(f"the model did not answer within {self.timeout:g}s") from None
        except httpx2.TransportError as error:
            self._log("unreachable", started)
            raise LLMError(f"cannot reach the model endpoint: {type(error).__name__}") from None

        self._log(str(response.status_code), started)
        if response.status_code != 200:
            raise LLMError(
                f"the model endpoint returned HTTP {response.status_code}: "
                f"{self._error_detail(response)}"
            )
        return self._text(response)

    def _text(self, response: httpx2.Response) -> str:
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError("the model endpoint sent a reply in an unexpected format") from None
        if not isinstance(content, str) or not content:
            raise LLMError("the model reply contained no text")
        return content

    def _error_detail(self, response: httpx2.Response) -> str:
        """A short, key-free description of what the provider said."""
        try:
            detail = response.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            detail = response.text
        detail = " ".join(str(detail).split())[:_MAX_ERROR_DETAIL]
        return detail.replace(self._api_key, "[redacted]") or "(no details)"

    def _log(self, outcome: str, started: float) -> None:
        # Metadata only. Never headers, never the request body, never the key.
        logger.info(
            "llm call",
            extra={
                "model": self.model,
                "outcome": outcome,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
            },
        )


def get_llm_client(settings: Settings) -> OpenAICompatibleClient:
    """Build the configured client, or explain what is missing."""
    missing = [
        name
        for name, value in (
            ("KANON_LLM_BASE_URL", settings.llm_base_url),
            ("KANON_LLM_API_KEY", settings.llm_api_key),
            ("KANON_LLM_MODEL", settings.llm_model),
        )
        if not value
    ]
    if missing:
        raise LLMError(f"no model configured: set {', '.join(missing)}")
    return OpenAICompatibleClient(
        settings.llm_base_url,
        settings.llm_api_key.get_secret_value(),
        settings.llm_model,
        timeout=settings.llm_timeout_seconds,
    )
