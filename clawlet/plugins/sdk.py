"""Stable plugin SDK v2 for custom Clawlet tool extensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from clawlet.tools.registry import BaseTool, ToolResult

SDK_VERSION = "2.0.0"


@dataclass(slots=True)
class ToolSpec:
    """Metadata describing a plugin tool contract."""

    name: str
    description: str
    sdk_version: str = SDK_VERSION
    capabilities: list[str] = field(default_factory=list)
    deprecates: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ToolInput:
    """Structured tool input payload."""

    arguments: dict[str, Any]
    run_id: str
    session_id: str
    workspace_path: str


@dataclass(slots=True)
class ToolOutput:
    """Structured tool output payload."""

    output: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolError:
    """Standardized plugin tool error payload."""

    code: str
    message: str
    retryable: bool = False


@dataclass(slots=True)
class ToolContext:
    """Execution context passed to plugin tools."""

    run_id: str
    session_id: str
    workspace_path: str
    channel: str = ""


class SupportsPluginExecute(Protocol):
    """Protocol for plugin tools."""

    async def execute_with_context(self, tool_input: ToolInput, context: ToolContext) -> ToolOutput:
        ...


class PluginTool(BaseTool):
    """Base class for plugin tools with stable SDK metadata."""

    spec: ToolSpec

    def __init__(self, spec: ToolSpec):
        self.spec = spec

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def description(self) -> str:
        return self.spec.description

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "additionalProperties": True,
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs) -> ToolResult:
        try:
            tool_input = ToolInput(
                arguments=kwargs,
                run_id=str(kwargs.pop("_run_id", "")),
                session_id=str(kwargs.pop("_session_id", "")),
                workspace_path=str(kwargs.pop("_workspace_path", "")),
            )
            context = ToolContext(
                run_id=tool_input.run_id,
                session_id=tool_input.session_id,
                workspace_path=tool_input.workspace_path,
            )
            output = await self.execute_with_context(tool_input, context)
            return ToolResult(success=True, output=output.output, data=output.data)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def execute_with_context(self, tool_input: ToolInput, context: ToolContext) -> ToolOutput:
        raise NotImplementedError


ExecutionMode = Literal["local", "remote"]
