"""Volcengine Ark compatible chat and multimodal embedding clients.

The API key is accepted only as a ``SecretStr`` loaded from a mounted file.  No
request/response headers or payload bodies are logged here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import httpx
from pydantic import SecretStr

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.secret_filter import detect_secret


def _endpoint(base_url: str, suffix: str) -> str:
    return f"{base_url.rstrip('/')}/{suffix.lstrip('/')}"


# Chunk texts per embeddings call; a batch failure falls back to single items.
EMBED_BATCH_SIZE = 10


@dataclass(frozen=True)
class AnthropicCompatibleProvider:
    base_url: str
    api_key: SecretStr
    model: str
    uds: str | None = None
    transport: httpx.BaseTransport | None = None

    def __call__(self, payload: Mapping[str, Any], *, timeout_seconds: int = 60) -> dict[str, Any]:
        request = dict(payload.get("request") or {})
        context = dict(payload.get("context") or {})
        prompt = str(request.get("prompt") or request.get("query") or "").strip()
        if not prompt:
            prompt = "Produce the requested derived content from the supplied context."
        messages = [{"role": "user", "content": prompt}]
        if context:
            import json
            messages.append({
                "role": "user",
                "content": "Authoritative context (do not invent beyond it):\n" +
                json.dumps(context, ensure_ascii=False, default=str),
            })
        body = {
            "model": self.model,
            "max_tokens": min(max(int(request.get("max_tokens", 1024)), 1), 4096),
            "messages": messages,
        }
        thinking = request.get("thinking")
        if thinking is None:
            # Reasoning-class models (deepseek-v4.1) otherwise burn the whole
            # token budget on the internal thinking block, returning an empty
            # text block (stop_reason=max_tokens) that surfaces as
            # BRAIN_UNAVAILABLE. Evidence-backed answers do not need that
            # internal reasoning; callers may still opt in via request.
            thinking = {"type": "disabled"}
        body["thinking"] = thinking
        system = request.get("system")
        if system:
            body["system"] = str(system)
        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key.get_secret_value(),
            "anthropic-version": "2023-06-01",
        }
        try:
            transport = self.transport or (httpx.HTTPTransport(uds=self.uds) if self.uds else None)
            with httpx.Client(transport=transport, timeout=timeout_seconds) as client:
                response = client.post(_endpoint(self.base_url, "v1/messages"), headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise BrainError("BRAIN_UNAVAILABLE") from error
        content = data.get("content")
        if not isinstance(content, list):
            raise BrainError("BRAIN_UNAVAILABLE")
        text = "".join(
            str(item.get("text", "")) for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()
        if not text:
            raise BrainError("BRAIN_UNAVAILABLE")
        return {
            "text": text,
            "model": str(data.get("model") or self.model),
            "stop_reason": data.get("stop_reason"),
            "usage": data.get("usage") or {},
        }


@dataclass(frozen=True)
class VolcengineEmbeddingProvider:
    base_url: str
    api_key: SecretStr
    model: str
    dimensions: int = 1024
    uds: str | None = None
    transport: httpx.BaseTransport | None = None

    @property
    def model_version(self) -> str:
        return f"volcengine:{self.model}:{self.dimensions}"

    def embed(self, text: str, *, timeout_seconds: int = 60) -> list[float]:
        if not text.strip():
            raise BrainError("VALIDATION_FAILED")
        if detect_secret(filename="embedding-input.txt", content_type="text/plain", content=text).matched:
            raise BrainError("SECRET_REJECTED")
        return self._embed_batch([text], timeout_seconds=timeout_seconds)[0]

    def embed_many(self, texts: Sequence[str], *, timeout_seconds: int = 60) -> list[list[float]]:
        """Embed the chunk texts of one long document.

        Any secret-like chunk degrades the whole card (``SECRET_REJECTED``) —
        decision (b): suspect content is never sent upstream, even in part.
        Batches are sent together when the provider accepts them; a batch that
        fails while bigger than one item falls back to single-item calls so an
        input-count cap never blocks indexing (a genuinely unavailable provider
        still fails the first single call and surfaces honestly).
        """
        if not texts:
            raise BrainError("VALIDATION_FAILED")
        for text in texts:
            if not text.strip():
                raise BrainError("VALIDATION_FAILED")
            if detect_secret(filename="embedding-input.txt", content_type="text/plain", content=text).matched:
                raise BrainError("SECRET_REJECTED")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[start:start + EMBED_BATCH_SIZE]
            try:
                vectors.extend(self._embed_batch(batch, timeout_seconds=timeout_seconds))
            except BrainError as error:
                if error.code == "BRAIN_UNAVAILABLE" and len(batch) > 1:
                    for text in batch:
                        vectors.append(self.embed(text, timeout_seconds=timeout_seconds))
                else:
                    raise
        return vectors

    def _embed_batch(self, texts: Sequence[str], *, timeout_seconds: int) -> list[list[float]]:
        body = {
            "model": self.model,
            "encoding_format": "float",
            "dimensions": self.dimensions,
            "instructions": "Target_modality: text. Instruction: Retrieve semantically similar personal knowledge.",
            "input": [{"type": "text", "text": text} for text in texts],
        }
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.api_key.get_secret_value()}",
        }
        try:
            transport = self.transport or (httpx.HTTPTransport(uds=self.uds) if self.uds else None)
            with httpx.Client(transport=transport, timeout=timeout_seconds) as client:
                response = client.post(
                    _endpoint(self.base_url, "embeddings/multimodal"), headers=headers, json=body,
                )
                response.raise_for_status()
                data = response.json().get("data")
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as error:
            raise BrainError("BRAIN_UNAVAILABLE") from error
        if isinstance(data, dict):
            data = [data]
        if not (isinstance(data, list) and len(data) == len(texts)):
            raise BrainError("BRAIN_UNAVAILABLE")
        vectors = []
        for item in data:
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list) or len(vector) != self.dimensions:
                raise BrainError("BRAIN_UNAVAILABLE")
            try:
                vectors.append([float(value) for value in vector])
            except (TypeError, ValueError) as error:
                raise BrainError("BRAIN_UNAVAILABLE") from error
        return vectors
