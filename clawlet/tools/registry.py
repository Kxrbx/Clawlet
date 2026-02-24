"""
Tool registry and base tool interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, Tuple, Dict, Union
import json
import time
from collections import defaultdict

from loguru import logger

from clawlet.exceptions import ValidationError, validate_not_empty, validate_type


class RateLimiter:
    """Simple rate limiter for tool execution."""
    
    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: dict[str, list[float]] = defaultdict(list)
    
    def check(self, key: str) -> tuple[bool, str]:
        """Check if a key is within rate limits."""
        now = time.time()
        # Clean old calls outside the window
        self._calls[key] = [t for t in self._calls[key] if now - t < self.window_seconds]
        
        if len(self._calls[key]) >= self.max_calls:
            return False, f"Rate limit exceeded: {self.max_calls} calls per {self.window_seconds}s"
        
        self._calls[key].append(now)
        return True, ""
    
    def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        if key in self._calls:
            del self._calls[key]


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    output: str
    error: Optional[str] = None
    data: Any = None


class BaseTool(ABC):
    """
    Base class for all tools.
    
    Tools are capabilities the agent can use to interact with the world.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (used by LLM to call it)."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description (shown to LLM)."""
        pass
    
    @property
    def parameters_schema(self) -> dict:
        """JSON schema for tool parameters."""
        return {}
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass
    
    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            }
        }


class ToolRegistry:
    """Registry for all available tools."""
    
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._rate_limiter = RateLimiter(max_calls=10, window_seconds=60.0)
        logger.info("ToolRegistry initialized")
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")
    
    def set_rate_limit(self, max_calls: int, window_seconds: float = 60.0) -> None:
        """Configure rate limiting for tool execution."""
        self._rate_limiter = RateLimiter(max_calls=max_calls, window_seconds=window_seconds)
        logger.info(f"Rate limit set: {max_calls} calls per {window_seconds}s")
    
    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def all_tools(self) -> list[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def to_openai_tools(self) -> list[dict]:
        """Get all tools in OpenAI format."""
        return [tool.to_openai_schema() for tool in self._tools.values()]
    
    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool not found: {name}"
            )
        
        # Check rate limit
        is_allowed, error_msg = self._rate_limiter.check(name)
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for tool {name}")
            return ToolResult(
                success=False,
                output="",
                error=error_msg
            )
        
        try:
            result = await tool.execute(**kwargs)
            return result
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


# Tool name validation
TOOL_NAME_MAX_LENGTH = 64


def validate_tool_params(
    tool_name: str,
    params: Optional[Dict[str, Any]] = None,
    schema: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validate tool execution parameters.
    
    Args:
        tool_name: Name of the tool to execute
        params: Parameters passed to the tool
        schema: JSON schema defining expected parameters
        
    Returns:
        Tuple of (is_valid, error_message, sanitized_params)
    """
    sanitized = {}
    errors = []
    
    # Validate tool name (critical)
    is_valid, error_msg = validate_not_empty(tool_name, "tool_name", is_critical=True)
    if not is_valid:
        errors.append(error_msg)
    else:
        # Sanitize tool name
        sanitized_name = tool_name.strip()
        if len(sanitized_name) > TOOL_NAME_MAX_LENGTH:
            errors.append(f"tool_name exceeds maximum length of {TOOL_NAME_MAX_LENGTH}")
        elif not sanitized_name.replace("_", "").replace("-", "").isalnum():
            errors.append("tool_name contains invalid characters")
        else:
            sanitized["tool_name"] = sanitized_name
    
    # Initialize params as empty dict if None
    if params is None:
        params = {}
    
    # Validate params is a dict
    if not isinstance(params, dict):
        errors.append("params must be a dictionary")
        return False, "; ".join(errors), {}
    
    # If we have a schema, validate against it
    if schema and errors == []:
        # Check required parameters
        required = schema.get("required", [])
        for req_param in required:
            if req_param not in params:
                errors.append(f"Missing required parameter: {req_param}")
        
        # Validate parameter types
        properties = schema.get("properties", {})
        for param_name, param_value in params.items():
            if param_name in properties:
                expected_type = properties[param_name].get("type")
                if expected_type:
                    # Map JSON schema types to Python types
                    type_mapping = {
                        "string": str,
                        "integer": int,
                        "number": (int, float),
                        "boolean": bool,
                        "array": list,
                        "object": dict,
                    }
                    expected_python_type = type_mapping.get(expected_type)
                    if expected_python_type and not isinstance(param_value, expected_python_type):
                        # Allow int for number type
                        if expected_type == "number" and isinstance(param_value, int):
                            continue
                        errors.append(
                            f"Parameter '{param_name}' must be of type {expected_type}, "
                            f"got {type(param_value).__name__}"
                        )
                    
                    # Check enum constraints
                    enum_values = properties[param_name].get("enum")
                    if enum_values and param_value not in enum_values:
                        errors.append(
                            f"Parameter '{param_name}' must be one of: {enum_values}"
                        )
                    
                    # Check string length constraints
                    if expected_type == "string" and isinstance(param_value, str):
                        min_length = properties[param_name].get("minLength", 0)
                        max_length = properties[param_name].get("maxLength")
                        if len(param_value) < min_length:
                            errors.append(
                                f"Parameter '{param_name}' must be at least {min_length} characters"
                            )
                        if max_length and len(param_value) > max_length:
                            errors.append(
                                f"Parameter '{param_name}' must be at most {max_length} characters"
                            )
    
    # Add sanitized params
    if errors == []:
        sanitized["params"] = params
    
    if errors:
        error_message = "; ".join(errors)
        logger.warning(f"Tool parameter validation failed for '{tool_name}': {error_message}")
        return False, error_message, {}
    
    return True, "", sanitized
