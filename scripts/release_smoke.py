from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "clawlet", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout + completed.stderr


def main() -> int:
    help_output = run("--help")
    if "clawlet" not in help_output.lower():
        raise SystemExit("CLI help output did not render correctly")

    workspace_dir = Path(tempfile.mkdtemp(prefix="clawlet-release-smoke-"))
    try:
        init_output = run("init", "--workspace", str(workspace_dir))
        if "Workspace ready" not in init_output:
            raise SystemExit("Workspace init did not complete successfully")

        required_files = [
            workspace_dir / "config.yaml",
            workspace_dir / "SOUL.md",
            workspace_dir / "USER.md",
            workspace_dir / "MEMORY.md",
            workspace_dir / "HEARTBEAT.md",
            workspace_dir / "tasks" / "QUEUE.md",
        ]
        missing = [str(path) for path in required_files if not path.exists()]
        if missing:
            raise SystemExit(f"Workspace init did not create expected files: {missing}")

        heartbeat_output = run("heartbeat", "status", "--workspace", str(workspace_dir))
        if "Heartbeat" not in heartbeat_output:
            raise SystemExit("Heartbeat status command did not render correctly")

        validate_output = run("validate", "--workspace", str(workspace_dir))
        if "valid" not in validate_output.lower():
            raise SystemExit("Validate command did not report a valid configuration")

    finally:
        shutil.rmtree(workspace_dir, ignore_errors=True)

    print("release smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
