"""Central best-effort redaction for errors and operational logs."""
from __future__ import annotations

import re
from collections.abc import Iterable


_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+|bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
        r"\1[REDACTED]",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "sk-[REDACTED]"),
    (
        re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s,;]+)"),
        r"\1=[REDACTED]",
    ),
    # JWT-looking values are credentials even when a surrounding label is absent.
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "[JWT_REDACTED]"),
    # Remove credentials embedded in any URI-style connection string while
    # preserving only its scheme and destination. Database URLs commonly use
    # schemes such as ``postgresql+psycopg://`` rather than http(s).
    (
        re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^/@\s:]+:[^/@\s]+@"),
        r"\1[REDACTED]@",
    ),
)


def redact_sensitive(value: object, secrets: Iterable[str] = ()) -> str:
    text = str(value or "")
    for secret in secrets:
        secret = str(secret or "")
        if secret and len(secret) >= 6:
            text = text.replace(secret, "[REDACTED]")
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
