"""Protocol and grounding tests for the configured Ark model adapters."""

import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError


def test_anthropic_compatible_provider_uses_messages_protocol_without_exposing_key():
    from personal_brain_infra.models.volcengine import AnthropicCompatibleProvider

    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["has_key"] = bool(request.headers.get("x-api-key"))
        return httpx.Response(200, json={
            "model": "deepseek-v4.1-flash", "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "仅依据证据回答。"}],
            "usage": {"input_tokens": 3, "output_tokens": 5},
        })

    provider = AnthropicCompatibleProvider(
        "https://ark.cn-beijing.volces.com/api/coding", SecretStr("fixture-value"),
        "deepseek-v4.1-flash", transport=httpx.MockTransport(handler),
    )
    result = provider({"request": {"prompt": "问题"}, "context": {"sources": ["证据"]}})
    assert observed == {"path": "/api/coding/v1/messages", "has_key": True}
    assert result["text"] == "仅依据证据回答。"
    assert "fixture-value" not in repr(provider) and "fixture-value" not in repr(result)


def test_anthropic_compatible_provider_disables_thinking_by_default_and_allows_override():
    from personal_brain_infra.models.volcengine import AnthropicCompatibleProvider

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["thinking"] = json.loads(request.content).get("thinking")
        return httpx.Response(200, json={
            "model": "deepseek-v4.1-flash", "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "好。"}], "usage": {},
        })

    provider = AnthropicCompatibleProvider(
        "https://ark.cn-beijing.volces.com/api/coding", SecretStr("fixture-value"),
        "deepseek-v4.1-flash", transport=httpx.MockTransport(handler),
    )
    provider({"request": {"prompt": "问"}, "context": {}})
    assert seen["thinking"] == {"type": "disabled"}

    provider({"request": {"prompt": "问", "thinking": {"type": "enabled", "budget_tokens": 1024}}, "context": {}})
    assert seen["thinking"] == {"type": "enabled", "budget_tokens": 1024}


def test_anthropic_compatible_provider_fails_when_thinking_eats_all_tokens():
    """Regression: reasoning-only response (stop_reason=max_tokens, no text) must
    surface as BRAIN_UNAVAILABLE instead of an empty answer."""
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.models.volcengine import AnthropicCompatibleProvider

    provider = AnthropicCompatibleProvider(
        "https://ark.cn-beijing.volces.com/api/coding", SecretStr("fixture-value"),
        "deepseek-v4.1-flash",
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={
            "model": "deepseek-v4.1-flash", "stop_reason": "max_tokens",
            "content": [{"type": "thinking", "thinking": "很长的思考……"}], "usage": {},
        })),
    )
    with pytest.raises(BrainError) as caught:
        provider({"request": {"prompt": "问", "thinking": {"type": "enabled"}}, "context": {}})
    assert caught.value.code == "BRAIN_UNAVAILABLE"


def test_embedding_provider_uses_multimodal_protocol_and_validates_dimensions():
    from personal_brain_infra.models.volcengine import VolcengineEmbeddingProvider

    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["bearer"] = request.headers.get("authorization", "").startswith("Bearer ")
        return httpx.Response(200, json={"data": {"embedding": [0.1, 0.2, 0.3]}})

    provider = VolcengineEmbeddingProvider(
        "https://ark.cn-beijing.volces.com/api/coding/v3", SecretStr("fixture-value"),
        "doubao-embedding-vision", dimensions=3, transport=httpx.MockTransport(handler),
    )
    assert provider.embed("合成检索文本") == [0.1, 0.2, 0.3]
    assert observed == {"path": "/api/coding/v3/embeddings/multimodal", "bearer": True}
    assert provider.model_version.endswith(":3")


def test_embedding_provider_rejects_secret_like_text_before_network():
    from personal_brain_domain.common.errors import BrainError
    from personal_brain_infra.models.volcengine import VolcengineEmbeddingProvider

    provider = VolcengineEmbeddingProvider(
        "https://ark.cn-beijing.volces.com/api/coding/v3", SecretStr("fixture-value"),
        "doubao-embedding-vision", dimensions=3,
        transport=httpx.MockTransport(lambda _request: pytest.fail("network must not be called")),
    )
    with pytest.raises(BrainError) as caught:
        provider.embed("token=abcdefghijklmnopqrstuvwxyz")
    assert caught.value.code == "SECRET_REJECTED"


def test_external_model_settings_require_secret_file_and_approved_host(tmp_path):
    from personal_brain_server.bootstrap.settings import Settings

    base = dict(
        _env_file=None, environment="test", data_root=tmp_path / "data",
        database_dsn_file=tmp_path / "dsn", token_pepper_file=tmp_path / "pepper",
        external_models_enabled=True,
    )
    with pytest.raises(ValidationError):
        Settings(**base)
    with pytest.raises(ValidationError):
        Settings(**base, model_api_key_file=tmp_path / "key",
                 chat_model_base_url="https://example.invalid/api")
    configured = Settings(**base, model_api_key_file=tmp_path / "key")
    assert configured.safe_summary()["chat_model_name"] == "deepseek-v4.1-flash"
    assert "key" not in repr(configured.model_dump())


def test_answer_brain_is_grounded_in_permission_filtered_search():
    from personal_brain_infra.models.gateway import ModelCard, ModelGateway
    from personal_brain_server.api.authorized_tools import AuthorizedToolService

    owner_id, calls = uuid4(), []

    class Authority:
        def authenticate(self, credential):
            assert credential == "opaque"
            return SimpleNamespace(owner_id=owner_id, client_id=uuid4())

        def authorize(self, context, **kwargs):
            calls.append(kwargs)

    class Search:
        def search(self, **kwargs):
            return [{
                "excerpt": "已确认事实", "source_links": ["raw_input:synthetic"],
                "freshness": "fresh", "warnings": [],
            }]

    gateway = ModelGateway(
        provider=lambda payload: {"text": "根据证据：已确认事实", "model": payload["model"]},
        card=ModelCard(
            name="deepseek-v4.1-flash", version="v1", dimensions=0,
            tokenizer="compatible", sensitivity="private", max_input_tokens=1000,
            allowed_context_keys=("sources",),
        ), max_calls=1,
    )
    service = AuthorizedToolService(
        Authority(), lambda **_kwargs: None,
        search_factory=lambda **_kwargs: Search(), model_gateway=gateway,
    )
    result = service.answer_brain(
        credential="opaque", query="问题", requested_scope="knowledge",
    )
    assert result["grounded"] is True
    assert result["sources"][0]["excerpt"] == "已确认事实"
    assert len(calls) >= 3
