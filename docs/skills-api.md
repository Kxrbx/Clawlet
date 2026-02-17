# Skills API Reference

This document provides technical documentation for developers working with the Skills system programmatically.

## Table of Contents

- [Overview](#overview)
- [Core Classes](#core-classes)
  - [SkillMetadata](#skillmetadata)
  - [ToolParameter](#toolparameter)
  - [ToolDefinition](#tooldefinition)
  - [BaseSkill](#baseskill)
  - [PlaceholderSkill](#placeholderskill)
- [SkillLoader](#skillloader)
- [SkillRegistry](#skillregistry)
- [ToolRegistry Integration](#toolregistry-integration)
- [Programmatic Skill Creation](#programmatic-skill-creation)
- [Error Handling](#error-handling)

---

## Overview

The Skills system is organized into three main modules:

| Module | Purpose |
|--------|---------|
| `clawlet.skills.base` | Core classes and data structures |
| `clawlet.skills.loader` | SKILL.md parsing and loading |
| `clawlet.skills.registry` | Skill management and discovery |

```python
from clawlet.skills import (
    SkillRegistry,
    SkillLoader,
    BaseSkill,
    SkillMetadata,
    ToolDefinition,
    ToolParameter,
)
```

---

## Core Classes

### SkillMetadata

Dataclass containing skill metadata parsed from SKILL.md frontmatter.

```python
from clawlet.skills.base import SkillMetadata

@dataclass
class SkillMetadata:
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = "unknown"
    requires: list[str] = field(default_factory=list)
    tools: list[ToolDefinition] = field(default_factory=list)
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Unique skill identifier |
| `version` | `str` | Semantic version string |
| `description` | `str` | Brief description |
| `author` | `str` | Author name |
| `requires` | `list[str]` | Required config keys |
| `tools` | `list[ToolDefinition]` | Tool definitions |

#### Example

```python
metadata = SkillMetadata(
    name="email",
    version="1.0.0",
    description="Send and manage emails",
    author="clawlet",
    requires=["smtp_server", "smtp_port"],
    tools=[...]
)
```

---

### ToolParameter

Definition of a single tool parameter with JSON Schema support.

```python
from clawlet.skills.base import ToolParameter

@dataclass
class ToolParameter:
    name: str
    type: str  # "string", "integer", "number", "boolean", "array", "object"
    description: Optional[str] = None
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[list[str]] = None
```

#### Methods

##### `to_json_schema() -> dict`

Converts the parameter to JSON Schema format.

```python
param = ToolParameter(
    name="visibility",
    type="string",
    description="Access level",
    required=False,
    default="public",
    enum=["public", "private"]
)

schema = param.to_json_schema()
# {
#     "type": "string",
#     "description": "Access level",
#     "default": "public",
#     "enum": ["public", "private"]
# }
```

#### Example

```python
# Required string parameter
to_param = ToolParameter(
    name="to",
    type="string",
    description="Recipient email address",
    required=True
)

# Optional integer with default
limit_param = ToolParameter(
    name="limit",
    type="integer",
    description="Maximum results",
    required=False,
    default=10
)
```

---

### ToolDefinition

Complete tool definition with OpenAI schema conversion.

```python
from clawlet.skills.base import ToolDefinition

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
```

#### Methods

##### `to_openai_schema() -> dict`

Converts to OpenAI function calling format.

```python
tool = ToolDefinition(
    name="send_email",
    description="Send an email",
    parameters=[
        ToolParameter(name="to", type="string", description="Recipient", required=True),
        ToolParameter(name="subject", type="string", description="Subject", required=True),
    ]
)

schema = tool.to_openai_schema()
# {
#     "type": "function",
#     "function": {
#         "name": "send_email",
#         "description": "Send an email",
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "to": {"type": "string", "description": "Recipient"},
#                 "subject": {"type": "string", "description": "Subject"}
#             },
#             "required": ["to", "subject"]
#         }
#     }
# }
```

##### `get_namespaced_name(skill_name: str) -> str`

Returns the namespaced tool name.

```python
tool = ToolDefinition(name="send_email", description="...")
tool.get_namespaced_name("email")  # "email_send_email"
```

---

### BaseSkill

Abstract base class for all skills. Extend this class to implement custom skill behavior.

```python
from clawlet.skills.base import BaseSkill, SkillMetadata
from clawlet.tools.registry import ToolResult

class BaseSkill(ABC):
    def __init__(self, metadata: SkillMetadata, skill_path: Optional[Path] = None):
        self._metadata = metadata
        self._skill_path = skill_path
        self._config: dict[str, Any] = {}
        self._enabled = True
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Skill name from metadata |
| `version` | `str` | Skill version |
| `description` | `str` | Skill description |
| `author` | `str` | Skill author |
| `requires` | `list[str]` | Required config keys |
| `tools` | `list[ToolDefinition]` | Tool definitions |
| `skill_path` | `Optional[Path]` | Path to skill directory |
| `enabled` | `bool` | Whether skill is enabled |
| `config` | `dict[str, Any]` | Skill configuration |

#### Methods

##### `configure(config: dict[str, Any]) -> None`

Configure the skill with provided settings.

```python
skill.configure({
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
})
```

##### `validate_requirements() -> tuple[bool, list[str]]`

Validate that all required configuration is present.

```python
is_valid, missing = skill.validate_requirements()
if not is_valid:
    print(f"Missing: {missing}")
```

##### `execute_tool(tool_name: str, **kwargs) -> ToolResult`

Execute a skill tool (async).

```python
result = await skill.execute_tool("send_email", to="user@example.com", subject="Hello")
if result.success:
    print(result.output)
else:
    print(result.error)
```

##### `_execute_tool_impl(tool_name: str, **kwargs) -> ToolResult`

Abstract method to implement tool execution. Override in subclasses.

```python
class MySkill(BaseSkill):
    async def _execute_tool_impl(self, tool_name: str, **kwargs) -> ToolResult:
        if tool_name == "my_tool":
            # Implement tool logic
            return ToolResult(success=True, output="Done")
        return ToolResult(success=False, error="Unknown tool")
```

##### `to_openai_tools() -> list[dict]`

Convert skill tools to OpenAI format with namespaced names.

```python
tools = skill.to_openai_tools()
# [{"type": "function", "function": {...}}, ...]
```

##### `get_instructions() -> str`

Get the skill instructions (markdown content). Override to provide custom instructions.

```python
instructions = skill.get_instructions()
```

#### Example Implementation

```python
from pathlib import Path
from clawlet.skills.base import BaseSkill, SkillMetadata, ToolDefinition, ToolParameter
from clawlet.tools.registry import ToolResult

class EmailSkill(BaseSkill):
    """Email skill with actual SMTP implementation."""
    
    def __init__(self, metadata: SkillMetadata, skill_path: Optional[Path] = None):
        super().__init__(metadata, skill_path)
        self._smtp_client = None
    
    async def _execute_tool_impl(self, tool_name: str, **kwargs) -> ToolResult:
        if tool_name == "send_email":
            return await self._send_email(**kwargs)
        return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
    
    async def _send_email(self, to: str, subject: str, body: str, **kwargs) -> ToolResult:
        try:
            # Implement SMTP sending
            import smtplib
            # ... SMTP logic ...
            return ToolResult(success=True, output=f"Email sent to {to}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

---

### PlaceholderSkill

A skill that doesn't implement actual functionality. Used for skills defined in SKILL.md without Python implementations.

```python
from clawlet.skills.base import PlaceholderSkill

class PlaceholderSkill(BaseSkill):
    def __init__(
        self, 
        metadata: SkillMetadata, 
        skill_path: Optional[Path] = None,
        instructions: str = ""
    ):
        super().__init__(metadata, skill_path)
        self._instructions = instructions
    
    async def _execute_tool_impl(self, tool_name: str, **kwargs) -> ToolResult:
        return ToolResult(
            success=False,
            error=f"Skill '{self.name}' tool '{tool_name}' is defined but not implemented."
        )
```

When tools are called on a PlaceholderSkill, it returns an error indicating the skill needs implementation.

---

## SkillLoader

Parser and loader for SKILL.md files.

```python
from clawlet.skills.loader import SkillLoader, SkillLoadError, discover_skills
```

### SkillLoadError

Exception raised when skill loading fails.

```python
class SkillLoadError(Exception):
    pass
```

### SkillLoader Class

#### Class Methods

##### `parse_skill_md(content: str) -> tuple[dict, str]`

Parse SKILL.md content into frontmatter and markdown.

```python
content = """---
name: email
version: "1.0.0"
---

# Email Skill
Instructions...
"""

frontmatter, markdown = SkillLoader.parse_skill_md(content)
# frontmatter = {"name": "email", "version": "1.0.0"}
# markdown = "# Email Skill\nInstructions..."
```

##### `parse_tool_parameter(param_data: dict) -> ToolParameter`

Parse a tool parameter from frontmatter data.

```python
param_data = {
    "name": "to",
    "type": "string",
    "description": "Recipient",
    "required": True
}
param = SkillLoader.parse_tool_parameter(param_data)
```

##### `parse_tool_definition(tool_data: dict) -> ToolDefinition`

Parse a tool definition from frontmatter.

```python
tool_data = {
    "name": "send_email",
    "description": "Send an email",
    "parameters": [...]
}
tool = SkillLoader.parse_tool_definition(tool_data)
```

##### `parse_metadata(frontmatter: dict) -> SkillMetadata`

Parse skill metadata from frontmatter.

```python
metadata = SkillLoader.parse_metadata(frontmatter)
```

##### `load_from_file(skill_md_path: Path) -> BaseSkill`

Load a skill from a SKILL.md file.

```python
from pathlib import Path

skill = SkillLoader.load_from_file(Path("~/.clawlet/skills/email/SKILL.md"))
print(skill.name)  # "email"
```

##### `load_from_directory(skill_dir: Path) -> Optional[BaseSkill]`

Load a skill from a directory containing SKILL.md.

```python
skill = SkillLoader.load_from_directory(Path("~/.clawlet/skills/email"))
```

### discover_skills Function

Discover and load all skills in a directory.

```python
from pathlib import Path
from clawlet.skills.loader import discover_skills

skills = discover_skills(Path("~/.clawlet/skills"))
for skill in skills:
    print(f"Found: {skill.name}")
```

---

## SkillRegistry

Central registry for managing skills.

```python
from clawlet.skills.registry import SkillRegistry
from clawlet.tools.registry import ToolRegistry
```

### Constructor

```python
registry = SkillRegistry(
    tool_registry=tool_registry,  # Optional ToolRegistry
    config={"email": {"smtp_server": "..."}},  # Optional config
)
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `skills` | `dict[str, BaseSkill]` | All registered skills |

### Methods

#### Directory Loading

##### `add_skill_directory(directory: Path) -> int`

Add a directory to search for skills. Returns count of loaded skills.

```python
count = registry.add_skill_directory(Path("~/.clawlet/skills"))
print(f"Loaded {count} skills")
```

##### `load_from_directories(directories: list[Path]) -> int`

Load skills from multiple directories (in priority order).

```python
total = registry.load_from_directories([
    Path("~/.clawlet/skills"),
    Path("./skills"),
])
```

##### `load_bundled_skills() -> int`

Load bundled skills shipped with Clawlet.

```python
count = registry.load_bundled_skills()
```

#### Registration

##### `register(skill: BaseSkill) -> None`

Manually register a skill.

```python
registry.register(my_skill)
```

##### `unregister(name: str) -> None`

Unregister a skill by name.

```python
registry.unregister("email")
```

#### Access

##### `get(name: str) -> Optional[BaseSkill]`

Get a skill by name.

```python
skill = registry.get("email")
if skill:
    print(skill.description)
```

##### `all_skills() -> list[BaseSkill]`

Get all registered skills.

```python
for skill in registry.all_skills():
    print(f"{skill.name}: {skill.description}")
```

##### `enabled_skills() -> list[BaseSkill]`

Get all enabled skills.

```python
for skill in registry.enabled_skills():
    print(skill.name)
```

#### Enable/Disable

##### `disable_skill(name: str) -> None`

Disable a skill by name.

```python
registry.disable_skill("email")
```

##### `enable_skill(name: str) -> None`

Enable a previously disabled skill.

```python
registry.enable_skill("email")
```

#### Configuration

##### `configure_skill(name: str, config: dict[str, Any]) -> bool`

Configure a specific skill.

```python
success = registry.configure_skill("email", {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
})
```

##### `configure_all(config: dict[str, Any]) -> None`

Configure all skills with nested config.

```python
registry.configure_all({
    "email": {
        "smtp_server": "smtp.gmail.com",
    },
    "calendar": {
        "provider": "google",
    },
})
```

#### Tools

##### `get_all_tools() -> list[ToolDefinition]`

Get all tool definitions from enabled skills.

```python
tools = registry.get_all_tools()
for tool in tools:
    print(tool.name)
```

##### `to_openai_tools() -> list[dict]`

Get all tools in OpenAI format.

```python
tools = registry.to_openai_tools()
# Pass to LLM API...
```

##### `register_tools_with_registry() -> int`

Register all skill tools with the ToolRegistry. Returns count registered.

```python
count = registry.register_tools_with_registry()
print(f"Registered {count} tools")
```

##### `execute_tool(namespaced_name: str, **kwargs) -> ToolResult`

Execute a skill tool by namespaced name (async).

```python
result = await registry.execute_tool(
    "email_send_email",
    to="user@example.com",
    subject="Hello",
    body="World"
)
```

#### Instructions

##### `get_skill_instructions() -> dict[str, str]`

Get instructions for all enabled skills.

```python
instructions = registry.get_skill_instructions()
for name, content in instructions.items():
    print(f"=== {name} ===\n{content}")
```

#### Validation

##### `validate_all_requirements() -> dict[str, list[str]]`

Validate requirements for all skills. Returns dict of skill names to missing requirements.

```python
missing = registry.validate_all_requirements()
if missing:
    for skill_name, reqs in missing.items():
        print(f"{skill_name} missing: {reqs}")
```

---

## ToolRegistry Integration

Skills integrate with the ToolRegistry for unified tool management.

### Setup

```python
from clawlet.tools.registry import ToolRegistry
from clawlet.skills.registry import SkillRegistry

# Create tool registry
tool_registry = ToolRegistry()

# Create skill registry with tool registry
skill_registry = SkillRegistry(tool_registry=tool_registry)

# Load skills
skill_registry.load_bundled_skills()
skill_registry.add_skill_directory(Path("~/.clawlet/skills"))

# Register skill tools with tool registry
skill_registry.register_tools_with_registry()
```

### Dynamic Tool Wrapper

When tools are registered, a dynamic wrapper class is created:

```python
class SkillTool:
    """Dynamic tool wrapper for skill tools."""
    
    @property
    def name(self) -> str:
        return self._ns_name  # Namespaced name
    
    @property
    def description(self) -> str:
        return self._tool_def.description
    
    @property
    def parameters_schema(self) -> dict:
        return self._tool_def.to_openai_schema()["function"]["parameters"]
    
    async def execute(self, **kwargs) -> ToolResult:
        return await self._skill.execute_tool(self._tool_def.name, **kwargs)
```

---

## Programmatic Skill Creation

### Creating Skills from Code

```python
from clawlet.skills.base import BaseSkill, SkillMetadata, ToolDefinition, ToolParameter
from clawlet.skills.registry import SkillRegistry
from clawlet.tools.registry import ToolResult

class WeatherSkill(BaseSkill):
    """Weather skill implementation."""
    
    async def _execute_tool_impl(self, tool_name: str, **kwargs) -> ToolResult:
        if tool_name == "get_weather":
            location = kwargs.get("location")
            # Call weather API...
            return ToolResult(
                success=True,
                output=f"Weather for {location}: Sunny, 22°C"
            )
        return ToolResult(success=False, error=f"Unknown tool: {tool_name}")

# Create metadata
metadata = SkillMetadata(
    name="weather",
    version="1.0.0",
    description="Get weather information",
    author="developer",
    requires=["weather_api_key"],
    tools=[
        ToolDefinition(
            name="get_weather",
            description="Get current weather",
            parameters=[
                ToolParameter(
                    name="location",
                    type="string",
                    description="City name",
                    required=True
                )
            ]
        )
    ]
)

# Create skill instance
weather_skill = WeatherSkill(metadata)

# Configure and register
weather_skill.configure({"weather_api_key": "your-key"})

registry = SkillRegistry()
registry.register(weather_skill)
```

### Loading from SKILL.md

```python
from pathlib import Path
from clawlet.skills.loader import SkillLoader

# Load from file
skill = SkillLoader.load_from_file(Path("skills/weather/SKILL.md"))

# Or from directory
skill = SkillLoader.load_from_directory(Path("skills/weather"))
```

### Creating Placeholder Skills

```python
from clawlet.skills.base import PlaceholderSkill

# Create from parsed data
skill = PlaceholderSkill(
    metadata=metadata,
    skill_path=Path("skills/weather"),
    instructions="# Weather Skill\n\nInstructions..."
)
```

---

## Error Handling

### SkillLoadError

Raised when SKILL.md parsing fails.

```python
from clawlet.skills.loader import SkillLoader, SkillLoadError

try:
    skill = SkillLoader.load_from_file(Path("skills/broken/SKILL.md"))
except SkillLoadError as e:
    print(f"Failed to load skill: {e}")
```

Common causes:
- Missing YAML frontmatter
- Invalid YAML syntax
- Missing required fields

### ToolResult Errors

Tools return errors via ToolResult:

```python
result = await skill.execute_tool("send_email", to="test@example.com")

if not result.success:
    print(f"Error: {result.error}")
```

Common error scenarios:
- Missing required parameters
- Tool not found in skill
- Skill not implemented (PlaceholderSkill)
- Configuration missing

### Validation Errors

Check requirements before using skills:

```python
is_valid, missing = skill.validate_requirements()
if not is_valid:
    print(f"Cannot use skill: missing {missing}")
    # Handle missing configuration
```

---

## Complete Example

```python
import asyncio
from pathlib import Path
from clawlet.skills import SkillRegistry, SkillLoader
from clawlet.tools.registry import ToolRegistry

async def main():
    # Create registries
    tool_registry = ToolRegistry()
    skill_registry = SkillRegistry(tool_registry=tool_registry)
    
    # Load skills
    skill_registry.load_bundled_skills()
    skill_registry.add_skill_directory(Path("~/.clawlet/skills"))
    
    # Configure skills
    skill_registry.configure_all({
        "email": {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "user@gmail.com",
            "smtp_password": "app-password",
        }
    })
    
    # Validate
    missing = skill_registry.validate_all_requirements()
    if missing:
        print(f"Warning: Missing configuration: {missing}")
    
    # Register tools
    count = skill_registry.register_tools_with_registry()
    print(f"Registered {count} tools")
    
    # Get OpenAI tools for LLM
    tools = skill_registry.to_openai_tools()
    print(f"Available tools: {[t['function']['name'] for t in tools]}")
    
    # Execute a tool
    result = await skill_registry.execute_tool(
        "email_send_email",
        to="recipient@example.com",
        subject="Hello",
        body="This is a test email."
    )
    
    if result.success:
        print(f"Success: {result.output}")
    else:
        print(f"Failed: {result.error}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## See Also

- [Skills Documentation](skills.md) - User guide for creating skills
- [Tool Registry](../clawlet/tools/registry.py) - Tool management implementation
- [Bundled Skills](../clawlet/skills/bundled/) - Example skill implementations