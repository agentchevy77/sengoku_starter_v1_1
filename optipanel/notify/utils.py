from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_SYMBOL_PLACEHOLDER = "__INVALID_SYMBOL__"
_SYMBOL_MAX_LENGTH = 48
_ALLOWED_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9._:/@+\-^]+$")
_ALLOWED_PREFIX_PATTERN = re.compile(r"^[A-Z0-9._:/@+\-^]+")
_SEV_RANK = {"high": 3, "medium": 2, "low": 1, "info": 1}


def invalid_symbol_token(tag: str, source: str) -> str:
    digest_source = source.encode("utf-8", "ignore") or tag.upper().encode("ascii")
    digest = hashlib.sha1(digest_source).hexdigest().upper()
    cleaned_tag = tag.upper()
    return f"{_SYMBOL_PLACEHOLDER}-{cleaned_tag}-{digest[:6]}"


def normalize_symbol(raw: Any) -> tuple[str, str | None]:
    if raw is None:
        return invalid_symbol_token("missing", ""), "missing"

    raw_str = str(raw)
    candidate = raw_str.strip()
    trimmed = candidate != raw_str

    if not candidate:
        return invalid_symbol_token("empty", ""), "empty"

    canonical = candidate.upper()
    if len(canonical) > _SYMBOL_MAX_LENGTH:
        return invalid_symbol_token("toolong", canonical), "too_long"

    if _ALLOWED_SYMBOL_PATTERN.fullmatch(canonical):
        return canonical, "whitespace" if trimmed else None

    prefix_match = _ALLOWED_PREFIX_PATTERN.match(canonical)
    if prefix_match:
        prefix = prefix_match.group(0)
        remainder = canonical[len(prefix) :]
        if prefix and not any(ch.isalnum() for ch in remainder):
            return prefix, "invalid_suffix"

    return invalid_symbol_token("badchar", canonical), "invalid_chars"


def normalize_severity(severity: Any) -> str:
    if severity is None or severity == "":
        return "info"

    try:
        severity_str = str(severity).strip().lower()
        if severity_str in _SEV_RANK:
            return severity_str
        logger.debug(
            "notify.utils.normalize_severity: unknown severity=%r, defaulting to 'info'",
            severity,
        )
        return "info"
    except Exception:
        logger.exception("notify.utils.normalize_severity: conversion failed for %r", severity)
        return "info"


def severity_rank(value: Any) -> int:
    return _SEV_RANK.get(str(value).lower(), 1)
