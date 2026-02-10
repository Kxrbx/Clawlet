"""
Tests for rate limiter.
"""

import pytest
import asyncio
import time

from clawlet.rate_limit import (
    RateLimit,
    RateLimiter,
    TokenBucket,
)


class TestRateLimit:
    """Test rate limit configuration."""
    
    def test_per_second(self):
        """Test per-second rate limit."""
        limit = RateLimit.per_second(10)
        
        assert limit.max_requests == 10
        assert limit.window_seconds == 1.0
    
    def test_per_minute(self):
        """Test per-minute rate limit."""
        limit = RateLimit.per_minute(60)
        
        assert limit.max_requests == 60
        assert limit.window_seconds == 60.0
    
    def test_per_hour(self):
        """Test per-hour rate limit."""
        limit = RateLimit.per_hour(1000)
        
        assert limit.max_requests == 1000
        assert limit.window_seconds == 3600.0


class TestRateLimiter:
    """Test rate limiter."""
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter()
        
        assert limiter.default_limit is not None
        assert limiter.tool_limit is not None
    
    def test_custom_limits(self):
        """Test custom rate limits."""
        limiter = RateLimiter(
            default_limit=RateLimit.per_minute(30),
            tool_limit=RateLimit.per_minute(10),
        )
        
        assert limiter.default_limit.max_requests == 30
        assert limiter.tool_limit.max_requests == 10
    
    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = RateLimiter(
            default_limit=RateLimit.per_second(10),
        )
        
        # Should allow 10 requests
        for _ in range(10):
            allowed, _ = limiter.is_allowed("test_user")
            assert allowed is True
    
    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        """Test that requests over limit are blocked."""
        limiter = RateLimiter(
            default_limit=RateLimit.per_second(5),
        )
        
        # Use up the limit
        for _ in range(5):
            limiter.is_allowed("test_user")
        
        # Next should be blocked
        allowed, retry_after = limiter.is_allowed("test_user")
        assert allowed is False
        assert retry_after > 0
    
    @pytest.mark.asyncio
    async def test_separate_keys(self):
        """Test that different keys have separate limits."""
        limiter = RateLimiter(
            default_limit=RateLimit.per_second(2),
        )
        
        # Use up limit for user1
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        
        # user1 should be blocked
        allowed, _ = limiter.is_allowed("user1")
        assert allowed is False
        
        # user2 should still be allowed
        allowed, _ = limiter.is_allowed("user2")
        assert allowed is True
    
    @pytest.mark.asyncio
    async def test_message_rate_limit(self):
        """Test message rate limiting."""
        limiter = RateLimiter(
            default_limit=RateLimit.per_second(3),
        )
        
        # Should allow 3 messages
        for _ in range(3):
            allowed, _ = limiter.check_message("user1", "telegram")
            assert allowed is True
        
        # 4th should be blocked
        allowed, _ = limiter.check_message("user1", "telegram")
        assert allowed is False
    
    @pytest.mark.asyncio
    async def test_tool_rate_limit(self):
        """Test tool rate limiting."""
        limiter = RateLimiter(
            tool_limit=RateLimit.per_second(2),
        )
        
        # Should allow 2 tool executions
        for _ in range(2):
            allowed, _ = limiter.check_tool("shell", "user1")
            assert allowed is True
        
        # 3rd should be blocked
        allowed, _ = limiter.check_tool("shell", "user1")
        assert allowed is False
    
    @pytest.mark.asyncio
    async def test_reset(self):
        """Test resetting rate limits."""
        limiter = RateLimiter(
            default_limit=RateLimit.per_second(1),
        )
        
        # Use up limit
        limiter.is_allowed("user1")
        
        # Should be blocked
        allowed, _ = limiter.is_allowed("user1")
        assert allowed is False
        
        # Reset
        limiter.reset("user1")
        
        # Should be allowed again
        allowed, _ = limiter.is_allowed("user1")
        assert allowed is True


class TestTokenBucket:
    """Test token bucket rate limiter."""
    
    def test_initialization(self):
        """Test token bucket initialization."""
        bucket = TokenBucket(rate=10.0, burst=20)
        
        assert bucket.rate == 10.0
        assert bucket.burst == 20
        assert bucket._tokens == 20.0  # Starts full
    
    def test_consume_tokens(self):
        """Test consuming tokens."""
        bucket = TokenBucket(rate=1.0, burst=5)
        
        # Should be able to consume 5 tokens
        for _ in range(5):
            assert bucket.consume(1) is True
        
        # 6th should fail
        assert bucket.consume(1) is False
    
    def test_token_refill(self):
        """Test that tokens refill over time."""
        bucket = TokenBucket(rate=100.0, burst=10)  # 100 tokens/sec
        
        # Use all tokens
        bucket.consume(10)
        
        # Wait a bit
        time.sleep(0.1)  # Should refill ~10 tokens
        
        # Should have tokens again
        assert bucket.consume(1) is True
    
    def test_wait_for_tokens(self):
        """Test calculating wait time."""
        bucket = TokenBucket(rate=10.0, burst=5)
        
        # Should have tokens
        assert bucket.wait_for_tokens(1) == 0.0
        
        # Use all tokens
        bucket.consume(5)
        
        # Need to wait for more
        wait_time = bucket.wait_for_tokens(5)
        assert wait_time > 0
        assert wait_time < 1.0  # Should be less than a second with rate=10
