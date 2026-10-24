"""Provider-agnostic JSON LLM client used by extraction and later answer generation."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Protocol


class LLMError(RuntimeError):
    """Base error for configured or remote LLM failures."""


class LLMConfigurationError(LLMError):
    """Raised when LLM extraction is enabled without usable configuration."""


class JSONGenerator(Protocol):
    """Structural interface used by extractors and easy to mock in tests."""

    enabled: bool
    api_key: str | None

    def generate_json(self, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any] | str:
        ...


class LLMClient:
    """Small OpenAI-compatible wrapper with retries and JSON repair.

    ``LLM_PROVIDER`` remains part of the public configuration so another
    provider can be added behind this class without changing callers.
    """

    def __init__(
        self,
        provider: str = "openai",
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        enabled: bool = False,
        timeout: float = 45.0,
        max_retries: int = 3,
    ):
        self.provider = provider.lower().strip()
        self.api_key = api_key
        self.model = model
        self.enabled = enabled
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Any | None = None

    @classmethod
    def from_env(cls) -> "LLMClient":
        """Build an LLM client from environment-only configuration."""

        enabled = os.getenv("LLM_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            api_key=os.getenv("LLM_API_KEY"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            enabled=enabled,
            timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "45")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        )

    def status(self) -> dict[str, Any]:
        """Return safe configuration status without exposing credentials."""

        if self.provider == "ollama":
            configured = bool(self.model)
        else:
            configured = bool(self.api_key)
        return {
            "llm_enabled": self.enabled and configured,
            "llm_provider": self.provider,
            "llm_model": self.model,
            "llm_configured": configured,
        }

    def generate_json(self, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate and parse one JSON object, retrying transient failures."""

        if not self.enabled:
            raise LLMConfigurationError("LLM extraction is disabled")
        if self.provider != "ollama" and not self.api_key:
            raise LLMConfigurationError("LLM_ENABLED=true requires LLM_API_KEY")
        if self.provider not in {"openai", "openai-compatible", "ollama"}:
            raise LLMConfigurationError(f"Unsupported LLM_PROVIDER: {self.provider}")

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                raw = self._generate_openai(system_prompt, user_prompt, schema)
                return self.parse_json(raw)
            except Exception as exc:  # pragma: no cover - remote/provider dependent
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(0.5 * (2**attempt))
        raise LLMError(f"LLM JSON generation failed after {self.max_retries} attempts: {last_error}") from last_error

    def _generate_openai(self, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> str:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - dependency setup dependent
                raise LLMConfigurationError("Install the 'openai' package to enable LLM extraction") from exc
            api_key = self.api_key
            if self.provider == "ollama" and not api_key:
                api_key = "ollama"
            kwargs: dict[str, Any] = {"api_key": api_key, "timeout": self.timeout}
            base_url = os.getenv("LLM_BASE_URL")
            if self.provider == "ollama" and not base_url:
                base_url = "http://localhost:11434/v1"
            if base_url:
                kwargs["base_url"] = base_url
            self._client = OpenAI(**kwargs)

        schema_text = json.dumps(schema, ensure_ascii=False)
        client = self._client
        if client is None:
            raise LLMConfigurationError("LLM client was not initialized")
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": f"{system_prompt}\nReturn JSON matching this schema exactly:\n{schema_text}"},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise LLMError("LLM returned an empty response")
        return content

    @staticmethod
    def parse_json(value: str | dict[str, Any]) -> dict[str, Any]:
        """Parse plain or fenced JSON and recover the first object if needed."""

        if isinstance(value, dict):
            return value
        cleaned = value.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start < 0 or end <= start:
                raise LLMError("LLM response did not contain a JSON object")
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as exc:
                raise LLMError("LLM response contained malformed JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMError("LLM response must be a JSON object")
        return parsed
