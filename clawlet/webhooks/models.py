"""
Webhook event models for Clawlet.

Defines data structures for webhook events that can be received
from external services like GitHub, Stripe, and custom applications.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from enum import Enum
import uuid


class WebhookSource(str, Enum):
    """Supported webhook sources."""
    GITHUB = "github"
    STRIPE = "stripe"
    CUSTOM = "custom"
    HEARTBEAT = "heartbeat"
    USER_DEFINED = "user_defined"


class WebhookEventType(str, Enum):
    """Common webhook event types."""
    # GitHub events
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    ISSUES = "issues"
    ISSUE_COMMENT = "issue_comment"
    RELEASE = "release"
    WORKFLOW_RUN = "workflow_run"
    
    # Stripe events
    PAYMENT_SUCCEEDED = "payment_intent.succeeded"
    PAYMENT_FAILED = "payment_intent.payment_failed"
    CUSTOMER_CREATED = "customer.created"
    CUSTOMER_UPDATED = "customer.updated"
    SUBSCRIPTION_CREATED = "customer.subscription.created"
    SUBSCRIPTION_UPDATED = "customer.subscription.updated"
    SUBSCRIPTION_DELETED = "customer.subscription.deleted"
    INVOICE_PAID = "invoice.paid"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
    
    # Custom events
    CUSTOM = "custom"
    
    # Heartbeat events
    HEARTBEAT_TRIGGER = "heartbeat.trigger"
    
    @classmethod
    def from_github_event(cls, event_name: str) -> "WebhookEventType":
        """Map GitHub event names to WebhookEventType."""
        mapping = {
            "push": cls.PUSH,
            "pull_request": cls.PULL_REQUEST,
            "issues": cls.ISSUES,
            "issue_comment": cls.ISSUE_COMMENT,
            "release": cls.RELEASE,
            "workflow_run": cls.WORKFLOW_RUN,
        }
        return mapping.get(event_name, cls.CUSTOM)
    
    @classmethod
    def from_stripe_event(cls, event_type: str) -> "WebhookEventType":
        """Map Stripe event types to WebhookEventType."""
        mapping = {
            "payment_intent.succeeded": cls.PAYMENT_SUCCEEDED,
            "payment_intent.payment_failed": cls.PAYMENT_FAILED,
            "customer.created": cls.CUSTOMER_CREATED,
            "customer.updated": cls.CUSTOMER_UPDATED,
            "customer.subscription.created": cls.SUBSCRIPTION_CREATED,
            "customer.subscription.updated": cls.SUBSCRIPTION_UPDATED,
            "customer.subscription.deleted": cls.SUBSCRIPTION_DELETED,
            "invoice.paid": cls.INVOICE_PAID,
            "invoice.payment_failed": cls.INVOICE_PAYMENT_FAILED,
        }
        return mapping.get(event_type, cls.CUSTOM)


@dataclass
class WebhookEvent:
    """
    Represents a webhook event received from an external service.
    
    Attributes:
        id: Unique identifier for the event
        source: Where the webhook came from (github, stripe, custom, etc.)
        type: Type of event (push, payment, etc.)
        payload: The raw event payload
        timestamp: When the event was received
        signature: HMAC signature from the source (if provided)
        verified: Whether the signature was verified
        headers: Original HTTP headers from the webhook request
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    type: str = ""
    payload: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    signature: Optional[str] = None
    verified: bool = False
    headers: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate and normalize fields after initialization."""
        if isinstance(self.source, WebhookSource):
            self.source = self.source.value
        if isinstance(self.type, WebhookEventType):
            self.type = self.type.value
    
    @property
    def is_github(self) -> bool:
        """Check if this is a GitHub webhook event."""
        return self.source == WebhookSource.GITHUB.value
    
    @property
    def is_stripe(self) -> bool:
        """Check if this is a Stripe webhook event."""
        return self.source == WebhookSource.STRIPE.value
    
    @property
    def is_custom(self) -> bool:
        """Check if this is a custom webhook event."""
        return self.source == WebhookSource.CUSTOM.value
    
    def to_dict(self) -> dict:
        """Convert the event to a dictionary for serialization."""
        return {
            "id": self.id,
            "source": self.source,
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "signature": self.signature,
            "verified": self.verified,
            "headers": self.headers,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WebhookEvent":
        """Create a WebhookEvent from a dictionary."""
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class WebhookResponse:
    """
    Response to send back to the webhook sender.
    
    Attributes:
        status_code: HTTP status code to return
        message: Response message
        data: Optional additional data to include
    """
    status_code: int = 200
    message: str = "OK"
    data: Optional[dict] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON response."""
        result = {"message": self.message}
        if self.data:
            result["data"] = self.data
        return result


@dataclass
class WebhookError:
    """
    Represents an error that occurred during webhook processing.
    
    Attributes:
        code: Error code
        message: Human-readable error message
        details: Additional error details
    """
    code: str
    message: str
    details: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON response."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }
