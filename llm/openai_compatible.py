"""OpenAI-compatible HTTP client (GLM / DeepSeek / etc.).

Credentials and endpoints come from environment variables or constructor
arguments — nothing is hard-coded.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional, Sequence

from llm.base import LLMClient, LLMResponse


class OpenAICompatibleClient(LLMClient):
    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_sec: float = 120.0,
    ) -> None:
        self.model = model
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        self.timeout_sec = timeout_sec
        if not self.base_url:
            raise ValueError(
                "base_url is required (pass --base-url or set LLM_BASE_URL)"
            )
        if not self.api_key:
            raise ValueError(
                "api_key is required (pass --api-key or set LLM_API_KEY / OPENAI_API_KEY)"
            )

    def generate(
        self,
        messages: Sequence[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 64,
    ) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTPError {e.code}: {err}") from e
        latency = time.perf_counter() - t0
        text = body["choices"][0]["message"]["content"]
        usage = body.get("usage") or {}
        return LLMResponse(
            text=text if isinstance(text, str) else str(text),
            latency_sec=latency,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            raw=body,
        )
