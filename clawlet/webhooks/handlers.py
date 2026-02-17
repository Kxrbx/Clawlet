"""
Webhook handlers for processing incoming webhook events.

Provides base handler class and specific implementations for
GitHub, Stripe, and custom webhooks with HMAC signature verification.
"""

import hashlib
import hmac
import json
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any, Awaitable
from datetime import datetime

from loguru import logger

from clawlet.webhooks.models import (
    WebhookEvent,
    WebhookResponse,
    WebhookError,
    WebhookSource,
    WebhookEventType,
)


class WebhookHandler(ABC):
    """
    Abstract base class for webhook handlers.
    
    Subclasses must implement:
        - verify_signature: Validate the webhook signature
        - parse_event: Parse the raw payload into a WebhookEvent
        - get_event_type: Determine the event type from the payload
    """
    
    def __init__(self, secret: Optional[str] = None):
        """
        Initialize the handler.
        
        Args:
            secret: Secret key for HMAC signature verification
        """
        self.secret = secret
        self._event_hooks: dict[str, list[Callable[[WebhookEvent], Awaitable[None]]]] = {}
    
    def register_hook(
        self, 
        event_type: str, 
        hook: Callable[[WebhookEvent], Awaitable[None]]
    ) -> None:
        """
        Register a hook to be called when a specific event type is received.
        
        Args:
            event_type: The event type to hook into
            hook: Async function to call when the event is received
        """
        if event_type not in self._event_hooks:
            self._event_hooks[event_type] = []
        self._event_hooks[event_type].append(hook)
        logger.debug(f"Registered hook for event type: {event_type}")
    
    async def process(
        self, 
        payload: bytes, 
        headers: dict
    ) -> tuple[Optional[WebhookEvent], Optional[WebhookError]]:
        """
        Process an incoming webhook request.
        
        Args:
            payload: Raw request body bytes
            headers: HTTP headers from the request
            
        Returns:
            Tuple of (WebhookEvent or None, WebhookError or None)
        """
        # Verify signature
        signature = self._extract_signature(headers)
        if self.secret and not self.verify_signature(payload, signature, headers):
            error = WebhookError(
                code="INVALID_SIGNATURE",
                message="Webhook signature verification failed",
                details={"source": self.source_name}
            )
            return None, error
        
        # Parse the event
        try:
            event = self.parse_event(payload, headers, signature)
            event.verified = True
        except Exception as e:
            logger.exception(f"Failed to parse {self.source_name} webhook")
            error = WebhookError(
                code="PARSE_ERROR",
                message=f"Failed to parse webhook payload: {str(e)}",
                details={"source": self.source_name}
            )
            return None, error
        
        # Run event hooks
        await self._run_hooks(event)
        
        logger.info(
            f"Processed {self.source_name} webhook: {event.type} (id={event.id})"
        )
        return event, None
    
    async def _run_hooks(self, event: WebhookEvent) -> None:
        """Run all registered hooks for the event type."""
        hooks = self._event_hooks.get(event.type, [])
        hooks.extend(self._event_hooks.get("*", []))  # Wildcard hooks
        
        for hook in hooks:
            try:
                await hook(event)
            except Exception as e:
                logger.exception(f"Error in webhook hook: {e}")
    
    @abstractmethod
    def verify_signature(
        self, 
        payload: bytes, 
        signature: Optional[str],
        headers: dict
    ) -> bool:
        """
        Verify the webhook signature.
        
        Args:
            payload: Raw request body bytes
            signature: Extracted signature from headers
            headers: HTTP headers
            
        Returns:
            True if signature is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def parse_event(
        self, 
        payload: bytes, 
        headers: dict,
        signature: Optional[str]
    ) -> WebhookEvent:
        """
        Parse the raw payload into a WebhookEvent.
        
        Args:
            payload: Raw request body bytes
            headers: HTTP headers
            signature: Extracted signature from headers
            
        Returns:
            Parsed WebhookEvent
        """
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the source name for this handler."""
        pass
    
    def _extract_signature(self, headers: dict) -> Optional[str]:
        """Extract signature from headers (override in subclasses)."""
        return None


