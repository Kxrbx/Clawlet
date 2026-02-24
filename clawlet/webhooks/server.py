"""
Webhook HTTP server for receiving external events.

Provides an async HTTP server using aiohttp with:
- Multiple webhook endpoints
- HMAC signature verification
- Rate limiting
- Event queue for async processing
"""

import asyncio
import time
from typing import Optional, Callable, Awaitable
from collections import defaultdict
from dataclasses import dataclass

from aiohttp import web
from loguru import logger

from clawlet.webhooks.models import WebhookEvent, WebhookResponse, WebhookError
from clawlet.webhooks.handlers import (
    WebhookHandler,
    GitHubHandler,
    StripeHandler,
    CustomHandler,
    HandlerRegistry,
    registry as global_registry,
)
from clawlet.bus.queue import InboundMessage, MessageBus


@dataclass
class RateLimitEntry:
    """Track rate limit state for a client."""
    count: int = 0
    window_start: float = 0.0


class RateLimiter:
    """
    Simple in-memory rate limiter for webhook endpoints.
    
    Uses a sliding window approach to limit requests per time period.
    """
    
    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
        cleanup_interval: int = 300
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Window duration in seconds
            cleanup_interval: Interval to clean up old entries
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.cleanup_interval = cleanup_interval
        self._entries: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._last_cleanup = time.time()
    
    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """
        Check if a client is allowed to make a request.
        
        Args:
            client_id: Unique identifier for the client (e.g., IP address)
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = time.time()
        entry = self._entries[client_id]
        
        # Check if window has expired
        if now - entry.window_start > self.window_seconds:
            entry.count = 0
            entry.window_start = now
        
        # Check limit
        if entry.count >= self.max_requests:
            retry_after = int(self.window_seconds - (now - entry.window_start))
            return False, max(1, retry_after)
        
        # Increment and allow
        entry.count += 1
        
        # Periodic cleanup
        if now - self._last_cleanup > self.cleanup_interval:
            self._cleanup(now)
        
        return True, 0
    
    def _cleanup(self, now: float) -> None:
        """Remove expired entries."""
        expired = [
            client_id for client_id, entry in self._entries.items()
            if now - entry.window_start > self.window_seconds
        ]
        for client_id in expired:
            del self._entries[client_id]
        self._last_cleanup = now
        logger.debug(f"Cleaned up {len(expired)} expired rate limit entries")


class WebhookEventQueue:
    """
    Async queue for webhook events awaiting processing.
    
    Events are queued and can be consumed by the agent or
    other processing systems.
    """
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize the event queue.
        
        Args:
            max_size: Maximum number of events in the queue
        """
        self._queue: asyncio.Queue[WebhookEvent] = asyncio.Queue(maxsize=max_size)
        self._event_hooks: list[Callable[[WebhookEvent], Awaitable[None]]] = []
        logger.info(f"WebhookEventQueue initialized with max_size={max_size}")
    
    async def put(self, event: WebhookEvent) -> None:
        """
        Add an event to the queue.
        
        Args:
            event: The webhook event to queue
        """
        await self._queue.put(event)
        logger.debug(f"Queued webhook event: {event.source}/{event.type} (id={event.id})")
        
        # Run event hooks
        for hook in self._event_hooks:
            try:
                await hook(event)
            except Exception as e:
                logger.exception(f"Error in event hook: {e}")
    
    async def get(self) -> WebhookEvent:
        """
        Get the next event from the queue.
        
        Returns:
            The next webhook event
        """
        return await self._queue.get()
    
    def qsize(self) -> int:
        """Get the current queue size."""
        return self._queue.qsize()
    
    def register_hook(self, hook: Callable[[WebhookEvent], Awaitable[None]]) -> None:
        """
        Register a hook to be called when events are queued.
        
        Args:
            hook: Async function to call for each event
        """
        self._event_hooks.append(hook)
    
    async def publish_to_bus(self, bus: MessageBus) -> None:
        """
        Publish an event to the message bus as an InboundMessage.
        
        Args:
            bus: The message bus to publish to
        """
        event = await self.get()
        msg = InboundMessage(
            channel=f"webhook:{event.source}",
            chat_id=event.id,
            content=event.type,
            user_id=event.headers.get("sender"),
            metadata={
                "webhook_event": event.to_dict(),
                "source": event.source,
                "type": event.type,
                "payload": event.payload,
            }
        )
        await bus.publish_inbound(msg)
        logger.debug(f"Published webhook event to message bus: {event.id}")


