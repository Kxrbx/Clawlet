"""Optional Rust bridge for hybrid runtime acceleration."""

from __future__ import annotations

import hashlib
import re
from typing import Optional, Tuple


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
        return _validate_patch_python(patch)


def execute_command_argv(
    argv: list[str],
    cwd: str,
    timeout_seconds: float,
) -> Optional[tuple[bool, int, str, str, str]]:
    """
    Execute command argv via Rust core when available.

    Returns:
      - tuple(success, returncode, stdout, stderr, error) if Rust path succeeded
      - None when Rust core is unavailable (caller should use Python fallback path)
    """
    try:
        import clawlet_rust_core  # type: ignore

        result = clawlet_rust_core.execute_command_argv(argv, cwd, float(timeout_seconds))
        if isinstance(result, tuple) and len(result) == 5:
            return (
                bool(result[0]),
                int(result[1]),
                str(result[2]),
                str(result[3]),
                str(result[4]),
            )
    except Exception:
        return None
    return None


def read_text_file(path: str) -> Optional[tuple[bool, str, str]]:
    """Read UTF-8 text file via Rust core when available."""
    try:
        import clawlet_rust_core  # type: ignore

        result = clawlet_rust_core.read_text_file(str(path))
        if isinstance(result, tuple) and len(result) == 3:
            return (bool(result[0]), str(result[1]), str(result[2]))
    except Exception:
        return None
    return None


def write_text_file(path: str, content: str) -> Optional[tuple[bool, int, str]]:
    """Write UTF-8 text file via Rust core when available."""
    try:
        import clawlet_rust_core  # type: ignore

        result = clawlet_rust_core.write_text_file(str(path), str(content))
        if isinstance(result, tuple) and len(result) == 3:
            return (bool(result[0]), int(result[1]), str(result[2]))
    except Exception:
        return None
    return None


def list_dir_entries(path: str) -> Optional[tuple[bool, list[tuple[str, bool]], str]]:
    """List directory entries via Rust core when available."""
    try:
        import clawlet_rust_core  # type: ignore

        result = clawlet_rust_core.list_dir_entries(str(path))
        if isinstance(result, tuple) and len(result) == 3:
            ok = bool(result[0])
            raw_entries = result[1] if isinstance(result[1], list) else []
            entries: list[tuple[str, bool]] = []
            for item in raw_entries:
                if isinstance(item, tuple) and len(item) == 2:
                    entries.append((str(item[0]), bool(item[1])))
            return (ok, entries, str(result[2]))
    except Exception:
        return None
    return None


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _validate_patch_python(patch: str) -> Tuple[bool, str]:
    if not patch or not patch.strip():
        return False, "Patch is empty"

    lines = patch.splitlines()
    saw_hunk = False
    in_hunk = False
    expected_old = 0
    expected_new = 0
    seen_old = 0
    seen_new = 0

    for line in lines:
        m = _HUNK_RE.match(line)
        if m:
            if in_hunk:
                if expected_old > 0 and seen_old != expected_old:
                    return False, f"Old-side hunk line count mismatch: expected {expected_old}, got {seen_old}"
                if expected_new > 0 and seen_new != expected_new:
                    return False, f"New-side hunk line count mismatch: expected {expected_new}, got {seen_new}"
            saw_hunk = True
            in_hunk = True
            expected_old = int(m.group(2) or "1")
            expected_new = int(m.group(4) or "1")
            seen_old = 0
            seen_new = 0
            continue

        if not in_hunk:
            continue

        if line.startswith(" "):
            seen_old += 1
            seen_new += 1
        elif line.startswith("-"):
            seen_old += 1
        elif line.startswith("+"):
            seen_new += 1
        elif line.startswith("\\ No newline"):
            pass
        elif line.startswith("--- ") or line.startswith("+++ "):
            pass
        else:
            return False, f"Unsupported patch line in hunk: {line}"

    if not saw_hunk:
        return False, "Patch must contain at least one unified diff hunk (@@ ...)"

    if expected_old > 0 and seen_old != expected_old:
        return False, f"Old-side hunk line count mismatch: expected {expected_old}, got {seen_old}"
    if expected_new > 0 and seen_new != expected_new:
        return False, f"New-side hunk line count mismatch: expected {expected_new}, got {seen_new}"

    return True, "ok"
