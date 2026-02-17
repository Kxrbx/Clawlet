# Webhooks Documentation

Webhooks allow Clawlet to receive and process events from external services like GitHub, Stripe, and custom applications.

## Table of Contents

- [Overview](#overview)
- [Setting Up Webhooks](#setting-up-webhooks)
- [GitHub Integration](#github-integration)
- [Stripe Integration](#stripe-integration)
- [Custom Webhooks](#custom-webhooks)
- [Security Best Practices](#security-best-practices)
- [Configuration Reference](#configuration-reference)

---

## Overview

The webhook system provides:

- **Async HTTP Server** - Built on aiohttp for high performance
- **HMAC Signature Verification** - Secure webhook validation
- **Multiple Endpoints** - Handle different webhook sources
- **Rate Limiting** - Protect against abuse
- **Event Queue** - Async event processing

### Architecture

```
External Service -> HTTP POST -> WebhookServer -> Handler -> Event Queue -> Agent
```

### Components

| Component | Purpose |
|-----------|---------|
| `WebhookServer` | HTTP server for receiving webhooks |
| `WebhookHandler` | Base class for processing webhooks |
| `GitHubHandler` | GitHub webhook processing |
| `StripeHandler` | Stripe webhook processing |
| `CustomHandler` | Generic webhook handler |
| `RateLimiter` | Request rate limiting |

---

## Setting Up Webhooks

### Basic Configuration

Add webhook configuration to `~/.clawlet/config.yaml`:

```yaml
webhooks:
  enabled: true
  host: "0.0.0.0"
  port: 8080
  handlers:
    github:
      enabled: true
      secret: "${GITHUB_WEBHOOK_SECRET}"
    stripe:
      enabled: true
      secret: "${STRIPE_WEBHOOK_SECRET}"
```

### Starting the Webhook Server

```bash
# Start with webhooks enabled
clawlet agent --webhooks

# Or specify port
clawlet agent --webhook-port 8080
```

### Public URL Requirements

Webhooks require a publicly accessible URL. Options:

1. **Direct Deployment** - Deploy on a server with public IP
2. **Reverse Proxy** - Use nginx/Apache with SSL
3. **Tunneling** - Use ngrok for development

#### Using ngrok (Development)

```bash
# Install ngrok
# Start Clawlet on port 8080
clawlet agent --webhook-port 8080

# In another terminal, start ngrok
ngrok http 8080

# Use the ngrok URL for webhook configuration
# Example: https://abc123.ngrok.io/webhook/github
```

---

## GitHub Integration

### Setup

1. Go to your repository settings on GitHub
2. Navigate to "Webhooks" > "Add webhook"
3. Configure:
   - **Payload URL**: `https://your-domain.com/webhook/github`
   - **Content type**: `application/json`
   - **Secret**: Your chosen secret
   - **Events**: Select events to receive

### Configuration

```yaml
webhooks:
  handlers:
    github:
      enabled: true
      secret: "${GITHUB_WEBHOOK_SECRET}"
      events:
        - push
        - pull_request
        - issues
        - issue_comment
```

### Supported Events

| Event | Description |
|-------|-------------|
| `push` | Code pushed to repository |
| `pull_request` | PR opened, closed, or synchronized |
| `issues` | Issue opened, closed, or edited |
| `issue_comment` | Comment on issue or PR |
| `release` | Release published |
| `fork` | Repository forked |
| `star` | Repository starred |

### Example Usage

When a GitHub event is received, Clawlet can:
- Notify you of new issues or PRs
- Summarize push events
- Respond to comments
- Trigger workflows

```
GitHub -> Webhook -> Clawlet -> "New PR #42 opened in repo/owner"
```

### Signature Verification

GitHub signs webhooks with HMAC-SHA256:

```python
# Automatic verification
# X-Hub-Signature-256: sha256=<hex-digest>
```

Clawlet automatically verifies signatures when a secret is configured.

---

## Stripe Integration

### Setup

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
2. Navigate to "Developers" > "Webhooks"
3. Click "Add endpoint"
4. Configure:
   - **Endpoint URL**: `https://your-domain.com/webhook/stripe`
   - **Events**: Select events to receive

### Configuration

```yaml
webhooks:
  handlers:
    stripe:
      enabled: true
      secret: "${STRIPE_WEBHOOK_SECRET}"  # Signing secret from Stripe
      events:
        - checkout.session.completed
        - payment_intent.succeeded
        - invoice.paid
```

### Supported Events

| Event | Description |
|-------|-------------|
| `checkout.session.completed` | Checkout session completed |
| `payment_intent.succeeded` | Payment successful |
| `payment_intent.payment_failed` | Payment failed |
| `invoice.paid` | Invoice paid |
| `invoice.payment_failed` | Invoice payment failed |
| `customer.created` | New customer created |
| `customer.updated` | Customer updated |

### Example Usage

When a Stripe event is received, Clawlet can:
- Confirm successful payments
- Alert on failed payments
- Update customer records
- Trigger fulfillment

```
Stripe -> Webhook -> Clawlet -> "Payment of $29.99 received from customer"
```

### Signature Verification

Stripe signs webhooks with HMAC-SHA256:

```python
# Automatic verification
# Stripe-Signature: t=<timestamp>,v1=<signature>
```

Clawlet verifies both signature and timestamp to prevent replay attacks.

---

## Custom Webhooks

### Creating a Custom Handler

For services not natively supported, create a custom webhook handler:

```yaml
webhooks:
  handlers:
    custom:
      enabled: true
      path: "/webhook/custom"
      secret: "${CUSTOM_WEBHOOK_SECRET}"  # Optional
```

### Custom Handler Configuration

```yaml
webhooks:
  handlers:
    my_service:
      enabled: true
      path: "/webhook/myservice"
      secret: "${MYSERVICE_SECRET}"
      response_type: "json"  # "json" or "text"
      events:
        - event_type_1
        - event_type_2
```

### Webhook Payload Format

Custom webhooks should send JSON payloads:

```json
{
  "event_type": "user.created",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "user_id": "123",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

### Processing Custom Events

Clawlet processes custom webhook events and can:
- Extract event type from payload
- Pass event data to the agent
- Trigger configured actions

### Signature Verification (Optional)

For custom webhooks with signature verification:

```python
# Your external service should sign payloads
import hmac
import hashlib

signature = hmac.new(
    secret.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()

# Send header: X-Signature: sha256=<signature>
```

---

## Security Best Practices

### 1. Always Use HTTPS

Never expose webhooks over HTTP in production:

```yaml
webhooks:
  host: "0.0.0.0"
  port: 443
  ssl:
    cert: "/path/to/cert.pem"
    key: "/path/to/key.pem"
```

Or use a reverse proxy with SSL termination.

### 2. Configure Secrets

Always configure webhook secrets:

```yaml
webhooks:
  handlers:
    github:
      secret: "${GITHUB_WEBHOOK_SECRET}"  # Required
```

### 3. Verify Signatures

Clawlet automatically verifies signatures when secrets are configured. Never disable verification in production.

### 4. Rate Limiting

Configure rate limiting to prevent abuse:

```yaml
webhooks:
  rate_limit:
    enabled: true
    max_requests: 100  # Per window
    window_seconds: 60
```

### 5. IP Allowlisting (Optional)

Restrict webhook sources by IP:

```yaml
webhooks:
  allowed_ips:
    - "192.0.2.0/24"  # GitHub IPs
    - "203.0.113.0/24"  # Stripe IPs
```

### 6. Validate Event Types

Only process expected event types:

```yaml
webhooks:
  handlers:
    github:
      events:
        - push
        - pull_request
      # Ignore all other events
```

### 7. Log for Auditing

Enable logging for security auditing:

```yaml
webhooks:
  logging:
    enabled: true
    level: "INFO"
    include_payload: false  # Don't log sensitive data
```

### 8. Handle Errors Gracefully

Return appropriate HTTP status codes:

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | Bad request / invalid payload |
| 401 | Invalid signature |
| 429 | Rate limit exceeded |
| 500 | Server error |

---

## Configuration Reference

### Top-Level Configuration

```yaml
webhooks:
  enabled: true
  host: "0.0.0.0"
  port: 8080
  
  # Rate limiting
  rate_limit:
    enabled: true
    max_requests: 100
    window_seconds: 60
  
  # SSL (optional, use reverse proxy instead)
  ssl:
    enabled: false
    cert: null
    key: null
  
  # Handlers
  handlers:
    github: { ... }
    stripe: { ... }
    custom: { ... }
```

### GitHub Handler

```yaml
github:
  enabled: true
  path: "/webhook/github"  # Default
  secret: "${GITHUB_WEBHOOK_SECRET}"
  events:
    - push
    - pull_request
    - issues
    - issue_comment
```

### Stripe Handler

```yaml
stripe:
  enabled: true
  path: "/webhook/stripe"  # Default
  secret: "${STRIPE_WEBHOOK_SECRET}"
  events:
    - checkout.session.completed
    - payment_intent.succeeded
    - invoice.paid
```

### Custom Handler

```yaml
custom:
  enabled: true
  path: "/webhook/custom"
  secret: null  # Optional
  response_type: "json"
  events: []  # Accept all events
```

---

## Webhook Endpoints

| Endpoint | Handler | Purpose |
|----------|---------|---------|
| `/webhook/github` | GitHubHandler | GitHub events |
| `/webhook/stripe` | StripeHandler | Stripe events |
| `/webhook/custom` | CustomHandler | Generic webhooks |
| `/health` | Server | Health check |

---

## Troubleshooting

### Webhook Not Received

1. Check the URL is publicly accessible
2. Verify the endpoint path matches configuration
3. Check server logs for incoming requests
4. Verify SSL certificate is valid

### Signature Verification Failed

1. Ensure secret matches on both ends
2. Check payload is sent as raw bytes
3. Verify signature header format
4. Check for encoding issues

### Rate Limiting Issues

1. Increase rate limit if legitimate traffic is blocked
2. Check for retry storms from webhook source
3. Consider IP allowlisting for known sources

### Debug Mode

Enable debug logging:

```yaml
webhooks:
  logging:
    level: "DEBUG"
    include_headers: true
    include_payload: true  # Be careful with sensitive data
```

---

## See Also

- [Channels Documentation](channels.md) - Messaging platform integrations
- [Scheduling Documentation](scheduling.md) - Schedule automated tasks
- [Multi-Agent Documentation](multi-agent.md) - Route events to different agents