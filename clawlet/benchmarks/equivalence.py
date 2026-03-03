"""Engine equivalence checks between Python and Rust execution paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from clawlet.benchmarks.async_utils import run_async as _run_async
from clawlet.runtime import rust_bridge
from clawlet.tools.files import ListDirTool, ReadFileTool, WriteFileTool
from clawlet.tools.shell import ShellTool


@dataclass(slots=True)
class EquivalenceResult:
    rust_available: bool
    shell_equivalent: bool
    file_equivalent: bool
    patch_equivalent: bool
    details: list[str]

    @property
    def passed(self) -> bool:
        return self.shell_equivalent and self.file_equivalent and self.patch_equivalent


def run_engine_equivalence_smokecheck(workspace: Path) -> EquivalenceResult:
    """
    Compare Python vs Rust behavior for critical execution primitives.

    When Rust extension is unavailable, this still validates Python fallback behavior
    and marks Rust-dependent checks as pass-by-fallback.
    """
    details: list[str] = []
    workspace.mkdir(parents=True, exist_ok=True)
    rust_available = rust_bridge.is_available()

    shell_ok = _check_shell_equivalence(workspace, rust_available, details)
    file_ok = _check_file_equivalence(workspace, rust_available, details)
    patch_ok = _check_patch_equivalence(rust_available, details)

    return EquivalenceResult(
        rust_available=rust_available,
        shell_equivalent=shell_ok,
        file_equivalent=file_ok,
        patch_equivalent=patch_ok,
        details=details,
    )


def _check_shell_equivalence(workspace: Path, rust_available: bool, details: list[str]) -> bool:
    try:
        with TemporaryDirectory(dir=str(workspace)) as td:
            td_path = Path(td)
            py_tool = ShellTool(workspace=td_path, use_rust_core=False)
            py_result = _run_async(py_tool.execute("echo clawlet-equivalence"))
            py_tuple = (py_result.success, py_result.output.strip(), py_result.error or "")

            if not rust_available:
                details.append("shell: rust unavailable; python fallback validated")
                return py_result.success

            rust_tool = ShellTool(workspace=td_path, use_rust_core=True)
            rust_result = _run_async(rust_tool.execute("echo clawlet-equivalence"))
            rust_tuple = (rust_result.success, rust_result.output.strip(), rust_result.error or "")

            if py_tuple != rust_tuple:
                details.append(f"shell mismatch: python={py_tuple} rust={rust_tuple}")
                return False

            details.append("shell: python/rust equivalent")
            return True
    except Exception as e:
        details.append(f"shell check failed: {e}")
        return False


def _check_patch_equivalence(rust_available: bool, details: list[str]) -> bool:
    valid_patch = (
        "--- a/demo.txt\n"
        "+++ b/demo.txt\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
    )
    invalid_patch = (
        "--- a/demo.txt\n"
        "+++ b/demo.txt\n"
        "@@ -1,2 +1,1 @@\n"
        "-old\n"
        "+new\n"
    )
    apply_patch = (
        "@@ -1,2 +1,2 @@\n"
        " alpha\n"
        "-beta\n"
        "+beta_done\n"
    )

    py_valid = rust_bridge._validate_patch_python(valid_patch)
    py_invalid = rust_bridge._validate_patch_python(invalid_patch)
    runtime_valid = rust_bridge.validate_patch(valid_patch)
    runtime_invalid = rust_bridge.validate_patch(invalid_patch)
    py_applied = _apply_patch_python("alpha\nbeta\n", apply_patch)
    runtime_apply = rust_bridge.apply_unified_patch("alpha\nbeta\n", apply_patch)

    if not rust_available:
        ok = py_valid == runtime_valid and py_invalid == runtime_invalid and runtime_apply is None
        if ok:
            details.append("patch: rust unavailable; python fallback parity validated")
        else:
            details.append(
                f"patch fallback mismatch: py_valid={py_valid} runtime_valid={runtime_valid} "
                f"py_invalid={py_invalid} runtime_invalid={runtime_invalid} "
                f"runtime_apply={runtime_apply}"
            )
        return ok

    # Rust is available: compare success/failure class and resulting content for apply path.
    if runtime_apply is None:
        details.append("patch mismatch: rust available but apply_unified_patch bridge returned None")
        return False

    ok = (
        (py_valid[0] == runtime_valid[0])
        and (py_invalid[0] == runtime_invalid[0])
        and runtime_apply[0]
        and (runtime_apply[1] == py_applied)
    )
    if ok:
        details.append("patch: python/rust equivalent")
    else:
        details.append(
            f"patch mismatch: py_valid={py_valid} rust_valid={runtime_valid} "
            f"py_invalid={py_invalid} rust_invalid={runtime_invalid} "
            f"py_applied={py_applied!r} rust_apply={runtime_apply}"
        )
    return ok


def _check_file_equivalence(workspace: Path, rust_available: bool, details: list[str]) -> bool:
    try:
        with TemporaryDirectory(dir=str(workspace)) as td:
            td_path = Path(td)
            target = td_path / "equivalence.txt"
            content = "hello-equivalence"

            py_writer = WriteFileTool(allowed_dir=td_path, use_rust_core=False)
            py_write = _run_async(py_writer.execute(target.name, content))
            if not py_write.success:
                details.append(f"file python write failed: {py_write.error}")
                return False

            py_reader = ReadFileTool(allowed_dir=td_path, use_rust_core=False)
            py_read = _run_async(py_reader.execute(target.name))
            py_list = _run_async(ListDirTool(allowed_dir=td_path, use_rust_core=False).execute("."))
            py_tuple = (py_read.success, py_read.output, py_list.success, py_list.output)

            if not rust_available:
                details.append("file: rust unavailable; python fallback validated")
                return py_read.success and py_list.success

            rust_read = _run_async(ReadFileTool(allowed_dir=td_path, use_rust_core=True).execute(target.name))
            rust_list = _run_async(ListDirTool(allowed_dir=td_path, use_rust_core=True).execute("."))
            rust_tuple = (rust_read.success, rust_read.output, rust_list.success, rust_list.output)

            if py_tuple != rust_tuple:
                details.append(f"file mismatch: python={py_tuple} rust={rust_tuple}")
                return False

            details.append("file: python/rust equivalent")
            return True
    except Exception as e:
        details.append(f"file check failed: {e}")
        return False


def _apply_patch_python(original: str, patch: str) -> str:
    src_lines = original.splitlines(keepends=True)
    hunk_re = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    out: list[str] = []
    src_idx = 0
    lines = patch.splitlines()
    i = 0

    while i < len(lines):
        m = hunk_re.match(lines[i])
        if not m:
            i += 1
            continue
        old_start = int(m.group(1)) - 1
        out.extend(src_lines[src_idx:old_start])
        src_idx = old_start
        i += 1

        while i < len(lines) and not lines[i].startswith("@@"):
            line = lines[i]
            if line.startswith("--- ") or line.startswith("+++ "):
                i += 1
                continue

            token = line[0] if line else " "
            body = line[1:] if line else ""
            if token == " ":
                expected = src_lines[src_idx].rstrip("\n")
                if expected != body:
                    raise ValueError("Patch context mismatch")
                out.append(src_lines[src_idx])
                src_idx += 1
            elif token == "-":
                expected = src_lines[src_idx].rstrip("\n")
                if expected != body:
                    raise ValueError("Patch removal mismatch")
                src_idx += 1
            elif token == "+":
                out.append(body + "\n")
            elif token == "\\":
                pass
            else:
                raise ValueError(f"Unsupported diff token: {token}")
            i += 1

    out.extend(src_lines[src_idx:])
    return "".join(out)
