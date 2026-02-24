"""
Message bus for handling inbound and outbound messages.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple
from collections import defaultdict, deque

from loguru import logger

from clawlet.exceptions import ValidationError, validate_not_empty, validate_string_length, sanitize_string


@dataclass
class InboundMessage:
    """Represents an incoming message from a channel."""
    channel: str
    chat_id: str
    content: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# Maximum content length to prevent memory issues
MAX_CONTENT_LENGTH = 100000  # 100KB


def validate_inbound_message(
    channel: Optional[str] = None,
    chat_id: Optional[str] = None,
    content: Optional[str] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
) -> Tuple[bool, str, dict]:
    """
    Validate inbound message fields.
    
    Args:
        channel: Channel identifier
        chat_id: Chat/conversation identifier
        content: Message content
        user_id: Optional user identifier
        user_name: Optional user name
        
    Returns:
        Tuple of (is_valid, error_message, sanitized_data)
        - is_valid: Whether validation passed
        - error_message: Error message if validation failed
        - sanitized_data: Dictionary with sanitized values (empty if invalid)
    """
    sanitized = {}
    errors = []
    
    # Validate channel (critical - required field)
    is_valid, error_msg = validate_not_empty(channel, "channel", is_critical=True)
    if not is_valid:
        errors.append(error_msg)
    else:
        sanitized["channel"] = channel.strip().lower()
    
    # Validate chat_id (critical - required field)
    is_valid, error_msg = validate_not_empty(chat_id, "chat_id", is_critical=True)
    if not is_valid:
        errors.append(error_msg)
    else:
        sanitized["chat_id"] = chat_id.strip()
    
    # Validate content (critical - required field)
    is_valid, error_msg = validate_not_empty(content, "content", is_critical=True)
    if not is_valid:
        errors.append(error_msg)
    else:
        # Check content length
        is_valid, error_msg = validate_string_length(
            content, "content", min_length=1, max_length=MAX_CONTENT_LENGTH, is_critical=True
        )
        if not is_valid:
            errors.append(error_msg)
        else:
            # Sanitize content to prevent injection attacks
            sanitized["content"] = sanitize_string(content, max_length=MAX_CONTENT_LENGTH)
    
    # Validate user_id (optional - warning only)
    if user_id is not None:
        is_valid, error_msg = validate_string_length(
            user_id, "user_id", min_length=1, max_length=256, is_critical=False
        )
        if is_valid:
            sanitized["user_id"] = sanitize_string(user_id, max_length=256)
        else:
            logger.warning(f"Invalid user_id: {error_msg}")
            sanitized["user_id"] = None
    
    # Validate user_name (optional - warning only)
    if user_name is not None:
        is_valid, error_msg = validate_string_length(
            user_name, "user_name", min_length=1, max_length=256, is_critical=False
        )
        if is_valid:
            sanitized["user_name"] = sanitize_string(user_name, max_length=256)
        else:
            logger.warning(f"Invalid user_name: {error_msg}")
            sanitized["user_name"] = None
    
    if errors:
        error_message = "; ".join(errors)
        # Log warnings for non-critical issues
        logger.warning(f"Inbound message validation failed: {error_message}")
        return False, error_message, {}
    
    return True, "", sanitized


@dataclass  
class OutboundMessage:
    """Represents an outgoing message to a channel."""
    channel: str
    chat_id: str
    content: str
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class OutboundRateLimiter:
    """
    Rate limiter for outbound messages using sliding window algorithm.
    
    Tracks messages sent per channel/chat_id and enforces configurable limits.
    """
    
    def __init__(
        self,
        max_per_minute: int = 20,
        max_per_hour: int = 100,
        strict_mode: bool = False,
    ):
        """
        Initialize outbound rate limiter.
        
        Args:
            max_per_minute: Maximum outbound messages per minute per chat
            max_per_hour: Maximum outbound messages per hour per chat
            strict_mode: If True, reject messages when rate limited.
                        If False (default), log warning but allow message.
        """
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self.strict_mode = strict_mode
        
        # Track timestamps for each channel:chat_id
        self._timestamps: dict[str, deque[float]] = defaultdict(deque)
        self._cleanup_interval = 60.0  # Cleanup every minute
        self._last_cleanup = time.time()
        
        logger.info(
            f"OutboundRateLimiter initialized: max_per_minute={max_per_minute}, "
            f"max_per_hour={max_per_hour}, strict_mode={strict_mode}"
        )
    
    def _cleanup(self) -> None:
        """Remove expired timestamps from all entries."""
        now = time.time()
        hour_ago = now - 3600
        
        for key, timestamps in list(self._timestamps.items()):
            # Remove timestamps older than 1 hour
            while timestamps and timestamps[0] < hour_ago:
                timestamps.popleft()
            
            # Remove empty entries
            if not timestamps:
                del self._timestamps[key]
        
        self._last_cleanup = now
        logger.debug(f"OutboundRateLimiter cleanup: {len(self._timestamps)} active keys")
    
    def _get_key(self, channel: str, chat_id: str) -> str:
        """Generate unique key for channel:chat_id pair."""
        return f"{channel}:{chat_id}"
    
    def _clean_key(self, key: str) -> None:
        """Remove expired timestamps for a specific key."""
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        timestamps = self._timestamps[key]
        
        # Keep timestamps from last hour (needed for hour limit)
        while timestamps and timestamps[0] < hour_ago:
            timestamps.popleft()
    
    def check(self, channel: str, chat_id: str) -> tuple[bool, float]:
        """
        Check if sending a message is allowed.
        
        Args:
            channel: Channel identifier (e.g., 'telegram', 'discord')
            chat_id: Chat/conversation identifier
            
        Returns:
            (is_allowed, retry_after_seconds): Tuple of whether allowed and seconds until retry
        """
        # Periodic cleanup
        if time.time() - self._last_cleanup > self._cleanup_interval:
            self._cleanup()
        
        key = self._get_key(channel, chat_id)
        self._clean_key(key)
        
        timestamps = self._timestamps[key]
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        # Count messages in current minute and hour
        minute_count = sum(1 for t in timestamps if t >= minute_ago)
        hour_count = len(timestamps)
        
        # Check minute limit first
        if minute_count >= self.max_per_minute:
            # Calculate retry time based on oldest message in current minute
            recent_timestamps = [t for t in timestamps if t >= minute_ago]
            if recent_timestamps:
                oldest = min(recent_timestamps)
                retry_after = oldest + 60 - now
            else:
                retry_after = 60.0
            
            if self.strict_mode:
                logger.warning(
                    f"Outbound rate limit (minute) exceeded for {channel}:{chat_id}. "
                    f"{minute_count}/{self.max_per_minute} messages. Retry after {retry_after:.1f}s"
                )
            return False, max(0, retry_after)
        
        # Check hour limit
        if hour_count >= self.max_per_hour:
            if timestamps:
                oldest = min(timestamps)
                retry_after = oldest + 3600 - now
            else:
                retry_after = 3600.0
            
            if self.strict_mode:
                logger.warning(
                    f"Outbound rate limit (hour) exceeded for {channel}:{chat_id}. "
                    f"{hour_count}/{self.max_per_hour} messages. Retry after {retry_after:.1f}s"
                )
            return False, max(0, retry_after)
        
        # Allowed - record the timestamp
        timestamps.append(now)
        return True, 0.0
    
    def is_allowed(self, channel: str, chat_id: str) -> bool:
        """
        Simple check if sending is allowed (without retry time).
        
        Args:
            channel: Channel identifier
            chat_id: Chat/conversation identifier
            
        Returns:
            True if allowed, False if rate limited
        """
        allowed, _ = self.check(channel, chat_id)
        return allowed
    
    def record(self, channel: str, chat_id: str) -> None:
        """
        Record a sent message (for when check passed but we want to record explicitly).
        
        Args:
            channel: Channel identifier
            chat_id: Chat/conversation identifier
        """
        key = self._get_key(channel, chat_id)
        self._timestamps[key].append(time.time())
    
    def get_stats(self, channel: str, chat_id: str) -> dict:
        """
        Get rate limit statistics for a specific channel:chat_id.
        
        Returns:
            Dict with current counts and limits
        """
        key = self._get_key(channel, chat_id)
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        timestamps = self._timestamps.get(key, [])
        minute_count = sum(1 for t in timestamps if t >= minute_ago)
        hour_count = len(timestamps)
        
        return {
            "channel": channel,
            "chat_id": chat_id,
            "messages_last_minute": minute_count,
            "messages_last_hour": hour_count,
            "max_per_minute": self.max_per_minute,
            "max_per_hour": self.max_per_hour,
        }
    
    def reset(self, channel: Optional[str] = None, chat_id: Optional[str] = None) -> None:
        """
        Reset rate limits.
        
        Args:
            channel: If provided, reset only this channel
            chat_id: If provided with channel, reset only this chat
        """
        if channel and chat_id:
            key = self._get_key(channel, chat_id)
            if key in self._timestamps:
                del self._timestamps[key]
            logger.info(f"Reset outbound rate limit for {channel}:{chat_id}")
        elif channel:
            # Reset all chats for this channel
            keys_to_delete = [
                k for k in self._timestamps.keys() 
                if k.startswith(f"{channel}:")
            ]
            for key in keys_to_delete:
                del self._timestamps[key]
            logger.info(f"Reset outbound rate limits for channel {channel}")
        else:
            self._timestamps.clear()
            logger.info("Reset all outbound rate limits")


class MessageBus:
    """
    Async message bus for routing messages between channels and agent.
    
    Uses asyncio queues for non-blocking message handling.
    Supports outbound rate limiting to prevent spam.
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        max_outbound_per_minute: int = 20,
        max_outbound_per_hour: int = 100,
        outbound_rate_limit_enabled: bool = True,
        outbound_rate_limit_strict: bool = False,
    ):
        """
        Initialize MessageBus.
        
        Args:
            max_size: Maximum queue size
            max_outbound_per_minute: Max outbound messages per minute per chat
            max_outbound_per_hour: Max outbound messages per hour per chat
            outbound_rate_limit_enabled: Enable outbound rate limiting
            outbound_rate_limit_strict: If True, reject messages when rate limited.
                                        If False (default), log warning but allow message.
        """
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=max_size)
        self._outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue(maxsize=max_size)
        self._running = False
        
        # Initialize outbound rate limiter
        self._outbound_rate_limiter: Optional[OutboundRateLimiter] = None
        if outbound_rate_limit_enabled:
            self._outbound_rate_limiter = OutboundRateLimiter(
                max_per_minute=max_outbound_per_minute,
                max_per_hour=max_outbound_per_hour,
                strict_mode=outbound_rate_limit_strict,
            )
        
        logger.info(f"MessageBus initialized with max_size={max_size}")
    
    @property
    def outbound_rate_limiter(self) -> Optional[OutboundRateLimiter]:
        """Get the outbound rate limiter instance."""
        return self._outbound_rate_limiter
    
    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish an inbound message to the queue."""
        await self._inbound.put(msg)
        logger.debug(f"Published inbound message from {msg.channel}/{msg.chat_id}")
    
    async def publish_outbound(self, msg: OutboundMessage) -> bool:
        """
        Publish an outbound message to the queue.
        
        Args:
            msg: The outbound message to publish
            
        Returns:
            True if published successfully, False if rate limited (non-strict mode)
            
        Raises:
            RateLimitExceeded: If strict mode is enabled and rate limit is exceeded
        """
        # Check rate limit if enabled
        if self._outbound_rate_limiter is not None:
            allowed, retry_after = self._outbound_rate_limiter.check(msg.channel, msg.chat_id)
            
            if not allowed:
                stats = self._outbound_rate_limiter.get_stats(msg.channel, msg.chat_id)
                if self._outbound_rate_limiter.strict_mode:
                    from clawlet.exceptions import RateLimitExceeded
                    raise RateLimitExceeded(
                        f"Outbound rate limit exceeded for {msg.channel}:{msg.chat_id}. "
                        f"Minute: {stats['messages_last_minute']}/{stats['max_per_minute']}, "
                        f"Hour: {stats['messages_last_hour']}/{stats['max_per_hour']}. "
                        f"Retry after {retry_after:.1f}s"
                    )
                else:
                    logger.warning(
                        f"Outbound rate limit exceeded for {msg.channel}:{msg.chat_id}. "
                        f"Allowing anyway (non-strict mode). "
                        f"Minute: {stats['messages_last_minute']}/{stats['max_per_minute']}, "
                        f"Hour: {stats['messages_last_hour']}/{stats['max_per_hour']}"
                    )
                    # Still allow the message in non-strict mode
        
        await self._outbound.put(msg)
        logger.debug(f"Published outbound message to {msg.channel}/{msg.chat_id}")
        return True
    
    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message."""
        return await self._inbound.get()
    
    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message."""
        return await self._outbound.get()
    
    @property
    def inbound_size(self) -> int:
        """Get number of pending inbound messages."""
        return self._inbound.qsize()
    
    @property
    def outbound_size(self) -> int:
        """Get number of pending outbound messages."""
        return self._outbound.qsize()
