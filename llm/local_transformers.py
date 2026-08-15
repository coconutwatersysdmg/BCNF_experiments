"""Local HuggingFace / transformers client (optional dependency)."""

from __future__ import annotations

import time
from typing import Any, Optional, Sequence

from llm.base import LLMClient, LLMResponse


class LocalTransformersClient(LLMClient):
    """Generate with a local transformers model (e.g. Qwen).

    Requires optional packages: transformers, torch.
    Algorithm experiments do NOT depend on these packages.
    """

    def __init__(
        self,
        model: str,
        device: Optional[str] = None,
        max_new_tokens: int = 64,
    ) -> None:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
            import torch  # type: ignore
        except ImportError as e:
            raise ImportError(
                "LocalTransformersClient requires optional deps: transformers, torch. "
                "Install them only if you need local LLM experiments."
            ) from e

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model, trust_remote_code=True)
        self.model_obj = AutoModelForCausalLM.from_pretrained(
            model, trust_remote_code=True
        )
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model_obj.to(device)
        self.max_new_tokens = max_new_tokens
        self.model_name = model

    def generate(
        self,
        messages: Sequence[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 64,
    ) -> LLMResponse:
        # Simple chat formatting
        parts = []
        for m in messages:
            parts.append(f"{m.get('role', 'user').upper()}: {m.get('content', '')}")
        parts.append("ASSISTANT:")
        prompt = "\n".join(parts)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        t0 = time.perf_counter()
        do_sample = temperature > 0
        with self.torch.no_grad():
            out = self.model_obj.generate(
                **inputs,
                max_new_tokens=max_tokens or self.max_new_tokens,
                do_sample=do_sample,
                temperature=max(temperature, 1e-5) if do_sample else None,
            )
        latency = time.perf_counter() - t0
        gen = out[0][inputs["input_ids"].shape[-1] :]
        text = self.tokenizer.decode(gen, skip_special_tokens=True)
        return LLMResponse(
            text=text.strip(),
            latency_sec=latency,
            prompt_tokens=int(inputs["input_ids"].shape[-1]),
            completion_tokens=int(gen.shape[-1]),
            raw={},
        )
