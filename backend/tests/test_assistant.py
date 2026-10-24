"""Provider contract and graceful fallback, without network or external LLM."""
import json

import httpx
import pytest

from app.config import Settings
from app.services import assistant


@pytest.mark.parametrize("provider", ["ollama", "openai_compatible"])
def test_provider_contract(monkeypatch, provider):
    settings = Settings(llm_provider=provider, llm_base_url="http://model/v1/",
                        llm_api_key="test-key", llm_model="open-weights-demo")
    monkeypatch.setattr(assistant, "get_settings", lambda: settings)
    purpose = next(iter(assistant.PURPOSES))

    def post(url, **kwargs):
        if provider == "openai_compatible":
            assert url == "http://model/v1/chat/completions"
            assert kwargs["headers"] == {"Authorization": "Bearer test-key"}
            assert kwargs["json"]["model"] == "open-weights-demo"
            assert kwargs["json"]["messages"][0]["role"] == "user"
            payload = {"choices": [{"message": {"content": json.dumps({"purpose": purpose})}}]}
        else:
            assert url.endswith("/api/generate")
            payload = {"response": json.dumps({"purpose": purpose})}
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(assistant.httpx, "post", post)
    assert assistant.classify_llm("закупить товар") == purpose


@pytest.mark.parametrize("failure", ["timeout", "malformed", "http_error"])
def test_llm_failure_falls_back_to_rules(monkeypatch, failure):
    monkeypatch.setattr(assistant, "get_settings", lambda: Settings(llm_enabled=True))
    def fail(_):
        raise {"timeout": httpx.TimeoutException, "malformed": ValueError,
               "http_error": RuntimeError}[failure]("synthetic failure")
    monkeypatch.setattr(assistant, "classify_llm", fail)
    monkeypatch.setattr(assistant, "list_products", lambda db: [])
    result = assistant.recommend(None, "закупить товар", None)
    assert result.engine == "rules"
    assert result.purpose in assistant.PURPOSES
