"""Failure taxonomy and classification helpers for runtime reliability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover - optional dependency in some environments
    httpx = None  # type: ignore


@dataclass(slots=True)
class FailureInfo:
    code: str
    retryable: bool
    category: str

KNOWN_FAILURE_CODES = {
    "unknown_error",
    "timeout",
    "rate_limited",
    "network_error",
    "not_found",
    "validation_error",
    "policy_denied",
    "permission_denied",
    "process_failed",
    "tool_error",
    "provider_timeout",
    "provider_connect_error",
    "provider_read_error",
    "provider_request_error",
    "provider_rate_limited",
    "provider_server_error",
    "provider_client_error",
    "provider_http_error",
}


def classify_error_text(message: str | None) -> FailureInfo:
    text = (message or "").strip().lower()
    if not text:
        return FailureInfo(code="unknown_error", retryable=False, category="unknown")

    if "timed out" in text or "timeout" in text:
        return FailureInfo(code="timeout", retryable=True, category="transient")
    if "rate limit" in text or "429" in text:
        return FailureInfo(code="rate_limited", retryable=True, category="provider")
    if "network" in text or "connection" in text or "temporarily unavailable" in text:
        return FailureInfo(code="network_error", retryable=True, category="transient")
    if "not found" in text or "unknown tool" in text:
        return FailureInfo(code="not_found", retryable=False, category="tooling")
    if "invalid tool call" in text or "validation" in text:
        return FailureInfo(code="validation_error", retryable=False, category="input")
    if "requires explicit approval" in text or "is disabled" in text or "not allowed by runtime policy" in text:
        return FailureInfo(code="policy_denied", retryable=False, category="policy")
    if "permission" in text or "access denied" in text:
        return FailureInfo(code="permission_denied", retryable=False, category="security")
    if "exit code:" in text:
        return FailureInfo(code="process_failed", retryable=False, category="execution")

    return FailureInfo(code="tool_error", retryable=False, category="execution")


def classify_exception(exc: Exception) -> FailureInfo:
    if httpx is not None:
        if isinstance(exc, httpx.TimeoutException):
            return FailureInfo(code="provider_timeout", retryable=True, category="provider")
        if isinstance(exc, httpx.ConnectError):
            return FailureInfo(code="provider_connect_error", retryable=True, category="provider")
        if isinstance(exc, httpx.ReadError):
            return FailureInfo(code="provider_read_error", retryable=True, category="provider")
        if isinstance(exc, httpx.RequestError):
            return FailureInfo(code="provider_request_error", retryable=True, category="provider")
        if isinstance(exc, httpx.HTTPStatusError):
            status = _status_code(exc)
            if status == 429:
                return FailureInfo(code="provider_rate_limited", retryable=True, category="provider")
            if status is not None and status >= 500:
                return FailureInfo(code="provider_server_error", retryable=True, category="provider")
            if status is not None and status >= 400:
                return FailureInfo(code="provider_client_error", retryable=False, category="provider")
            return FailureInfo(code="provider_http_error", retryable=False, category="provider")

    return classify_error_text(str(exc))


def _status_code(exc: Exception) -> int | None:
    try:
        return int(getattr(exc.response, "status_code", None))
    except Exception:
        return None


def to_payload(info: FailureInfo) -> dict[str, Any]:
    return {"failure_code": info.code, "retryable": info.retryable, "failure_category": info.category}


def is_known_failure_code(code: str | None) -> bool:
    return bool(code) and str(code) in KNOWN_FAILURE_CODES
