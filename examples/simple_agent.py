"""
Example: Simple agent that responds to messages.
"""

import asyncio

from clawlet import IdentityLoader, AgentLoop
from clawlet.bus.queue import MessageBus
from clawlet.config import load_config


async def main():
    """Run a simple agent."""
    # Load config
    config = load_config()
    
    # Load identity
    identity = IdentityLoader()
    
    # Create message bus
    bus = MessageBus()
    
    # Create agent loop
    agent = AgentLoop(
        bus=bus,
        identity=identity,
        config=config,
    )
    
    # Process a simple message
    from clawlet.bus.queue import InboundMessage
    
    message = InboundMessage(
        channel="telegram",
        chat_id="test",
        content="Hello! What can you do?",
        user_id="user1",
        user_name="TestUser",
    )
    
    await bus.publish_inbound(message)
    
    # Run the agent
    print("Starting agent...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
