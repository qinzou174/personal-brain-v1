"""Fail-closed, environment-only non-secret configuration for the Brain server.

Secret *values* live in mounted files, not environment variables or project files.
Call ``read_secret_file`` at the narrow integration boundary; never log its result.
"""

from __future__ import annotations

import os
import stat
from ipaddress import IPv4Address
from pathlib import Path
from typing import Self
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BRAIN_",
        case_sensitive=False,
        extra="forbid",
        env_file=None,
        frozen=True,
    )

    environment: str = "development"
    bind_host: IPv4Address = IPv4Address("127.0.0.1")
    published_host: IPv4Address | None = None
    containerized: bool = False
    bind_port: int = Field(default=18081, ge=1024, le=65535)
    data_root: Path
    database_dsn_file: Path = Field(repr=False, exclude=True)
    token_pepper_file: Path = Field(repr=False, exclude=True)
    default_timezone: str = "Asia/Shanghai"
    default_currency: str = "CNY"
    external_models_enabled: bool = False
    model_api_key_file: Path | None = Field(default=None, repr=False, exclude=True)
    chat_model_base_url: str = "https://ark.cn-beijing.volces.com/api/coding"
    chat_model_name: str = "deepseek-v4.1-flash"
    embedding_base_url: str = "https://ark.cn-beijing.volces.com/api/coding/v3"
    embedding_model_name: str = "doubao-embedding-vision"
    embedding_dimensions: int = Field(default=1024, ge=1, le=4096)
    model_proxy_socket: Path | None = None
    # Background LLM derivation (extraction/digest) is bounded by a per-local-day
    # job budget instead of a per-call cap, so the backend can stay "alive"
    # without unbounded cost.  Exceeding it degrades to rules only, never blocks
    # canonical writes.
    llm_daily_quota: int = Field(default=200, ge=1, le=10000)

    @field_validator("data_root", "database_dsn_file", "token_pepper_file", "model_api_key_file", "model_proxy_socket")
    @classmethod
    def require_absolute_path(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        if not value.is_absolute() or ".." in value.parts:
            raise ValueError("configuration path must be absolute and normalized")
        return value

    @model_validator(mode="after")
    def require_safe_bind(self) -> Self:
        approved_lan = IPv4Address("192.168.10.7")
        if self.bind_host.is_multicast:
            raise ValueError("Brain must not bind to a multicast address")
        if self.bind_host.is_unspecified and not (
            self.environment == "production"
            and self.containerized
            and self.published_host == approved_lan
        ):
            raise ValueError("all-interface bind requires the approved container publish boundary")
        if self.environment == "production":
            external_host = self.published_host or self.bind_host
            if external_host != approved_lan:
                raise ValueError("production publish differs from the approved LAN endpoint")
            if self.containerized and not self.bind_host.is_unspecified:
                raise ValueError("containerized production must use an internal all-interface listener")
            if not self.containerized and self.bind_host != approved_lan:
                raise ValueError("non-container production bind differs from the approved LAN endpoint")
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("unsupported environment")
        if len(self.default_currency) != 3 or not self.default_currency.isupper():
            raise ValueError("default currency must be an uppercase ISO-4217 code")
        if self.external_models_enabled:
            if self.model_api_key_file is None:
                raise ValueError("external models require a mounted API key file")
            for url in (self.chat_model_base_url, self.embedding_base_url):
                parsed = urlparse(url)
                if (parsed.scheme, parsed.hostname, parsed.port) != (
                    "https", "ark.cn-beijing.volces.com", None,
                ):
                    raise ValueError("external model endpoint is not owner-approved")
            if not self.chat_model_name or not self.embedding_model_name:
                raise ValueError("external model identity is incomplete")
        return self

    def safe_summary(self) -> dict[str, str | int | bool]:
        """Allow-listed operational diagnostics without paths or secret material."""
        return {
            "environment": self.environment,
            "bind_host": str(self.bind_host),
            "published_host": str(self.published_host) if self.published_host else "",
            "containerized": self.containerized,
            "bind_port": self.bind_port,
            "default_timezone": self.default_timezone,
            "default_currency": self.default_currency,
            "external_models_enabled": self.external_models_enabled,
            "chat_model_name": self.chat_model_name if self.external_models_enabled else "disabled",
            "embedding_model_name": self.embedding_model_name if self.external_models_enabled else "disabled",
            "embedding_dimensions": self.embedding_dimensions if self.external_models_enabled else 0,
        }


def read_secret_file(path: Path, *, max_bytes: int = 8192) -> SecretStr:
    """Load one mounted secret without including its content in errors or reprs."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("invalid secret file path")
    try:
        if path.is_symlink():
            raise ValueError("secret file must not be a symlink")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size == 0 or info.st_size > max_bytes:
                raise ValueError("secret file has invalid type or size")
            if os.name == "posix" and info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                broad = info.st_mode & (stat.S_IRWXG | stat.S_IRWXO)
                readonly_secret_mount = (
                    path.parent == Path("/run/secrets")
                    and broad & ~(stat.S_IRGRP | stat.S_IROTH) == 0
                    and bool(os.statvfs(path).f_flag & getattr(os, "ST_RDONLY", 1))
                )
                if not readonly_secret_mount:
                    raise ValueError("secret file permissions are too broad")
            content = stream.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise ValueError("secret file has invalid size")
            value = content.decode("utf-8").strip()
    except OSError:
        raise ValueError("secret file unavailable") from None
    except UnicodeError:
        raise ValueError("secret file is not UTF-8") from None
    if not value:
        raise ValueError("secret file is empty")
    return SecretStr(value)
