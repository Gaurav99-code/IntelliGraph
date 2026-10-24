import sys
from types import SimpleNamespace
from typing import Any

import pytest

from backend.llm_client import LLMClient, LLMConfigurationError


def install_fake_openai(monkeypatch, captured):
    class FakeCompletions:
        def create(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))


def test_ollama_status_does_not_require_api_key():
    client = LLMClient(provider="ollama", model="llama3.2", enabled=True)

    assert client.status() == {
        "llm_enabled": True,
        "llm_provider": "ollama",
        "llm_model": "llama3.2",
        "llm_configured": True,
    }


def test_ollama_uses_local_defaults_without_api_key(monkeypatch):
    captured: dict[str, Any] = {}
    install_fake_openai(monkeypatch, captured)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)

    client = LLMClient(provider="ollama", model="llama3.2", enabled=True)
    assert client.generate_json("system", "user", {"type": "object"}) == {"ok": True}
    assert captured["client"] == {
        "api_key": "ollama",
        "timeout": 45.0,
        "base_url": "http://localhost:11434/v1",
    }


def test_ollama_uses_configured_base_url(monkeypatch):
    captured: dict[str, Any] = {}
    install_fake_openai(monkeypatch, captured)
    monkeypatch.setenv("LLM_BASE_URL", "http://ollama.internal:11434/v1")

    client = LLMClient(provider="ollama", model="llama3.2", enabled=True)
    assert client.generate_json("system", "user", {"type": "object"}) == {"ok": True}
    assert captured["client"]["base_url"] == "http://ollama.internal:11434/v1"


def test_ollama_json_response_parsing():
    assert LLMClient.parse_json("```json\n{\"ok\": true}\n```") == {"ok": True}


def test_openai_still_requires_api_key():
    client = LLMClient(provider="openai", model="gpt-4o-mini", enabled=True)

    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY"):
        client.generate_json("system", "user", {"type": "object"})
