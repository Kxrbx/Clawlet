"""
Rate limiting for message and tool execution.
"""

import asyncio
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Optional

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
    timestamps: deque[float] = field(default_factory=deque)
    
    def cleanup(self, window_seconds: float, now: Optional[float] = None) -> None:
        """Remove expired timestamps."""
        current_time = time.time() if now is None else now
        cutoff = current_time - window_seconds

        while self.timestamps and self.timestamps[0] <= cutoff:
            self.timestamps.popleft()
    
    def is_allowed(self, max_requests: int) -> bool:
        """Check if request is allowed."""
        return len(self.timestamps) < max_requests
    
    def record(self, now: Optional[float] = None) -> None:
        """Record a request."""
        self.timestamps.append(time.time() if now is None else now)


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
    
    # Default maximum number of entries to prevent memory growth
    DEFAULT_MAX_ENTRIES = 10000
    
    def __init__(
        self,
        default_limit: Optional[RateLimit] = None,
        tool_limit: Optional[RateLimit] = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        """
        Initialize rate limiter.
        
        Args:
            default_limit: Default rate limit for messages
            tool_limit: Rate limit for tool executions
            max_entries: Maximum number of entries to prevent memory growth (default: 10000)
        """
        self.default_limit = default_limit or RateLimit.per_minute(60)
        self.tool_limit = tool_limit or RateLimit.per_minute(30)
        self.max_entries = max_entries
        
        self._entries: OrderedDict[str, RateLimitEntry] = OrderedDict()
        self._cleanup_interval = 60.0  # Cleanup every minute
        self._last_cleanup = time.time()
        self._cleanup_batch_size = max(32, min(256, self.max_entries))
        self._aggressive_cleanup_batch_size = max(
            self._cleanup_batch_size,
            min(max(self.max_entries, 1), 1024),
        )
        
        logger.info(f"RateLimiter initialized: messages={self.default_limit}, tools={self.tool_limit}, max_entries={self.max_entries}")
    
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
        now = time.time()
        
        # Periodic cleanup
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup(now=now)
        
        entry = self._entries.get(key)
        is_new_key = entry is None
        
        # Limit total entries to prevent memory growth
        if is_new_key:
            if not self._ensure_capacity(key, now):
                logger.error(f"Rate limiter cannot accept new key {key}: too many entries")
                return False, 60.0  # Retry after 1 minute
            entry = RateLimitEntry()
            self._entries[key] = entry
        else:
            self._entries.move_to_end(key)
        
        entry.cleanup(limit.window_seconds, now=now)

        if not entry.timestamps:
            self._entries.move_to_end(key)
        
        if entry.is_allowed(limit.max_requests):
            entry.record(now=now)
            return True, 0.0
        else:
            # Calculate retry time
            oldest = entry.timestamps[0]
            retry_after = oldest + limit.window_seconds - now
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
        self._get_or_create_entry(key).record()
    
    def record_tool(self, tool_name: str, user_id: str) -> None:
        """Record a tool execution."""
        key = f"tool:{tool_name}:{user_id}"
        self._get_or_create_entry(key).record()

    def _get_or_create_entry(self, key: str) -> RateLimitEntry:
        """Get an entry and update its LRU position."""
        entry = self._entries.get(key)
        if entry is None:
            entry = RateLimitEntry()
            self._entries[key] = entry
        else:
            self._entries.move_to_end(key)
        return entry

    def _ensure_capacity(self, incoming_key: str, now: float) -> bool:
        """Make room for a new key using bounded cleanup and LRU eviction."""
        if self.max_entries <= 0:
            return False

        if len(self._entries) < self.max_entries:
            return True

        logger.warning(
            f"Rate limiter entries limit reached ({self.max_entries}), running aggressive cleanup"
        )
        self._cleanup(aggressive=True, now=now)

        while len(self._entries) >= self.max_entries:
            evicted_key, _ = self._entries.popitem(last=False)
            logger.debug(f"Rate limiter evicted least recently used key: {evicted_key}")
            if evicted_key == incoming_key:
                continue

        return len(self._entries) < self.max_entries
    
    def _cleanup(self, aggressive: bool = False, now: Optional[float] = None) -> None:
        """
        Clean up expired entries.
        
        Args:
            aggressive: If True, inspect a larger oldest-first batch before evicting
        """
        current_time = time.time() if now is None else now
        max_window = max(self.default_limit.window_seconds, self.tool_limit.window_seconds)

        batch_size = self._aggressive_cleanup_batch_size if aggressive else self._cleanup_batch_size
        keys_to_check = list(self._entries.keys())[:batch_size]

        for key in keys_to_check:
            entry = self._entries.get(key)
            if entry is None:
                continue

            entry.cleanup(max_window, now=current_time)

            if not entry.timestamps:
                del self._entries[key]
        
        self._last_cleanup = current_time
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
