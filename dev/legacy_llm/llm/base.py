"""LLM client base interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence


@dataclass
class LLMResponse:
    text: str
    latency_sec: float = 0.0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict)


class LLMClient(ABC):
    """Unified LLM client interface."""

    @abstractmethod
    def generate(
        self,
        messages: Sequence[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 64,
    ) -> LLMResponse:
        raise NotImplementedError