class WebhookServer:
    """
    Async HTTP server for receiving webhooks.
    
    Provides endpoints for:
    - /webhooks/github - GitHub events
    - /webhooks/stripe - Stripe events
    - /webhooks/custom - Generic custom webhooks
    - /webhooks/:name - User-defined webhooks
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        registry: Optional[HandlerRegistry] = None,
        event_queue: Optional[WebhookEventQueue] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """
        Initialize the webhook server.
        
        Args:
            host: Host to bind to
            port: Port to listen on
            registry: Handler registry (uses global if not provided)
            event_queue: Event queue for processed events
            rate_limiter: Rate limiter for requests
        """
        self.host = host
        self.port = port
        self.registry = registry or global_registry
        self.event_queue = event_queue or WebhookEventQueue()
        self.rate_limiter = rate_limiter or RateLimiter()
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
    
    def create_app(self) -> web.Application:
        """
        Create the aiohttp application with routes.
        
        Returns:
            Configured aiohttp Application
        """
        app = web.Application()
        
        # Health check endpoint
        app.router.add_get("/health", self._handle_health)
        
        # Webhook endpoints
        app.router.add_post("/webhooks/github", self._handle_github)
        app.router.add_post("/webhooks/stripe", self._handle_stripe)
        app.router.add_post("/webhooks/custom", self._handle_custom)
        app.router.add_post("/webhooks/custom/{name}", self._handle_custom)
        app.router.add_post("/webhooks/{name}", self._handle_named)
        
        # Middleware for rate limiting
        app.middlewares.append(self._rate_limit_middleware)
        
        logger.info("Webhook server routes configured")
        return app
    
    @web.middleware
    async def _rate_limit_middleware(
        self, 
        request: web.Request, 
        handler: Callable[[web.Request], Awaitable[web.Response]]
    ) -> web.Response:
        """Middleware for rate limiting requests."""
        # Get client identifier (IP or X-Forwarded-For)
        client_id = request.remote
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_id = forwarded.split(",")[0].strip()
        
        # Check rate limit
        allowed, retry_after = self.rate_limiter.is_allowed(client_id)
        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_id}")
            return web.Response(
                status=429,
                text="Too Many Requests",
                headers={"Retry-After": str(retry_after)}
            )
        
        return await handler(request)
    
    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle health check requests."""
        return web.json_response({
            "status": "healthy",
            "queue_size": self.event_queue.qsize(),
            "handlers": self.registry.sources(),
        })
    
    async def _handle_github(self, request: web.Request) -> web.Response:
        """Handle GitHub webhook requests."""
        return await self._process_webhook(request, "github")
    
    async def _handle_stripe(self, request: web.Request) -> web.Response:
        """Handle Stripe webhook requests."""
        return await self._process_webhook(request, "stripe")
    
    async def _handle_custom(self, request: web.Request) -> web.Response:
        """Handle custom webhook requests."""
        name = request.match_info.get("name", "custom")
        return await self._process_webhook(request, name)
    
    async def _handle_named(self, request: web.Request) -> web.Response:
        """Handle named webhook requests."""
        name = request.match_info.get("name")
        return await self._process_webhook(request, name)
    
    async def _process_webhook(
        self, 
        request: web.Request, 
        source: str
    ) -> web.Response:
        """
        Process a webhook request.
        
        Args:
            request: The incoming HTTP request
            source: The webhook source name
            
        Returns:
            HTTP response
        """
        # Get handler
        handler = self.registry.get(source)
        if not handler:
            logger.warning(f"No handler registered for source: {source}")
            error = WebhookError(
                code="UNKNOWN_SOURCE",
                message=f"No handler registered for source: {source}",
                details={"source": source}
            )
            return web.json_response(error.to_dict(), status=404)
        
        # Read payload
        payload = await request.read()
        headers = dict(request.headers)
        
        # Process with handler
        event, error = await handler.process(payload, headers)
        
        if error:
            return web.json_response(error.to_dict(), status=error.code == "INVALID_SIGNATURE" and 401 or 400)
        
        # Queue event for processing
        if event:
            await self.event_queue.put(event)
        
        response = WebhookResponse(
            status_code=200,
            message="Webhook received",
            data={"event_id": event.id if event else None}
        )
        return web.json_response(response.to_dict(), status=response.status_code)
    
    async def start(self) -> None:
        """Start the webhook server."""
        self._app = self.create_app()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        
        logger.info(f"Webhook server started on {self.host}:{self.port}")
    
    async def stop(self) -> None:
        """Stop the webhook server."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        
        logger.info("Webhook server stopped")
    
    async def __aenter__(self) -> "WebhookServer":
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()


async def create_webhook_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    default_secret: Optional[str] = None,
    github_secret: Optional[str] = None,
    stripe_secret: Optional[str] = None,
    custom_handlers: Optional[dict[str, str]] = None,
    queue_max_size: int = 1000,
    rate_limit_max: int = 100,
    rate_limit_window: int = 60,
) -> WebhookServer:
    """
    Create and configure a webhook server with default handlers.
    
    Args:
        host: Host to bind to
        port: Port to listen on
        default_secret: Default secret for custom webhooks
        github_secret: Secret for GitHub webhooks
        stripe_secret: Secret for Stripe webhooks
        custom_handlers: Dict mapping handler names to secrets
        queue_max_size: Maximum events in queue
        rate_limit_max: Max requests per window
        rate_limit_window: Rate limit window in seconds
        
    Returns:
        Configured WebhookServer instance
    """
    # Create registry with handlers
    registry = HandlerRegistry()
    registry.create_default_handlers(
        default_secret=default_secret,
        github_secret=github_secret,
        stripe_secret=stripe_secret,
        custom_handlers=custom_handlers
    )
    
    # Create event queue and rate limiter
    event_queue = WebhookEventQueue(max_size=queue_max_size)
    rate_limiter = RateLimiter(
        max_requests=rate_limit_max,
        window_seconds=rate_limit_window
    )
    
    # Create server
    server = WebhookServer(
        host=host,
        port=port,
        registry=registry,
        event_queue=event_queue,
        rate_limiter=rate_limiter,
    )
    
    return server