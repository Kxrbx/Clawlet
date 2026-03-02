"""Remote-optional tool execution client for runtime v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from clawlet.runtime.types import ToolCallEnvelope
from clawlet.tools.registry import ToolResult

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    httpx = None  # type: ignore


@dataclass(slots=True)
class RemoteExecutionRequest:
    run_id: str
    session_id: str
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    execution_mode: str
    workspace_path: str
    timeout_seconds: float


class RemoteToolExecutor:
    """HTTP client for remote worker tool execution."""

    def __init__(
        self,
        endpoint: str,
        api_key: str = "",
        timeout_seconds: float = 60.0,
    ):
        self.endpoint = (endpoint or "").rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = max(1.0, float(timeout_seconds))

    async def execute(self, envelope: ToolCallEnvelope) -> ToolResult:
        if not self.endpoint:
            return ToolResult(success=False, output="", error="Remote endpoint is not configured")
        if httpx is None:
            return ToolResult(success=False, output="", error="httpx is unavailable for remote execution")

        payload = asdict(
            RemoteExecutionRequest(
                run_id=envelope.run_id,
                session_id=envelope.session_id,
                tool_call_id=envelope.tool_call_id,
                tool_name=envelope.tool_name,
                arguments=envelope.arguments,
                execution_mode=envelope.execution_mode,
                workspace_path=envelope.workspace_path,
                timeout_seconds=envelope.timeout_seconds,
            )
        )
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"

        url = f"{self.endpoint}/execute"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json() or {}
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Remote execution failed: {e}")

        return ToolResult(
            success=bool(data.get("success", False)),
            output=str(data.get("output") or ""),
            error=str(data.get("error") or "") or None,
            data=data.get("data"),
        )

    async def health(self) -> tuple[bool, str]:
        if not self.endpoint:
            return False, "Remote endpoint is not configured"
        if httpx is None:
            return False, "httpx is unavailable"
        url = f"{self.endpoint}/health"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
            return True, "ok"
        except Exception as e:
            return False, str(e)
