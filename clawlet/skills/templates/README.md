# Skill Templates

This directory contains templates for creating new skills. Copy and customize these templates to build your own skills.

## Available Templates

| Template | Description | Use Case |
|----------|-------------|----------|
| `basic/` | Minimal skill template | Simple skills without tools |
| `api-integration/` | API integration template | Connect to external APIs |
| `automation/` | Automation task template | Scheduled tasks, workflows |

## Quick Start

### 1. Choose a Template

```bash
# For a simple skill
cp -r clawlet/skills/templates/basic ~/.clawlet/skills/my_skill

# For an API integration
cp -r clawlet/skills/templates/api-integration ~/.clawlet/skills/my_api

# For automation tasks
cp -r clawlet/skills/templates/automation ~/.clawlet/skills/my_automation
```

### 2. Rename and Edit

```bash
cd ~/.clawlet/skills/my_skill
# Edit SKILL.md with your editor
```

### 3. Customize

Update the following in your SKILL.md:
- `name` - Unique skill identifier
- `description` - What the skill does
- `requires` - Configuration keys needed
- `tools` - Tool definitions
- Markdown content - Instructions for the agent

### 4. Test

```bash
clawlet agent --channel telegram
# Look for: "Discovered skill 'my_skill' from ..."
```

## Template Details

### Basic Template

The simplest skill template with:
- Minimal frontmatter
- Basic instructions structure
- No tools defined

Use for:
- Instruction-only skills
- Personality extensions
- Context providers

### API Integration Template

Template for connecting to external APIs:
- API key configuration
- Multiple tool definitions
- Error handling guidance
- Rate limiting considerations

Use for:
- Weather APIs
- Translation services
- Data providers
- Any external service

### Automation Template

Template for automated tasks:
- Scheduled action tools
- Task management tools
- Status reporting

Use for:
- Daily summaries
- Automated reports
- Maintenance tasks
- Workflow automation

## Best Practices

1. **Start Simple** - Begin with the basic template, add complexity as needed
2. **Clear Names** - Use descriptive, lowercase names with underscores
3. **Document Requirements** - List all required configuration in `requires`
4. **Provide Examples** - Include usage examples in the markdown content
5. **Handle Errors** - Document error scenarios and limitations

## Need Help?

- [Skills Documentation](../../../docs/skills.md) - Full documentation
- [Skills API Reference](../../../docs/skills-api.md) - Technical reference
- [Bundled Skills](../bundled/) - Example implementations