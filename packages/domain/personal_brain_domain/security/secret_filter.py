"""Secret-like filename/type/content detection with value-free results.

FR-072/ER-05: secret and secret-like material is rejected before ordinary
persistence. The detection result never retains the matched value, a recoverable
fragment, or a credential hash; only the matched rule names and a boolean are
exposed so the exclusion record cannot leak private content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

_FILENAME_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ssh_private_key", re.compile(r"^id_(rsa|dsa|ecdsa|ed25519)$", re.IGNORECASE)),
    ("dotenv", re.compile(r"^\.env($|\.)")),
    ("keychain", re.compile(r"(^|[._-])(key|secret|token|credential|password)s?(\.|$)", re.IGNORECASE)),
    ("certificate_private", re.compile(r"\.(pem|key|pfx|p12|jks|keystore)$", re.IGNORECASE)),
)

_CONTENT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("api_key_literal", re.compile(r"(?i)\b(api[_-]?key|access[_-]?key)\s*[:=]\s*\S{8,}")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("password_literal", re.compile(r"(?i)\bpassword\s*[:=]\s*\S{8,}")),
    ("token_literal", re.compile(r"(?i)\b(token|client[_-]?secret)\s*[:=]\s*\S{8,}")),
)


@dataclass(frozen=True)
class SecretDetection:
    matched: bool
    rules: tuple[str, ...] = field(default_factory=tuple)
    # No content, no fragments, no hashes. Only matched rule names are stored.

    def __repr__(self) -> str:
        return f"SecretDetection(matched={self.matched}, rules={self.rules!r})"

    def rule_list(self) -> list[str]:
        return list(self.rules)


def detect_secret(
    *,
    filename: str,
    content_type: str | None = None,
    content: str | None = None,
    extra_rules: Iterable[re.Pattern[str]] = (),
) -> SecretDetection:
    """Return a value-free detection result for a filename/type/content trio."""
    matched_rules: list[str] = []
    for rule_name, pattern in _FILENAME_RULES:
        if pattern.search(filename):
            matched_rules.append(rule_name)
    for pattern in extra_rules:
        if content is not None and pattern.search(content):
            matched_rules.append("extra")
    if content is not None:
        for rule_name, pattern in _CONTENT_RULES:
            if pattern.search(content):
                matched_rules.append(rule_name)
    return SecretDetection(matched=bool(matched_rules), rules=tuple(dict.fromkeys(matched_rules)))