class GitHubHandler(WebhookHandler):
    """
    Handler for GitHub webhook events.
    
    Supports signature verification using HMAC-SHA256 and
    parsing of common GitHub event types.
    """
    
    @property
    def source_name(self) -> str:
        return WebhookSource.GITHUB.value
    
    def _extract_signature(self, headers: dict) -> Optional[str]:
        """Extract X-Hub-Signature-256 header."""
        return headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256")
    
    def verify_signature(
        self, 
        payload: bytes, 
        signature: Optional[str],
        headers: dict
    ) -> bool:
        """
        Verify GitHub webhook signature using HMAC-SHA256.
        
        GitHub sends the signature in the X-Hub-Signature-256 header
        in the format: sha256=<hex_digest>
        """
        if not self.secret:
            logger.warning("No GitHub secret configured, skipping signature verification")
            return True
        
        if not signature:
            logger.warning("No signature provided in GitHub webhook")
            return False
        
        # GitHub sends: sha256=<hex_digest>
        if signature.startswith("sha256="):
            signature = signature[7:]
        
        expected = hmac.new(
            self.secret.encode("utf-8"),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    
    def parse_event(
        self, 
        payload: bytes, 
        headers: dict,
        signature: Optional[str]
    ) -> WebhookEvent:
        """Parse GitHub webhook payload."""
        data = json.loads(payload.decode("utf-8"))
        
        # Get event type from X-GitHub-Event header
        event_name = headers.get("X-GitHub-Event") or headers.get("x-github-event", "unknown")
        event_type = WebhookEventType.from_github_event(event_name)
        
        # Extract useful metadata
        repo = data.get("repository", {})
        sender = data.get("sender", {})
        
        return WebhookEvent(
            source=WebhookSource.GITHUB.value,
            type=event_type.value,
            payload=data,
            signature=signature,
            headers={
                "x-github-event": event_name,
                "x-github-delivery": headers.get("X-GitHub-Delivery", ""),
                "repository": repo.get("full_name", ""),
                "sender": sender.get("login", ""),
            }
        )


class StripeHandler(WebhookHandler):
    """
    Handler for Stripe webhook events.
    
    Supports signature verification using Stripe's signing secret
    and parsing of Stripe event objects.
    """
    
    # Stripe signature tolerance in seconds (5 minutes)
    SIGNATURE_TOLERANCE = 300
    
    @property
    def source_name(self) -> str:
        return WebhookSource.STRIPE.value
    
    def _extract_signature(self, headers: dict) -> Optional[str]:
        """Extract Stripe-Signature header."""
        return headers.get("Stripe-Signature") or headers.get("stripe-signature")
    
    def verify_signature(
        self, 
        payload: bytes, 
        signature: Optional[str],
        headers: dict
    ) -> bool:
        """
        Verify Stripe webhook signature.
        
        Stripe sends a signature header with timestamp and signatures:
        t=1492774557,v1=5257a869e7c...,v0=6ffbb...
        """
        if not self.secret:
            logger.warning("No Stripe secret configured, skipping signature verification")
            return True
        
        if not signature:
            logger.warning("No signature provided in Stripe webhook")
            return False
        
        # Parse the signature header
        elements = {}
        for item in signature.split(","):
            key, value = item.split("=", 1)
            elements[key] = value
        
        timestamp = elements.get("t")
        v1_signature = elements.get("v1")
        
        if not timestamp or not v1_signature:
            logger.warning("Invalid Stripe signature format")
            return False
        
        # Check timestamp to prevent replay attacks
        try:
            event_time = int(timestamp)
            current_time = int(datetime.utcnow().timestamp())
            if abs(current_time - event_time) > self.SIGNATURE_TOLERANCE:
                logger.warning("Stripe webhook timestamp outside tolerance")
                return False
        except ValueError:
            return False
        
        # Compute expected signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(
            self.secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(v1_signature, expected)
    
    def parse_event(
        self, 
        payload: bytes, 
        headers: dict,
        signature: Optional[str]
    ) -> WebhookEvent:
        """Parse Stripe webhook payload."""
        data = json.loads(payload.decode("utf-8"))
        
        # Stripe wraps events in an object with type, data, etc.
        event_type = WebhookEventType.from_stripe_event(data.get("type", "unknown"))
        
        return WebhookEvent(
            source=WebhookSource.STRIPE.value,
            type=event_type.value,
            payload=data,
            signature=signature,
            headers={
                "stripe-signature": signature or "",
                "stripe-event-id": data.get("id", ""),
            }
        )


class CustomHandler(WebhookHandler):
    """
    Handler for custom webhook events.
    
    Provides flexible payload handling with optional signature
    verification using a simple HMAC-SHA256 approach.
    """
    
    def __init__(
        self, 
        secret: Optional[str] = None,
        name: str = WebhookSource.CUSTOM.value
    ):
        super().__init__(secret)
        self._name = name
    
    @property
    def source_name(self) -> str:
        return self._name
    
    def _extract_signature(self, headers: dict) -> Optional[str]:
        """Extract X-Webhook-Signature header."""
        return headers.get("X-Webhook-Signature") or headers.get("x-webhook-signature")
    
    def verify_signature(
        self, 
        payload: bytes, 
        signature: Optional[str],
        headers: dict
    ) -> bool:
        """
        Verify custom webhook signature using HMAC-SHA256.
        
        Expects the signature in X-Webhook-Signature header as hex digest.
        """
        if not self.secret:
            logger.debug("No secret configured for custom webhook, skipping verification")
            return True
        
        if not signature:
            logger.warning("No signature provided in custom webhook")
            return False
        
        expected = hmac.new(
            self.secret.encode("utf-8"),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    
    def parse_event(
        self, 
        payload: bytes, 
        headers: dict,
        signature: Optional[str]
    ) -> WebhookEvent:
        """Parse custom webhook payload."""
        data = json.loads(payload.decode("utf-8"))
        
        # Custom webhooks should include type in payload, or use header
        event_type = (
            data.get("type") or 
            data.get("event_type") or 
            headers.get("X-Webhook-Type") or 
            WebhookEventType.CUSTOM.value
        )
        
        return WebhookEvent(
            source=self._name,
            type=event_type,
            payload=data,
            signature=signature,
            headers=dict(headers)
        )


class HandlerRegistry:
    """
    Registry for webhook handlers.
    
    Allows registration and lookup of handlers by source name.
    """
    
    def __init__(self):
        self._handlers: dict[str, WebhookHandler] = {}
    
    def register(self, handler: WebhookHandler) -> None:
        """Register a handler for its source name."""
        self._handlers[handler.source_name] = handler
        logger.info(f"Registered webhook handler: {handler.source_name}")
    
    def get(self, source: str) -> Optional[WebhookHandler]:
        """Get handler for a source name."""
        return self._handlers.get(source)
    
    def has(self, source: str) -> bool:
        """Check if a handler exists for a source."""
        return source in self._handlers
    
    def sources(self) -> list[str]:
        """Get list of registered source names."""
        return list(self._handlers.keys())
    
    def create_default_handlers(
        self,
        default_secret: Optional[str] = None,
        github_secret: Optional[str] = None,
        stripe_secret: Optional[str] = None,
        custom_handlers: Optional[dict[str, str]] = None
    ) -> None:
        """
        Create and register default handlers.
        
        Args:
            default_secret: Default secret for custom webhooks
            github_secret: Secret for GitHub webhooks
            stripe_secret: Secret for Stripe webhooks
            custom_handlers: Dict mapping handler names to secrets
        """
        # Register GitHub handler
        if github_secret:
            self.register(GitHubHandler(secret=github_secret))
        
        # Register Stripe handler
        if stripe_secret:
            self.register(StripeHandler(secret=stripe_secret))
        
        # Register default custom handler
        self.register(CustomHandler(secret=default_secret))
        
        # Register additional custom handlers
        if custom_handlers:
            for name, secret in custom_handlers.items():
                self.register(CustomHandler(secret=secret, name=name))


# Global registry instance
registry = HandlerRegistry()