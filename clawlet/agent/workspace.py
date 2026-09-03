"""
Workspace management for multi-agent support.

Each workspace is an isolated environment with its own:
- Configuration (config.yaml)
- Identity files (SOUL.md, USER.md, MEMORY.md, HEARTBEAT.md)
- Memory database
- Tool registry with workspace-specific allowed directories
- Skill configuration
"""

import asyncio
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import yaml
from loguru import logger

from clawlet.config import Config, load_config
from clawlet.agent.identity import Identity, IdentityLoader
from clawlet.workspace_layout import get_workspace_layout

if TYPE_CHECKING:
    from clawlet.agent.loop import AgentLoop
    from clawlet.bus.queue import MessageBus


# Default identity file templates
DEFAULT_SOUL_MD = """# Who I Am

## Name
{agent_name}

## Description
I am an AI assistant helping {user_name} with their tasks and questions.

## Personality
- Helpful and friendly
- Honest and direct
- Curious and eager to learn
- Respectful of boundaries

## Capabilities
- Answer questions and provide information
- Help with planning and organization
- Remember important details about {user_name}
- Execute tasks using available tools
"""

DEFAULT_USER_MD = """# Who You Help

## Name
{user_name}

## What to call you
{user_name}

## Timezone
UTC

## Preferences
- Communication style: Clear and concise
- Level of detail: Balanced

## Notes
Add notes about yourself here to help me assist you better.
"""

DEFAULT_MEMORY_MD = """# Memories

This file stores important memories and context.

## Key Information

<!-- Add important facts to remember here -->

## Recent Interactions

<!-- Recent conversation highlights will be noted here -->
"""

DEFAULT_HEARTBEAT_MD = """# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.
"""


@dataclass
class WorkspaceStatus:
    """Status of a workspace."""

    name: str
    path: Path
    exists: bool
    has_config: bool
    has_identity: bool
    is_running: bool = False


