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
from clawlet.agent.router import AgentConfig

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

DEFAULT_HEARTBEAT_MD = """# Periodic Tasks

This file defines tasks I should perform periodically.

## Daily Check-in
Each day, I should:
- Review any pending tasks
- Check for important dates or events
- Ask if there's anything specific you need help with

## Notes
Configure specific periodic tasks in config.yaml under the schedule section.
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
        workspace = Workspace("personal", Path("~/.clawlet/workspaces/personal"))
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
        
        self.config: Optional[Config] = None
        self.identity: Optional[Identity] = None
        self.agent: Optional["AgentLoop"] = None
        self._running = False
    
    @property
    def config_path(self) -> Path:
        """Path to workspace config file."""
        return self.path / "config.yaml"
    
    @property
    def soul_path(self) -> Path:
        """Path to SOUL.md."""
        return self.path / "SOUL.md"
    
    @property
    def user_path(self) -> Path:
        """Path to USER.md."""
        return self.path / "USER.md"
    
    @property
    def memory_path(self) -> Path:
        """Path to MEMORY.md."""
        return self.path / "MEMORY.md"
    
    @property
    def heartbeat_path(self) -> Path:
        """Path to HEARTBEAT.md."""
        return self.path / "HEARTBEAT.md"
    
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
                "max_iterations": 10,
                "context_window": 20,
                "temperature": 0.7,
                "max_history": 100,
            },
            "skills": {
                "enabled": True,
                "directories": ["~/.clawlet/skills", "./skills"],
            },
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False)
        
        logger.debug(f"Created default config at {self.config_path}")
    
    def _create_identity_files(self, agent_name: str, user_name: str) -> None:
        """Create default identity files."""
        # SOUL.md
        if not self.soul_path.exists():
            self.soul_path.write_text(
                DEFAULT_SOUL_MD.format(agent_name=agent_name, user_name=user_name),
                encoding="utf-8"
            )
            logger.debug(f"Created SOUL.md at {self.soul_path}")
        
        # USER.md
        if not self.user_path.exists():
            self.user_path.write_text(
                DEFAULT_USER_MD.format(user_name=user_name),
                encoding="utf-8"
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
            self.config = load_config(Path.home() / ".clawlet")
        else:
            logger.warning(f"No config found for workspace '{self.name}', using defaults")
            self.config = load_config(Path.home() / ".clawlet")
        
        return self.config
    
    def load_identity(self) -> Identity:
        """
        Load workspace identity files.
        
        Returns:
            Loaded Identity object
        """
        loader = IdentityLoader(self.path)
        self.identity = loader.load_all()
        return self.identity
    
    def get_agent_config(self) -> AgentConfig:
        """
        Get agent configuration for this workspace.
        
        Returns:
            AgentConfig for registering with router
        """
        return AgentConfig(
            agent_id=self.name,
            workspace=self.name,
            enabled=True,
            description=f"Workspace: {self.name}"
        )
    
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
        
        # Load identity if not loaded
        if not self.identity:
            self.load_identity()
        
        # Import here to avoid circular imports
        from clawlet.agent.loop import AgentLoop
        from clawlet.tools.registry import ToolRegistry
        
        # Create tool registry if not provided
        if tools is None:
            tools = ToolRegistry()
        
        # Get model from config or use default
        if model is None and self.config:
            model = self.config.provider.openrouter.model if self.config.provider.openrouter else None
        
        # Create agent
        self.agent = AgentLoop(
            bus=bus,
            workspace=self.path,
            identity=self.identity,
            provider=provider,
            tools=tools,
            model=model,
            max_iterations=self.config.agent.max_iterations if self.config else 10,
        )
        
        self._running = True
        logger.info(f"Started agent for workspace '{self.name}'")
        
        return self.agent
    
    async def stop(self) -> None:
        """Stop the agent for this workspace."""
        if not self._running:
            return
        
        if self.agent:
            self.agent.stop()
            if hasattr(self.agent, 'close'):
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
            logger.warning(f"Delete not confirmed for workspace '{self.name}'. Pass confirm=True to delete.")
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


class WorkspaceManager:
    """
    Manages multiple workspaces.
    
    The manager handles:
    - Creating and deleting workspaces
    - Starting and stopping workspace agents
    - Listing available workspaces
    
    Example:
        manager = WorkspaceManager(Path("~/.clawlet/workspaces"))
        
        # Create a new workspace
        workspace = manager.create_workspace("personal")
        
        # List workspaces
        names = manager.list_workspaces()
        
        # Start all workspaces
        await manager.start_all(bus, provider)
    """
    
    def __init__(self, base_path: Path):
        """
        Initialize the workspace manager.
        
        Args:
            base_path: Base directory for workspaces
        """
        self.base_path = base_path.expanduser().resolve()
        self.workspaces: dict[str, Workspace] = {}
    
    @property
    def workspaces_path(self) -> Path:
        """Path to workspaces directory."""
        return self.base_path / "workspaces"
    
    def discover_workspaces(self) -> list[str]:
        """
        Discover existing workspaces in the base directory.
        
        Returns:
            List of workspace names found
        """
        if not self.workspaces_path.exists():
            return []
        
        workspaces = []
        for item in self.workspaces_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it looks like a workspace (has config or identity files)
                if (item / "config.yaml").exists() or (item / "SOUL.md").exists():
                    workspaces.append(item.name)
        
        return workspaces
    
    def create_workspace(
        self,
        name: str,
        agent_name: Optional[str] = None,
        user_name: Optional[str] = None,
        template_config: Optional[Config] = None,
    ) -> Workspace:
        """
        Create a new workspace.
        
        Args:
            name: Workspace name
            agent_name: Name for the agent
            user_name: Name for the user
            template_config: Optional config template
            
        Returns:
            The created Workspace instance
        """
        if name in self.workspaces:
            raise ValueError(f"Workspace '{name}' already exists")
        
        workspace = Workspace(name, self.workspaces_path / name)
        workspace.create(agent_name, user_name, template_config)
        
        self.workspaces[name] = workspace
        return workspace
    
    def get_workspace(self, name: str) -> Optional[Workspace]:
        """
        Get a workspace by name.
        
        Args:
            name: Workspace name
            
        Returns:
            Workspace if found, None otherwise
        """
        if name in self.workspaces:
            return self.workspaces[name]
        
        # Try to load from disk
        workspace_path = self.workspaces_path / name
        if workspace_path.exists():
            workspace = Workspace(name, workspace_path)
            self.workspaces[name] = workspace
            return workspace
        
        return None
    
    def get_or_create_workspace(self, name: str) -> Workspace:
        """
        Get a workspace or create it if it doesn't exist.
        
        Args:
            name: Workspace name
            
        Returns:
            Workspace instance
        """
        workspace = self.get_workspace(name)
        if workspace:
            return workspace
        
        return self.create_workspace(name)
    
    def list_workspaces(self) -> list[str]:
        """
        List all known workspace names.
        
        Returns:
            List of workspace names
        """
        # Combine discovered and loaded workspaces
        discovered = set(self.discover_workspaces())
        loaded = set(self.workspaces.keys())
        return sorted(discovered | loaded)
    
    def list_workspace_statuses(self) -> list[WorkspaceStatus]:
        """
        Get status of all workspaces.
        
        Returns:
            List of WorkspaceStatus objects
        """
        statuses = []
        for name in self.list_workspaces():
            workspace = self.get_workspace(name)
            if workspace:
                statuses.append(workspace.get_status())
        return statuses
    
    async def start_workspace(
        self,
        name: str,
        bus: "MessageBus",
        provider: "BaseProvider",
        tools: Optional["ToolRegistry"] = None,
        model: Optional[str] = None,
    ) -> Optional["AgentLoop"]:
        """
        Start a specific workspace's agent.
        
        Args:
            name: Workspace name
            bus: Message bus
            provider: LLM provider
            tools: Tool registry
            model: Model name
            
        Returns:
            AgentLoop if started, None if workspace not found
        """
        workspace = self.get_workspace(name)
        if not workspace:
            logger.warning(f"Workspace '{name}' not found")
            return None
        
        return await workspace.start(bus, provider, tools, model)
    
    async def stop_workspace(self, name: str) -> bool:
        """
        Stop a specific workspace's agent.
        
        Args:
            name: Workspace name
            
        Returns:
            True if stopped, False if not running or not found
        """
        workspace = self.get_workspace(name)
        if not workspace:
            return False
        
        await workspace.stop()
        return True
    
    async def start_all(
        self,
        bus: "MessageBus",
        provider: "BaseProvider",
        tools: Optional["ToolRegistry"] = None,
        model: Optional[str] = None,
    ) -> dict[str, "AgentLoop"]:
        """
        Start all discovered workspaces.
        
        Args:
            bus: Message bus
            provider: LLM provider
            tools: Tool registry
            model: Model name
            
        Returns:
            Dict mapping workspace names to their AgentLoop instances
        """
        agents = {}
        
        for name in self.list_workspaces():
            try:
                agent = await self.start_workspace(name, bus, provider, tools, model)
                if agent:
                    agents[name] = agent
            except Exception as e:
                logger.error(f"Failed to start workspace '{name}': {e}")
        
        return agents
    
    async def stop_all(self) -> None:
        """Stop all running workspace agents."""
        for name, workspace in self.workspaces.items():
            if workspace._running:
                try:
                    await workspace.stop()
                except Exception as e:
                    logger.error(f"Error stopping workspace '{name}': {e}")
    
    def delete_workspace(self, name: str) -> bool:
        """
        Delete a workspace.
        
        Args:
            name: Workspace name
            
        Returns:
            True if deleted, False if not found or running
        """
        workspace = self.get_workspace(name)
        if not workspace:
            return False
        
        if workspace.delete(confirm=True):
            del self.workspaces[name]
            return True
        
        return False
    
    def get_running_workspaces(self) -> list[str]:
        """
        Get list of currently running workspace names.
        
        Returns:
            List of running workspace names
        """
        return [
            name for name, workspace in self.workspaces.items()
            if workspace._running
        ]