from types import SimpleNamespace

from app import rag


def _response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_default_chat_uses_local_ollama_qwen(monkeypatch):
    captured = {}
    monkeypatch.setattr(rag, "LLM_MODEL", "ollama_chat/qwen2.5:3b")
    monkeypatch.setattr(rag, "OLLAMA", "http://ollama:11434")
    monkeypatch.setattr(rag, "LLM_API_BASE", "")
    monkeypatch.setattr(rag, "LLM_API_KEY", "")

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _response("local answer")

    monkeypatch.setattr(rag, "completion", fake_completion)

    result = rag._chat_completion([{"role": "user", "content": "hello"}])

    assert result == "local answer"
    assert captured["model"] == "ollama_chat/qwen2.5:3b"
    assert captured["api_base"] == "http://ollama:11434"
    assert captured["extra_body"] == {"options": {"num_ctx": 4096}}


def test_external_provider_uses_configured_model_and_key(monkeypatch):
    captured = {}
    monkeypatch.setattr(rag, "LLM_MODEL", "openai/example-model")
    monkeypatch.setattr(rag, "LLM_API_BASE", "")
    monkeypatch.setattr(rag, "LLM_API_KEY", "test-secret")

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _response("external answer")

    monkeypatch.setattr(rag, "completion", fake_completion)

    result = rag._chat_completion([{"role": "user", "content": "hello"}])

    assert result == "external answer"
    assert captured["model"] == "openai/example-model"
    assert captured["api_key"] == "test-secret"
    assert "api_base" not in captured
    assert "extra_body" not in captured


def test_custom_openai_compatible_endpoint_is_forwarded(monkeypatch):
    captured = {}
    monkeypatch.setattr(rag, "LLM_MODEL", "openai/custom-model")
    monkeypatch.setattr(rag, "LLM_API_BASE", "https://llm.example.test/v1")
    monkeypatch.setattr(rag, "LLM_API_KEY", "custom-secret")

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _response([{"type": "text", "text": "custom answer"}])

    monkeypatch.setattr(rag, "completion", fake_completion)

    result = rag._chat_completion([{"role": "user", "content": "hello"}])

    assert result == "custom answer"
    assert captured["api_base"] == "https://llm.example.test/v1"
    assert captured["api_key"] == "custom-secret"
