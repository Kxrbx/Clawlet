"""Optional Rust bridge for hybrid runtime acceleration."""

from __future__ import annotations

import hashlib
from typing import Tuple


def is_available() -> bool:
    try:
        import clawlet_rust_core  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def fast_hash(payload: str) -> str:
    """Compute fast stable hash. Uses Rust extension if available."""
    try:
        import clawlet_rust_core  # type: ignore

        return str(clawlet_rust_core.fast_hash(payload))
    except Exception:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_patch(patch: str) -> Tuple[bool, str]:
    """Validate patch format with Rust extension fallback."""
    try:
        import clawlet_rust_core  # type: ignore

        result = clawlet_rust_core.validate_patch(patch)
        if isinstance(result, tuple) and len(result) == 2:
            return bool(result[0]), str(result[1])
        return True, "ok"
    except Exception:
        if "@@" not in patch:
            return False, "Patch must include at least one unified diff hunk (@@ ...)"
        return True, "ok"
