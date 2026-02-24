---
name: email
version: 1.0.0
description: Send and manage emails on behalf of the user
author: clawlet
requires:
  - smtp_server
  - smtp_port
  - smtp_user
  - smtp_password
tools:
  - name: send_email
    description: Send an email to one or more recipients
    parameters:
      - name: to
        type: string
        description: Recipient email address(es), comma-separated for multiple
        required: true
      - name: subject
        type: string
        description: Email subject line
        required: true
      - name: body
        type: string
        description: Email body content (plain text)
        required: true
      - name: cc
        type: string
        description: CC recipient(s), comma-separated
        required: false
      - name: bcc
        type: string
        description: BCC recipient(s), comma-separated
        required: false
  - name: list_drafts
    description: List email drafts
    parameters:
      - name: limit
        type: integer
        description: Maximum number of drafts to return
        required: false
        default: 10
  - name: send_draft
    description: Send a previously saved draft
    parameters:
      - name: draft_id
        type: string
        description: ID of the draft to send
        required: true
---

# Email Skill

Use this skill to send emails on behalf of the user.

## Usage

When the user asks you to send an email, use the `send_email` tool. You should:

1. Confirm the recipient address
2. Ask for subject and body if not provided
3. Send the email using the tool

## Examples

- "Send an email to john@example.com with subject 'Hello'"
- "Email mom about the dinner plans"
- "Send a message to the team about tomorrow's meeting"

## Configuration Required

Before using this skill, ensure the following configuration is set:

```yaml
skills:
  email:
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    smtp_user: "your-email@gmail.com"
    smtp_password: "your-app-password"
```

## Limitations

- Only supports plain text emails (no HTML formatting)
- Attachments are not yet supported
- Only one SMTP account can be configured at a time

## Security Notes

- SMTP passwords should be stored securely
- Consider using app-specific passwords for Gmail
- Never log or display SMTP credentials