"""
Clawlet Webhooks Module

This module provides webhook handling capabilities for receiving external events
from services like GitHub, Stripe, and custom applications.

Features:
- Async HTTP server using aiohttp
- HMAC signature verification for security
- Multiple webhook endpoints (GitHub, Stripe, Custom)
- Rate limiting for webhook endpoints
- Event queue for async processing
"""

from .models import (
    WebhookEvent,
    WebhookResponse,
    WebhookError,
    WebhookSource,
    WebhookEventType,
)
from .handlers import (
    WebhookHandler,
    GitHubHandler,
    StripeHandler,
    CustomHandler,
    HandlerRegistry,
)
from .server import (
    WebhookServer,
    WebhookEventQueue,
    RateLimiter,
    create_webhook_server,
)

__all__ = [
    # Models
    "WebhookEvent",
    "WebhookResponse",
    "WebhookError",
    "WebhookSource",
    "WebhookEventType",
    # Handlers
    "WebhookHandler",
    "GitHubHandler",
    "StripeHandler",
    "CustomHandler",
    "HandlerRegistry",
    # Server
    "WebhookServer",
    "WebhookEventQueue",
    "RateLimiter",
    "create_webhook_server",
]
