# Skills System Documentation

Clawlet's Skills system provides a modular way to extend agent capabilities with structured instructions and tool definitions. Skills are compatible with OpenClaw's SKILL.md format, making it easy to share and reuse skills across platforms.

## Table of Contents

- [What are Skills?](#what-are-skills)
- [SKILL.md Format Specification](#skillmd-format-specification)
- [YAML Frontmatter Fields](#yaml-frontmatter-fields)
- [Tool Definitions](#tool-definitions)
- [Creating a New Skill](#creating-a-new-skill)
- [Installing Skills](#installing-skills)
- [Configuring Skills](#configuring-skills)
- [Best Practices](#best-practices)
- [Examples](#examples)

---

## What are Skills?

Skills are modular capabilities that extend your agent's functionality. Each skill provides:

1. **Instructions** - Markdown content that guides the agent on how to use the skill
2. **Tools** - Structured function definitions the agent can call
3. **Requirements** - Configuration keys needed for the skill to work

Skills enable your agent to:
- Send emails and manage communications
- Create and manage calendar events
- Take notes and set reminders
- Integrate with external APIs
- Perform domain-specific tasks

### Skill Locations

Clawlet loads skills from three locations in priority order:

| Priority | Location | Purpose |
|----------|----------|---------|
| 1 (Highest) | `clawlet/skills/bundled/` | Bundled skills shipped with Clawlet |
| 2 | `~/.clawlet/skills/` | User-installed skills |
| 3 | `./skills/` | Project-specific skills |

Skills in higher-priority locations override those with the same name in lower-priority locations.

---

## SKILL.md Format Specification

A SKILL.md file consists of two parts:

1. **YAML Frontmatter** - Metadata and tool definitions (between `---` markers)
2. **Markdown Content** - Instructions for the agent

### Basic Structure

```markdown
---
name: skill_name
version: "1.0.0"
description: What this skill does
author: your_name
requires:
  - required_config_key
tools:
  - name: tool_name
    description: What this tool does
    parameters:
      - name: param1
        type: string
        description: Parameter description
        required: true
---

# Skill Name

Instructions for using this skill go here. This content is provided
to the agent as context when the skill is enabled.

## Usage

Detailed usage instructions...

## Examples

- Example 1
- Example 2
```

---

## YAML Frontmatter Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique skill identifier (lowercase, underscores allowed) |
| `version` | string | Semantic version (e.g., "1.0.0") |
| `description` | string | Brief description of what the skill does |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `author` | string | Skill author/maintainer |
| `requires` | list | Configuration keys required by this skill |
| `tools` | list | Tool definitions (see below) |

### Field Details

#### `name`

The skill name must be:
- Lowercase
- Use underscores for spaces (e.g., `send_email`)
- Unique across all loaded skills

```yaml
name: email  # Good
name: SendEmail  # Bad - will be lowercased
```

#### `version`

Follow semantic versioning (MAJOR.MINOR.PATCH):

```yaml
version: "1.0.0"  # Initial release
version: "1.1.0"  # New features added
version: "2.0.0"  # Breaking changes
```

#### `requires`

List of configuration keys that must be set before the skill can function:

```yaml
requires:
  - smtp_server
  - smtp_port
  - smtp_user
  - smtp_password
```

These are validated at startup and warnings are logged if missing.

---

## Tool Definitions

Tools are functions the agent can call. Each tool has a name, description, and parameters.

### Tool Structure

```yaml
tools:
  - name: send_email
    description: Send an email to one or more recipients
    parameters:
      - name: to
        type: string
        description: Recipient email address(es), comma-separated
        required: true
      - name: subject
        type: string
        description: Email subject line
        required: true
      - name: body
        type: string
        description: Email body content
        required: true
      - name: cc
        type: string
        description: CC recipients
        required: false
```

### Parameter Types

| Type | Description | Example |
|------|-------------|---------|
| `string` | Text value | `"hello@example.com"` |
| `integer` | Whole number | `42` |
| `number` | Decimal number | `3.14` |
| `boolean` | True/false | `true` |
| `array` | List of values | `["a", "b", "c"]` |
| `object` | Nested structure | `{"key": "value"}` |

### Parameter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Parameter identifier |
| `type` | string | Yes | Data type (see above) |
| `description` | string | No | Help text for the agent |
| `required` | boolean | No | Whether parameter is required (default: true) |
| `default` | any | No | Default value if not provided |
| `enum` | list | No | List of allowed values |

### Example with All Fields

```yaml
tools:
  - name: create_event
    description: Create a calendar event
    parameters:
      - name: title
        type: string
        description: Event title
        required: true
      - name: duration_minutes
        type: integer
        description: Event duration in minutes
        required: false
        default: 30
      - name: visibility
        type: string
        description: Who can see this event
        required: false
        default: "default"
        enum:
          - "default"
          - "public"
          - "private"
```

### Namespaced Tool Names

When tools are registered, they are namespaced with the skill name:

```
Skill: email
Tool: send_email
Registered name: email_send_email
```

This prevents conflicts between skills with similar tool names.

---

## Creating a New Skill

### Step 1: Create the Directory

```bash
# User skill
mkdir -p ~/.clawlet/skills/my_skill

# Or project skill
mkdir -p ./skills/my_skill
```

### Step 2: Create SKILL.md

Create a `SKILL.md` file in the directory:

```markdown
---
name: my_skill
version: "1.0.0"
description: A brief description of what this skill does
author: your_name
requires:
  - api_key  # If your skill needs configuration
tools:
  - name: do_something
    description: Perform an action
    parameters:
      - name: input
        type: string
        description: Input to process
        required: true
---

# My Skill

Detailed instructions for the agent on how to use this skill.

## When to Use

Describe scenarios where this skill should be used.

## How to Use

Step-by-step instructions for the agent.

## Examples

- "Do something with this input"
- "Process the following data"

## Limitations

Be clear about what the skill cannot do.
```

### Step 3: Test the Skill

Start Clawlet and verify the skill is loaded:

```bash
clawlet agent --channel telegram
# Look for: "Discovered skill 'my_skill' from ..."
```

---

## Installing Skills

### From a Directory

Copy the skill directory to one of the skill locations:

```bash
# Copy to user skills
cp -r /path/to/skill ~/.clawlet/skills/

# Or copy to project skills
cp -r /path/to/skill ./skills/
```

### From a Git Repository

```bash
# Clone directly into skills directory
git clone https://github.com/user/skill-name.git ~/.clawlet/skills/skill-name
```

### Directory Structure

```
~/.clawlet/skills/
  email/
    SKILL.md
  calendar/
    SKILL.md
  my_custom_skill/
    SKILL.md
```

Each skill must have its own directory with a `SKILL.md` file.

---

## Configuring Skills

### In config.yaml

Add skill configuration under the `skills` key:

```yaml
skills:
  email:
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    smtp_user: "your-email@gmail.com"
    smtp_password: "${SMTP_PASSWORD}"  # Use environment variable
  
  calendar:
    calendar_provider: "google"
    google_client_id: "${GOOGLE_CLIENT_ID}"
    google_client_secret: "${GOOGLE_CLIENT_SECRET}"
```

### Environment Variables

Use `${VAR_NAME}` syntax to reference environment variables:

```yaml
skills:
  email:
    smtp_password: "${SMTP_PASSWORD}"
```

Then set the environment variable:

```bash
export SMTP_PASSWORD="your-app-password"
```

### Validating Configuration

Check if all requirements are met:

```bash
clawlet validate
```

This will report any missing skill configuration.

---

## Best Practices

### 1. Clear Descriptions

Write clear, concise descriptions for tools and parameters:

```yaml
# Good
description: Send an email to one or more recipients

# Bad
description: Sends email
```

### 2. Comprehensive Instructions

The markdown content should guide the agent thoroughly:

```markdown
# Email Skill

## When to Use
Use this skill when the user asks to send, draft, or manage emails.

## Workflow
1. Confirm recipient address
2. Ask for subject if not provided
3. Ask for body content
4. Send using the send_email tool

## Examples
- "Send an email to john@example.com"
- "Email mom about dinner plans"
```

### 3. Minimal Requirements

Only require configuration that is truly essential:

```yaml
# Good - only essential config
requires:
  - api_key

# Bad - too many requirements
requires:
  - api_key
  - api_url
  - timeout
  - retry_count
```

### 4. Sensible Defaults

Provide defaults for optional parameters:

```yaml
parameters:
  - name: limit
    type: integer
    description: Maximum results to return
    required: false
    default: 10
```

### 5. Enum for Choices

Use enum for parameters with fixed options:

```yaml
parameters:
  - name: format
    type: string
    description: Output format
    required: false
    default: "json"
    enum:
      - "json"
      - "xml"
      - "csv"
```

### 6. Document Limitations

Be upfront about what the skill cannot do:

```markdown
## Limitations

- Only plain text emails (no HTML)
- Attachments not supported
- Maximum 100 recipients per email
```

### 7. Security Notes

Include security guidance when relevant:

```markdown
## Security Notes

- Use app-specific passwords for Gmail
- Never log or display credentials
- Validate recipient addresses before sending
```

---

## Examples

### Minimal Skill (No Tools)

```markdown
---
name: greeter
version: "1.0.0"
description: Provides friendly greeting capabilities
author: clawlet
requires: []
tools: []
---

# Greeter Skill

This skill helps the agent provide warm, personalized greetings.

## Guidelines

- Use the user's name when known
- Consider the time of day
- Be genuine and warm
```

### API Integration Skill

```markdown
---
name: weather
version: "1.0.0"
description: Get current weather information
author: clawlet
requires:
  - weather_api_key
tools:
  - name: get_weather
    description: Get current weather for a location
    parameters:
      - name: location
        type: string
        description: City name or zip code
        required: true
      - name: units
        type: string
        description: Temperature units
        required: false
        default: "celsius"
        enum:
          - "celsius"
          - "fahrenheit"
---

# Weather Skill

Get current weather information for any location.

## Usage

Use `get_weather` when the user asks about weather conditions.

## Examples

- "What's the weather in Paris?"
- "Is it raining in London?"
- "Temperature in New York in Fahrenheit"

## Configuration

```yaml
skills:
  weather:
    weather_api_key: "${WEATHER_API_KEY}"
```

Get an API key from OpenWeatherMap.
```

### Automation Skill

```markdown
---
name: reminders
version: "1.0.0"
description: Create and manage reminders
author: clawlet
requires: []
tools:
  - name: create_reminder
    description: Create a new reminder
    parameters:
      - name: message
        type: string
        description: Reminder message
        required: true
      - name: remind_at
        type: string
        description: When to remind (ISO 8601 or natural language)
        required: true
  - name: list_reminders
    description: List all pending reminders
    parameters:
      - name: limit
        type: integer
        description: Maximum number to return
        required: false
        default: 10
  - name: delete_reminder
    description: Delete a reminder
    parameters:
      - name: reminder_id
        type: string
        description: ID of reminder to delete
        required: true
---

# Reminders Skill

Manage time-based reminders for the user.

## Tools

1. `create_reminder` - Set a new reminder
2. `list_reminders` - View pending reminders
3. `delete_reminder` - Remove a reminder

## Time Formats

The `remind_at` parameter accepts:
- ISO 8601: "2024-01-15T15:30:00"
- Natural: "tomorrow at 3pm"
- Relative: "in 2 hours"

## Examples

- "Remind me to call mom tomorrow at 5pm"
- "Set a reminder for the meeting in 1 hour"
- "What reminders do I have?"
```

---

## Bundled Skills

Clawlet includes several bundled skills:

| Skill | Description |
|-------|-------------|
| `email` | Send and manage emails |
| `calendar` | Manage calendar events |
| `notes` | Create and organize notes |

These are located in `clawlet/skills/bundled/` and are loaded automatically.

---

## Troubleshooting

### Skill Not Loading

1. Check the directory structure: `skill_name/SKILL.md`
2. Validate YAML syntax in frontmatter
3. Check logs for parsing errors

### Tools Not Appearing

1. Ensure the skill is enabled
2. Check for configuration requirements
3. Verify tool definitions are valid

### Configuration Errors

Run validation to identify missing requirements:

```bash
clawlet validate
```

---

## See Also

- [Skills API Reference](skills-api.md) - Technical documentation for developers
- [Scheduling Documentation](scheduling.md) - Schedule skill-based tasks
- [Quick Start Guide](../QUICKSTART.md) - Get started with Clawlet