class Workspace:
    """
    Isolated agent workspace with its own configuration.

    Each workspace has:
    - Separate configuration file
    - Separate identity files (SOUL.md, USER.md, MEMORY.md)
    - Separate memory database
    - Separate tool registry

    Example:
        workspace = Workspace("personal", Path("./workspaces/personal"))
        await workspace.start(bus, provider)
        # ... use workspace
        await workspace.stop()
    """

    def __init__(self, name: str, path: Path):
        """
        Initialize a workspace.

        Args:
            name: Workspace name (used as agent_id)
            path: Path to workspace directory
        """
        self.name = name
        self.path = path.expanduser().resolve()
        self.layout = get_workspace_layout(self.path)

        self.config: Optional[Config] = None
        self.identity: Optional[Identity] = None
        self.agent: Optional["AgentLoop"] = None
        self._running = False

    @property
    def config_path(self) -> Path:
        """Path to workspace config file."""
        return self.layout.config_path

    @property
    def soul_path(self) -> Path:
        """Path to SOUL.md."""
        return self.layout.soul_path

    @property
    def user_path(self) -> Path:
        """Path to USER.md."""
        return self.layout.user_path

    @property
    def memory_path(self) -> Path:
        """Path to MEMORY.md."""
        return self.layout.memory_markdown_path

    @property
    def heartbeat_path(self) -> Path:
        """Path to HEARTBEAT.md."""
        return self.layout.heartbeat_path

    @property
    def db_path(self) -> Path:
        """Path to workspace database."""
        return self.path / "memory.db"

    def exists(self) -> bool:
        """Check if workspace directory exists."""
        return self.path.exists()

    def has_config(self) -> bool:
        """Check if workspace has a config file."""
        return self.config_path.exists()

    def has_identity_files(self) -> bool:
        """Check if workspace has identity files."""
        return self.soul_path.exists() and self.user_path.exists()

    def create(
        self,
        agent_name: Optional[str] = None,
        user_name: Optional[str] = None,
        template_config: Optional[Config] = None,
    ) -> None:
        """
        Create the workspace directory and files.

        Args:
            agent_name: Name for the agent (defaults to workspace name)
            user_name: Name for the user (defaults to "User")
            template_config: Optional config to use as template
        """
        agent_name = agent_name or self.name.capitalize()
        user_name = user_name or "User"

        # Create directory
        self.path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created workspace directory: {self.path}")

        # Create config.yaml
        if template_config:
            # Use template config
            self.config = template_config
            self.config.save(self.config_path)
        else:
            # Create minimal config that inherits from parent
            self._create_default_config()

        # Create identity files
        self._create_identity_files(agent_name, user_name)

        logger.info(f"Workspace '{self.name}' created at {self.path}")

    def _create_default_config(self) -> None:
        """Create a default config.yaml for the workspace."""
        # Create a minimal config that can inherit from parent
        config_data = {
            "agent": {
                "max_iterations": 50,
                "context_window": 20,
                "temperature": 0.7,
                "max_history": 100,
            },
            "skills": {
                "enabled": True,
                "directories": ["./.skills/installed", "./skills"],
            },
        }

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False)

        logger.debug(f"Created default config at {self.config_path}")

    def _create_identity_files(self, agent_name: str, user_name: str) -> None:
        """Create default identity files."""
        # SOUL.md
        if not self.soul_path.exists():
            self.soul_path.write_text(
                DEFAULT_SOUL_MD.format(agent_name=agent_name, user_name=user_name),
                encoding="utf-8",
            )
            logger.debug(f"Created SOUL.md at {self.soul_path}")

        # USER.md
        if not self.user_path.exists():
            self.user_path.write_text(
                DEFAULT_USER_MD.format(user_name=user_name), encoding="utf-8"
            )
            logger.debug(f"Created USER.md at {self.user_path}")

        # MEMORY.md
        if not self.memory_path.exists():
            self.memory_path.write_text(DEFAULT_MEMORY_MD, encoding="utf-8")
            logger.debug(f"Created MEMORY.md at {self.memory_path}")

        # HEARTBEAT.md
        if not self.heartbeat_path.exists():
            self.heartbeat_path.write_text(DEFAULT_HEARTBEAT_MD, encoding="utf-8")
            logger.debug(f"Created HEARTBEAT.md at {self.heartbeat_path}")

    def load_config(self, parent_config: Optional[Config] = None) -> Config:
        """
        Load workspace configuration.

        If workspace has no config, uses defaults instead of inheriting from parent.
        This ensures each workspace has isolated configuration.

        Args:
            parent_config: Parent configuration (not used for isolation)

        Returns:
            Loaded or inherited configuration
        """
        if self.config_path.exists():
            logger.info(f"Loading config from {self.config_path}")
            self.config = load_config(self.path)
        elif parent_config:
            # Don't inherit parent config directly - use defaults for workspace
            # This ensures each workspace has isolated configuration
            logger.info(f"Using defaults for workspace '{self.name}' (no config found)")
            self.config = load_config(self.path)
        else:
            logger.warning(
                f"No config found for workspace '{self.name}', using defaults"
            )
            self.config = load_config(self.path)

        return self.config

    def load_identity(self) -> Identity:
        """
        Load workspace identity files.

        Always reloads from disk to ensure latest changes are picked up.

        Returns:
            Loaded Identity object
        """
        loader = IdentityLoader(self.path)
        # Always call load_all() to ensure we get fresh data from disk
        self.identity = loader.load_all()
        return self.identity

    async def start(
        self,
        bus: "MessageBus",
        provider: "BaseProvider",
        tools: Optional["ToolRegistry"] = None,
        model: Optional[str] = None,
    ) -> "AgentLoop":
        """
        Start the agent for this workspace.

        Args:
            bus: Message bus for communication
            provider: LLM provider to use
            tools: Tool registry (optional, will create if not provided)
            model: Model name (optional, uses provider default)

        Returns:
            The started AgentLoop instance
        """
        if self._running:
            logger.warning(f"Workspace '{self.name}' is already running")
            return self.agent

        # Load config if not loaded
        if not self.config:
            self.load_config()

        # Load identity if not loaded - always reload to get latest changes
        # Always reload identity to pick up any changes from previous sessions
        self.load_identity()

        # Import here to avoid circular imports
        from clawlet.agent.loop import AgentLoop
        from clawlet.tools.registry import ToolRegistry
        from clawlet.runtime import build_runtime_services

        services = build_runtime_services(self.path, self.config)
        memory_manager = services.memory_manager
        skill_runtime = services.skill_runtime
        skill_registry = skill_runtime.registry

        logger.info(
            f"Loaded {len(skill_registry.skills)} skills with {len(skill_registry.get_all_tools())} tools"
        )

        # Create tool registry if not provided
        if tools is None:
            tools = services.tools
            logger.info(
                f"Created default tool registry with {len(tools.all_tools())} tools for workspace '{self.name}'"
            )
            logger.debug(f"Registered tools: {[t.name for t in tools.all_tools()]}")

        # Get model from config or use default
        if model is None and self.config:
            model = (
                self.config.provider.openrouter.model
                if self.config.provider.openrouter
                else None
            )

        # Create agent
        self.agent = AgentLoop(
            bus=bus,
            workspace=self.path,
            identity=self.identity,
            provider=provider,
            tools=tools,
            model=model,
            max_iterations=self.config.agent.max_iterations if self.config else 50,
            max_tool_calls_per_message=(
                self.config.agent.max_tool_calls_per_message if self.config else 20
            ),
            runtime_config=self.config.runtime if self.config else None,
        )
        # Full config for the v2 orchestrator (per-task profiles, budgets).
        self.agent.full_config = self.config

        self._running = True
        logger.info(f"Started agent for workspace '{self.name}'")

        return self.agent

    async def stop(self) -> None:
        """Stop the agent for this workspace."""
        if not self._running:
            return

        if self.agent:
            self.agent.stop()
            if hasattr(self.agent, "close"):
                await self.agent.close()
            self.agent = None

        self._running = False
        logger.info(f"Stopped agent for workspace '{self.name}'")

    def delete(self, confirm: bool = False) -> bool:
        """
        Delete the workspace directory and all contents.

        Args:
            confirm: Must be True to actually delete. Safety measure to prevent accidental deletion.

        Returns:
            True if deleted successfully
        """
        if not confirm:
            logger.warning(
                f"Delete not confirmed for workspace '{self.name}'. Pass confirm=True to delete."
            )
            return False

        if self._running:
            logger.warning(f"Cannot delete running workspace '{self.name}'")
            return False

        if self.path.exists():
            shutil.rmtree(self.path)
            logger.info(f"Deleted workspace '{self.name}' at {self.path}")
            return True

        return False

    def get_status(self) -> WorkspaceStatus:
        """
        Get the current status of this workspace.

        Returns:
            WorkspaceStatus with current state
        """
        return WorkspaceStatus(
            name=self.name,
            path=self.path,
            exists=self.exists(),
            has_config=self.has_config(),
            has_identity=self.has_identity_files(),
            is_running=self._running,
        )
