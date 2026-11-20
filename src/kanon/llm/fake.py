"""A scripted stand-in for `LLMClient`, for tests of everything that calls a model."""

from collections.abc import Sequence
from typing import Any

from kanon.llm.client import LLMError, Message


class FakeLLMClient:
    """Returns queued replies in order and records every call.

    A queued `LLMError` (or any exception) is raised instead of returned.
    """

    def __init__(self, replies: Sequence[str | Exception] = ()) -> None:
        self._replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: Sequence[Message],
        *,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        self.calls.append(
            {
                "messages": list(messages),
                "max_tokens": max_tokens,
                "response_format": response_format,
            }
        )
        if not self._replies:
            raise LLMError("FakeLLMClient has no reply queued")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
