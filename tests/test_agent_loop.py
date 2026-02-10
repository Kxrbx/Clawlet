"""
Tests for agent loop
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from clawlet.agent.loop import AgentLoop, Message, ToolCall
from clawlet.agent.identity import Identity


class TestAgentLoopHistory:
    """Test agent loop history management."""
    
    def test_message_dataclass(self):
        """Test Message dataclass."""
        msg = Message(role="user", content="Hello")
        
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.metadata == {}
        assert msg.tool_calls == []
    
    def test_message_to_dict(self):
        """Test Message to_dict method."""
        msg = Message(
            role="assistant",
            content="Hi there",
            metadata={"key": "value"},
        )
        
        d = msg.to_dict()
        
        assert d["role"] == "assistant"
        assert d["content"] == "Hi there"
        assert "metadata" not in d  # Not included in to_dict
    
    def test_tool_call_dataclass(self):
        """Test ToolCall dataclass."""
        tc = ToolCall(id="call_1", name="shell", arguments={"command": "ls"})
        
        assert tc.id == "call_1"
        assert tc.name == "shell"
        assert tc.arguments == {"command": "ls"}
    
    @pytest.mark.asyncio
    async def test_history_trimming(self):
        """Test that history is trimmed when it exceeds max."""
        # Create mock dependencies
        bus = AsyncMock()
        identity = MagicMock(spec=Identity)
        identity.build_system_prompt = MagicMock(return_value="System prompt")
        provider = AsyncMock()
        provider.name = "test"
        provider.get_default_model = MagicMock(return_value="test-model")
        
        agent = AgentLoop(
            bus=bus,
            workspace=Path("/tmp"),
            identity=identity,
            provider=provider,
        )
        
        # Add more than MAX_HISTORY messages
        for i in range(150):
            agent._history.append(Message(role="user", content=f"Message {i}"))
        
        # Trim
        agent._trim_history()
        
        # Should be trimmed to MAX_HISTORY
        assert len(agent._history) == AgentLoop.MAX_HISTORY
        
        # Should keep most recent
        assert "Message 149" in agent._history[-1].content
    
    @pytest.mark.asyncio
    async def test_history_clear(self):
        """Test clearing history."""
        bus = AsyncMock()
        identity = MagicMock(spec=Identity)
        provider = AsyncMock()
        provider.name = "test"
        provider.get_default_model = MagicMock(return_value="test-model")
        
        agent = AgentLoop(
            bus=bus,
            workspace=Path("/tmp"),
            identity=identity,
            provider=provider,
        )
        
        # Add some history
        agent._history.append(Message(role="user", content="Test"))
        assert len(agent._history) == 1
        
        # Clear
        agent.clear_history()
        assert len(agent._history) == 0
    
    @pytest.mark.asyncio
    async def test_history_length(self):
        """Test getting history length."""
        bus = AsyncMock()
        identity = MagicMock(spec=Identity)
        provider = AsyncMock()
        provider.name = "test"
        provider.get_default_model = MagicMock(return_value="test-model")
        
        agent = AgentLoop(
            bus=bus,
            workspace=Path("/tmp"),
            identity=identity,
            provider=provider,
        )
        
        assert agent.get_history_length() == 0
        
        agent._history.append(Message(role="user", content="Test"))
        assert agent.get_history_length() == 1


class TestToolCallExtraction:
    """Test tool call extraction from LLM responses."""
    
    @pytest.mark.asyncio
    async def test_extract_xml_tool_call(self):
        """Test extracting tool call from XML format."""
        bus = AsyncMock()
        identity = MagicMock(spec=Identity)
        identity.build_system_prompt = MagicMock(return_value="System prompt")
        provider = AsyncMock()
        provider.name = "test"
        provider.get_default_model = MagicMock(return_value="test-model")
        
        agent = AgentLoop(
            bus=bus,
            workspace=Path("/tmp"),
            identity=identity,
            provider=provider,
        )
        
        content = '''I'll help you with that.
<tool_call name="shell" arguments='{"command": "ls"}' />'''
        
        tool_calls = agent._extract_tool_calls(content)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "shell"
        assert tool_calls[0].arguments == {"command": "ls"}
    
    @pytest.mark.asyncio
    async def test_extract_json_tool_call(self):
        """Test extracting tool call from JSON block."""
        bus = AsyncMock()
        identity = MagicMock(spec=Identity)
        identity.build_system_prompt = MagicMock(return_value="System prompt")
        provider = AsyncMock()
        provider.name = "test"
        provider.get_default_model = MagicMock(return_value="test-model")
        
        agent = AgentLoop(
            bus=bus,
            workspace=Path("/tmp"),
            identity=identity,
            provider=provider,
        )
        
        content = '''Let me check the files.
```json
{
  "name": "shell",
  "arguments": {"command": "ls -la"}
}
```'''
        
        tool_calls = agent._extract_tool_calls(content)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "shell"
        assert tool_calls[0].arguments == {"command": "ls -la"}
    
    @pytest.mark.asyncio
    async def test_no_tool_calls(self):
        """Test when there are no tool calls."""
        bus = AsyncMock()
        identity = MagicMock(spec=Identity)
        identity.build_system_prompt = MagicMock(return_value="System prompt")
        provider = AsyncMock()
        provider.name = "test"
        provider.get_default_model = MagicMock(return_value="test-model")
        
        agent = AgentLoop(
            bus=bus,
            workspace=Path("/tmp"),
            identity=identity,
            provider=provider,
        )
        
        content = "This is just a regular response with no tool calls."
        
        tool_calls = agent._extract_tool_calls(content)
        
        assert len(tool_calls) == 0
