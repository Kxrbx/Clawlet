"""
Agent router - routes incoming messages to appropriate agents.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from loguru import logger

from clawlet.bus.queue import InboundMessage

if TYPE_CHECKING:
    from clawlet.agent.loop import AgentLoop


@dataclass
class AgentConfig:
    """Configuration for a registered agent."""
    agent_id: str
    workspace: str  # Workspace name
    enabled: bool = True
    description: str = ""


@dataclass
class RouteRule:
    """
    Rule for routing messages to agents.
    
    Rules are matched in priority order (highest first).
    A rule matches if ALL specified conditions match (AND logic).
    """
    agent_id: str
    channel: Optional[str] = None      # "telegram", "discord", "slack", "whatsapp"
    user_id: Optional[str] = None       # Specific user ID
    workspace: Optional[str] = None     # Workspace name (for context)
    pattern: Optional[str] = None       # Regex pattern on message content
    priority: int = 0                   # Higher priority rules checked first
    
    # Compiled regex pattern (internal)
    _compiled_pattern: Optional[re.Pattern] = field(default=None, repr=False, compare=False)
    
    def __post_init__(self):
        """Compile the regex pattern if provided."""
        if self.pattern:
            try:
                self._compiled_pattern = re.compile(self.pattern, re.IGNORECASE)
            except re.error as e:
                logger.warning(f"Invalid regex pattern in route rule: {self.pattern} - {e}")
                self._compiled_pattern = None
    
    def matches(self, message: InboundMessage) -> bool:
        """
        Check if this rule matches the given message.
        
        Args:
            message: The inbound message to check
            
        Returns:
            True if all specified conditions match
        """
        # Check channel
        if self.channel is not None and message.channel != self.channel:
            return False
        
        # Check user_id
        if self.user_id is not None and message.user_id != self.user_id:
            return False
        
        # Check pattern on message content
        if self.pattern is not None and self._compiled_pattern is not None:
            if not self._compiled_pattern.search(message.content):
                return False
        
        # All specified conditions matched
        return True


class AgentRouter:
    """
    Routes incoming messages to appropriate agents.
    
    The router maintains a registry of agents and routing rules.
    When a message arrives, it checks rules in priority order
    and returns the first matching agent.
    
    Example:
        router = AgentRouter()
        router.register_agent("personal", AgentConfig(
            agent_id="personal",
            workspace="personal"
        ))
        router.add_route(RouteRule(
            agent_id="personal",
            channel="telegram",
            priority=10
        ))
        
        agent_id = router.route(message)
        if agent_id:
            agent = router.get_agent(agent_id)
            await agent.process(message)
    """
    
    def __init__(self):
        self.agents: dict[str, AgentConfig] = {}
        self.routes: list[RouteRule] = []
        self._agent_instances: dict[str, "AgentLoop"] = {}
    
    def register_agent(self, agent_id: str, config: AgentConfig) -> None:
        """
        Register an agent configuration.
        
        Args:
            agent_id: Unique identifier for the agent
            config: Agent configuration
        """
        self.agents[agent_id] = config
        logger.info(f"Registered agent: {agent_id} (workspace: {config.workspace})")
    
    def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent.
        
        Args:
            agent_id: Agent ID to unregister
            
        Returns:
            True if agent was removed, False if not found
        """
        if agent_id in self.agents:
            del self.agents[agent_id]
            # Remove associated instance
            if agent_id in self._agent_instances:
                del self._agent_instances[agent_id]
            # Remove routes for this agent
            self.routes = [r for r in self.routes if r.agent_id != agent_id]
            logger.info(f"Unregistered agent: {agent_id}")
            return True
        return False
    
    def add_route(self, rule: RouteRule) -> None:
        """
        Add a routing rule.
        
        Rules are automatically sorted by priority (highest first).
        
        Args:
            rule: The routing rule to add
        """
        # Verify agent exists
        if rule.agent_id not in self.agents:
            logger.warning(f"Adding route for unknown agent: {rule.agent_id}")
        
        self.routes.append(rule)
        # Sort by priority (highest first)
        self.routes.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"Added route: agent={rule.agent_id}, channel={rule.channel}, "
                   f"user={rule.user_id}, pattern={rule.pattern}, priority={rule.priority}")
    
    def remove_route(self, index: int) -> bool:
        """
        Remove a routing rule by index.
        
        Args:
            index: Index of the rule to remove
            
        Returns:
            True if rule was removed
        """
        if 0 <= index < len(self.routes):
            rule = self.routes.pop(index)
            logger.info(f"Removed route for agent: {rule.agent_id}")
            return True
        return False
    
    def clear_routes(self) -> None:
        """Clear all routing rules."""
        self.routes.clear()
        logger.info("Cleared all routing rules")
    
    def route(self, message: InboundMessage) -> Optional[str]:
        """
        Route a message to the appropriate agent.
        
        Checks rules in priority order and returns the first matching agent.
        
        Args:
            message: The inbound message to route
            
        Returns:
            Agent ID if a matching rule is found, None otherwise
        """
        for rule in self.routes:
            # Skip rules for disabled agents
            agent_config = self.agents.get(rule.agent_id)
            if agent_config and not agent_config.enabled:
                continue
            
            if rule.matches(message):
                logger.debug(f"Message routed to agent '{rule.agent_id}' "
                           f"(channel={message.channel}, user={message.user_id})")
                return rule.agent_id
        
        # No matching rule found
        logger.debug(f"No route found for message (channel={message.channel}, user={message.user_id})")
        return None
    
    def get_agent_config(self, agent_id: str) -> Optional[AgentConfig]:
        """
        Get agent configuration by ID.
        
        Args:
            agent_id: The agent ID
            
        Returns:
            AgentConfig if found, None otherwise
        """
        return self.agents.get(agent_id)
    
    def register_agent_instance(self, agent_id: str, agent: "AgentLoop") -> None:
        """
        Register an agent instance.
        
        Args:
            agent_id: The agent ID
            agent: The agent loop instance
        """
        self._agent_instances[agent_id] = agent
        logger.debug(f"Registered agent instance: {agent_id}")
    
    def get_agent(self, agent_id: str) -> Optional["AgentLoop"]:
        """
        Get an agent instance by ID.
        
        Args:
            agent_id: The agent ID
            
        Returns:
            AgentLoop instance if found, None otherwise
        """
        return self._agent_instances.get(agent_id)
    
    def unregister_agent_instance(self, agent_id: str) -> bool:
        """
        Unregister an agent instance.
        
        Args:
            agent_id: The agent ID
            
        Returns:
            True if instance was removed
        """
        if agent_id in self._agent_instances:
            del self._agent_instances[agent_id]
            logger.debug(f"Unregistered agent instance: {agent_id}")
            return True
        return False
    
    def list_agents(self) -> list[str]:
        """
        List all registered agent IDs.
        
        Returns:
            List of agent IDs
        """
        return list(self.agents.keys())
    
    def list_routes(self) -> list[RouteRule]:
        """
        List all routing rules.
        
        Returns:
            List of routing rules (sorted by priority)
        """
        return self.routes.copy()
    
    def get_routes_for_agent(self, agent_id: str) -> list[RouteRule]:
        """
        Get all routing rules for a specific agent.
        
        Args:
            agent_id: The agent ID
            
        Returns:
            List of routing rules for the agent
        """
        return [r for r in self.routes if r.agent_id == agent_id]
    
    def get_default_agent(self) -> Optional[str]:
        """
        Get the default agent ID (first registered agent).
        
        Returns:
            Default agent ID or None if no agents registered
        """
        if self.agents:
            return next(iter(self.agents.keys()))
        return None
