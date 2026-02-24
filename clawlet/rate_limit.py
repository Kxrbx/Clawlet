"""
Rate limiting for message and tool execution.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

from loguru import logger


@dataclass
class RateLimit:
    """Rate limit configuration."""
    max_requests: int
    window_seconds: float
    
    @classmethod
    def per_second(cls, max_requests: int) -> "RateLimit":
        """Create a per-second rate limit."""
        return cls(max_requests=max_requests, window_seconds=1.0)
    
    @classmethod
    def per_minute(cls, max_requests: int) -> "RateLimit":
        """Create a per-minute rate limit."""
        return cls(max_requests=max_requests, window_seconds=60.0)
    
    @classmethod
    def per_hour(cls, max_requests: int) -> "RateLimit":
        """Create a per-hour rate limit."""
        return cls(max_requests=max_requests, window_seconds=3600.0)


@dataclass
class RateLimitEntry:
    """Entry tracking requests for a key."""
    timestamps: list[float] = field(default_factory=list)
    
    def cleanup(self, window_seconds: float) -> None:
        """Remove expired timestamps."""
        cutoff = time.time() - window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]
    
    def is_allowed(self, max_requests: int) -> bool:
        """Check if request is allowed."""
        return len(self.timestamps) < max_requests
    
    def record(self) -> None:
        """Record a request."""
        self.timestamps.append(time.time())


class RateLimiter:
    """
    Rate limiter with sliding window algorithm.
    
    Supports:
    - Per-user rate limiting
    - Per-channel rate limiting  
    - Global rate limiting
    - Multiple rate limit tiers
    - Automatic cleanup of stale entries
    """
    
    # Maximum number of entries to prevent memory growth
    MAX_ENTRIES = 10000
    
    def __init__(
        self,
        default_limit: Optional[RateLimit] = None,
        tool_limit: Optional[RateLimit] = None,
    ):
        """
        Initialize rate limiter.
        
        Args:
            default_limit: Default rate limit for messages
            tool_limit: Rate limit for tool executions
        """
        self.default_limit = default_limit or RateLimit.per_minute(60)
        self.tool_limit = tool_limit or RateLimit.per_minute(30)
        
        self._entries: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._cleanup_interval = 60.0  # Cleanup every minute
        self._last_cleanup = time.time()
        
        logger.info(f"RateLimiter initialized: messages={self.default_limit}, tools={self.tool_limit}")
    
    def is_allowed(self, key: str, limit: Optional[RateLimit] = None) -> tuple[bool, float]:
        """
        Check if a request is allowed.
        
        Args:
            key: Unique identifier (e.g., user_id, channel_id)
            limit: Rate limit to use (default if not specified)
            
        Returns:
            (is_allowed, retry_after_seconds)
        """
        limit = limit or self.default_limit
        
        # Periodic cleanup
        if time.time() - self._last_cleanup > self._cleanup_interval:
            self._cleanup()
        
        # Limit total entries to prevent memory growth
        if len(self._entries) >= self.MAX_ENTRIES:
            logger.warning(f"Rate limiter entries limit reached ({self.MAX_ENTRIES}), running aggressive cleanup")
            self._cleanup(aggressive=True)
            
            # If still at limit after aggressive cleanup, reject the new key
            if len(self._entries) >= self.MAX_ENTRIES:
                logger.error(f"Rate limiter cannot accept new key {key}: too many entries")
                return False, 60.0  # Retry after 1 minute
        
        entry = self._entries[key]
        entry.cleanup(limit.window_seconds)
        
        if entry.is_allowed(limit.max_requests):
            entry.record()
            return True, 0.0
        else:
            # Calculate retry time
            oldest = min(entry.timestamps)
            retry_after = oldest + limit.window_seconds - time.time()
            return False, max(0, retry_after)
    
    def check_message(self, user_id: str, channel: str) -> tuple[bool, float]:
        """Check if a message is allowed."""
        key = f"msg:{channel}:{user_id}"
        return self.is_allowed(key, self.default_limit)
    
    def check_tool(self, tool_name: str, user_id: str) -> tuple[bool, float]:
        """Check if a tool execution is allowed."""
        key = f"tool:{tool_name}:{user_id}"
        return self.is_allowed(key, self.tool_limit)
    
    def record_message(self, user_id: str, channel: str) -> None:
        """Record a message (bypasses check)."""
        key = f"msg:{channel}:{user_id}"
        self._entries[key].record()
    
    def record_tool(self, tool_name: str, user_id: str) -> None:
        """Record a tool execution."""
        key = f"tool:{tool_name}:{user_id}"
        self._entries[key].record()
    
    def _cleanup(self, aggressive: bool = False) -> None:
        """
        Clean up expired entries.
        
        Args:
            aggressive: If True, also remove entries older than 2x window_seconds
        """
        max_window = max(self.default_limit.window_seconds, self.tool_limit.window_seconds)
        cutoff = time.time() - max_window
        
        # For aggressive cleanup, use 2x window_seconds cutoff
        aggressive_cutoff = time.time() - (2 * max_window) if aggressive else None
        
        # Clean up each entry
        for key, entry in list(self._entries.items()):
            entry.cleanup(max_window)
            
            # For aggressive cleanup, also check for stale entries
            if aggressive and aggressive_cutoff is not None:
                # Remove entries that have no recent timestamps
                if not entry.timestamps or min(entry.timestamps) < aggressive_cutoff:
                    del self._entries[key]
                    continue
            
            if not entry.timestamps:
                del self._entries[key]
        
        self._last_cleanup = time.time()
        logger.debug(f"Rate limiter cleanup: {len(self._entries)} active keys")
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        return {
            "active_keys": len(self._entries),
            "default_limit": {
                "max_requests": self.default_limit.max_requests,
                "window_seconds": self.default_limit.window_seconds,
            },
            "tool_limit": {
                "max_requests": self.tool_limit.max_requests,
                "window_seconds": self.tool_limit.window_seconds,
            },
        }
    
    def reset(self, key: Optional[str] = None) -> None:
        """Reset rate limits for a key (or all if key is None)."""
        if key:
            if key in self._entries:
                del self._entries[key]
        else:
            self._entries.clear()
        
        logger.info(f"Rate limits reset: {key or 'all'}")


class TokenBucket:
    """
    Token bucket rate limiter for smoother rate limiting.
    
    Good for APIs with burst allowances.
    """
    
    def __init__(
        self,
        rate: float,  # Tokens per second
        burst: int,   # Maximum tokens
    ):
        """
        Initialize token bucket.
        
        Args:
            rate: Tokens added per second
            burst: Maximum tokens (burst capacity)
        """
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last_update = time.time()
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_update = now
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.
        
        Returns True if successful, False if not enough tokens.
        """
        self._refill()
        
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False
    
    def wait_for_tokens(self, tokens: int = 1) -> float:
        """
        Calculate how long to wait for tokens.
        
        Returns wait time in seconds (0 if tokens available).
        """
        self._refill()
        
        if self._tokens >= tokens:
            return 0.0
        
        needed = tokens - self._tokens
        return needed / self.rate
