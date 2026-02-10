"""
Tests for message bus.
"""

import pytest
import asyncio

from clawlet.bus.queue import (
    MessageBus,
    InboundMessage,
    OutboundMessage,
)


class TestInboundMessage:
    """Test inbound message dataclass."""
    
    def test_create_inbound(self):
        """Test creating an inbound message."""
        msg = InboundMessage(
            channel="telegram",
            chat_id="123",
            content="Hello!",
            user_id="456",
            user_name="TestUser",
        )
        
        assert msg.channel == "telegram"
        assert msg.chat_id == "123"
        assert msg.content == "Hello!"
        assert msg.user_id == "456"
        assert msg.user_name == "TestUser"
        assert msg.metadata == {}
    
    def test_inbound_with_metadata(self):
        """Test inbound message with metadata."""
        msg = InboundMessage(
            channel="discord",
            chat_id="789",
            content="Test",
            user_id="111",
            user_name="DiscordUser",
            metadata={"guild_id": "222", "is_dm": False},
        )
        
        assert msg.metadata["guild_id"] == "222"
        assert msg.metadata["is_dm"] is False


class TestOutboundMessage:
    """Test outbound message dataclass."""
    
    def test_create_outbound(self):
        """Test creating an outbound message."""
        msg = OutboundMessage(
            channel="telegram",
            chat_id="123",
            content="Response!",
        )
        
        assert msg.channel == "telegram"
        assert msg.chat_id == "123"
        assert msg.content == "Response!"


class TestMessageBus:
    """Test message bus functionality."""
    
    @pytest.mark.asyncio
    async def test_publish_consume_inbound(self):
        """Test publishing and consuming inbound messages."""
        bus = MessageBus()
        
        # Publish a message
        msg = InboundMessage(
            channel="test",
            chat_id="1",
            content="Hello",
            user_id="2",
            user_name="User",
        )
        await bus.publish_inbound(msg)
        
        # Consume the message
        received = await bus.consume_inbound()
        
        assert received.channel == "test"
        assert received.content == "Hello"
    
    @pytest.mark.asyncio
    async def test_publish_consume_outbound(self):
        """Test publishing and consuming outbound messages."""
        bus = MessageBus()
        
        # Publish a message
        msg = OutboundMessage(
            channel="test",
            chat_id="1",
            content="Response",
        )
        await bus.publish_outbound(msg)
        
        # Consume the message
        received = await bus.consume_outbound()
        
        assert received.channel == "test"
        assert received.content == "Response"
    
    @pytest.mark.asyncio
    async def test_queue_ordering(self):
        """Test that messages are processed in order."""
        bus = MessageBus()
        
        # Publish multiple messages
        for i in range(5):
            await bus.publish_inbound(InboundMessage(
                channel="test",
                chat_id=str(i),
                content=f"Message {i}",
                user_id="1",
                user_name="User",
            ))
        
        # Consume and verify order
        for i in range(5):
            msg = await bus.consume_inbound()
            assert msg.chat_id == str(i)
    
    @pytest.mark.asyncio
    async def test_queue_full(self):
        """Test behavior when queue is full."""
        bus = MessageBus(maxsize=2)
        
        # Fill the queue
        for i in range(2):
            await bus.publish_inbound(InboundMessage(
                channel="test",
                chat_id=str(i),
                content=f"Message {i}",
                user_id="1",
                user_name="User",
            ))
        
        # Try to add one more - should wait or fail
        # With maxsize=2, this should block, so we use wait_for
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                bus.publish_inbound(InboundMessage(
                    channel="test",
                    chat_id="overflow",
                    content="Overflow",
                    user_id="1",
                    user_name="User",
                )),
                timeout=0.1,
            )
    
    @pytest.mark.asyncio
    async def test_consume_timeout(self):
        """Test that consume times out on empty queue."""
        bus = MessageBus()
        
        # Try to consume from empty queue with timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                bus.consume_inbound(),
                timeout=0.1,
            )
