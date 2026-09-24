"""External model gateway with declared identity, privacy and execution budgets."""

from __future__ import annotations

import inspect
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from personal_brain_domain.common.errors import BrainError
from personal_brain_domain.security.secret_filter import detect_secret

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_CALLS = 2
_SENSITIVITY = {"normal": 0, "personal": 1, "private": 2, "highly_private": 3, "secret": 4}


@dataclass(frozen=True)
class ModelCard:
    name: str
    version: str
    dimensions: int
    tokenizer: str
    sensitivity: str
    max_input_tokens: int
    provider_id: str = "local"
    max_context_bytes: int = 64 * 1024
    allowed_context_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.version or not self.tokenizer or not self.provider_id:
            raise ValueError("model identity is incomplete")
        if self.dimensions < 0 or self.max_input_tokens < 1 or self.max_context_bytes < 1:
            raise ValueError("model dimensions and budgets must be positive")
        if self.sensitivity not in _SENSITIVITY or self.sensitivity == "secret":
            raise ValueError("invalid model sensitivity ceiling")


@dataclass
class ProviderCallBudget:
    max_calls: int = DEFAULT_MAX_CALLS
    calls: int = 0

    def consume(self) -> None:
        if self.calls >= self.max_calls:
            raise BrainError("VALIDATION_FAILED")
        self.calls += 1


@dataclass(frozen=True)
class ModelGateway:
    provider: Callable[..., Any] | None = None
    card: ModelCard | None = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_calls: int = DEFAULT_MAX_CALLS

    def __post_init__(self) -> None:
        if not 1 <= self.timeout_seconds <= 300 or not 1 <= self.max_calls <= DEFAULT_MAX_CALLS:
            raise ValueError("provider execution bounds are invalid")
        if self.provider is not None and self.card is None:
            raise ValueError("enabled provider requires a model card")

    def generate(self, request: Mapping[str, Any], context: Mapping[str, Any], *, max_calls: int) -> Any:
        if max_calls > self.max_calls:
            raise BrainError("VALIDATION_FAILED")
        return self.execute(
            request, context, sensitivity="normal", budget=ProviderCallBudget(max_calls=max_calls),
        )

    def execute(self, request: Mapping[str, Any], context: Mapping[str, Any], *,
                sensitivity: str, budget: ProviderCallBudget) -> Any:
        if self.provider is None or self.card is None:
            raise BrainError("TOOL_DENIED")
        if sensitivity not in _SENSITIVITY or _SENSITIVITY[sensitivity] > _SENSITIVITY[self.card.sensitivity]:
            raise BrainError("SENSITIVITY_DENIED")
        if self.card.allowed_context_keys and not set(context) <= set(self.card.allowed_context_keys):
            raise BrainError("VALIDATION_FAILED")
        import json
        encoded = json.dumps({"request": request, "context": context}, ensure_ascii=False, default=str)
        if len(encoded.encode("utf-8")) > self.card.max_context_bytes:
            raise BrainError("PAYLOAD_TOO_LARGE")
        if detect_secret(filename="provider-request.json", content_type="application/json", content=encoded).matched:
            raise BrainError("SECRET_REJECTED")
        budget.consume()
        payload = {
            "request": dict(request), "context": dict(context),
            "model": self.card.name, "model_version": self.card.version,
            "provider_id": self.card.provider_id, "tokenizer": self.card.tokenizer,
        }

        def call() -> Any:
            parameters = inspect.signature(self.provider).parameters
            if "timeout_seconds" in parameters:
                return self.provider(payload, timeout_seconds=self.timeout_seconds)
            return self.provider(payload)

        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="brain-provider")
        future = executor.submit(call)
        try:
            return future.result(timeout=self.timeout_seconds)
        except TimeoutError as error:
            future.cancel()
            raise BrainError("BRAIN_UNAVAILABLE") from error
        except BrainError:
            raise
        except Exception as error:
            raise BrainError("BRAIN_UNAVAILABLE") from error
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
