---
name: calendar
version: 1.0.0
description: Manage calendar events and schedules
author: clawlet
requires:
  - calendar_provider
tools:
  - name: create_event
    description: Create a new calendar event
    parameters:
      - name: title
        type: string
        description: Event title/summary
        required: true
      - name: start_time
        type: string
        description: Event start time in ISO 8601 format (e.g., 2024-01-15T10:00:00)
        required: true
      - name: end_time
        type: string
        description: Event end time in ISO 8601 format
        required: true
      - name: description
        type: string
        description: Event description/notes
        required: false
      - name: location
        type: string
        description: Event location
        required: false
      - name: attendees
        type: string
        description: Attendee email addresses, comma-separated
        required: false
      - name: reminder_minutes
        type: integer
        description: Reminder time in minutes before event
        required: false
        default: 15
  - name: list_events
    description: List calendar events for a date range
    parameters:
      - name: start_date
        type: string
        description: Start date in YYYY-MM-DD format
        required: true
      - name: end_date
        type: string
        description: End date in YYYY-MM-DD format
        required: false
      - name: limit
        type: integer
        description: Maximum number of events to return
        required: false
        default: 20
  - name: delete_event
    description: Delete a calendar event
    parameters:
      - name: event_id
        type: string
        description: ID of the event to delete
        required: true
  - name: find_free_time
    description: Find available time slots in a date range
    parameters:
      - name: date
        type: string
        description: Date to search in YYYY-MM-DD format
        required: true
      - name: duration_minutes
        type: integer
        description: Required duration in minutes
        required: true
      - name: working_hours_start
        type: string
        description: Start of working hours (HH:MM format)
        required: false
        default: "09:00"
      - name: working_hours_end
        type: string
        description: End of working hours (HH:MM format)
        required: false
        default: "17:00"
---

# Calendar Skill

Use this skill to manage calendar events and schedules on behalf of the user.

## Usage

When the user asks you to schedule something, use the appropriate tool:

1. `create_event` - Create new events
2. `list_events` - View upcoming events
3. `delete_event` - Remove events
4. `find_free_time` - Find available time slots

## Examples

- "Schedule a meeting with John tomorrow at 2pm"
- "What's on my calendar next week?"
- "Find a 30-minute slot for a call on Friday"
- "Cancel my 3pm meeting"

## Configuration Required

Before using this skill, ensure the following configuration is set:

```yaml
skills:
  calendar:
    calendar_provider: "google"  # or "outlook", "caldav"
    # Provider-specific settings:
    google_client_id: "your-client-id"
    google_client_secret: "your-client-secret"
```

## Date/Time Handling

- All times should be in ISO 8601 format
- Dates should be in YYYY-MM-DD format
- The skill will use the user's configured timezone

## Limitations

- Recurring events are not yet fully supported
- Maximum 100 attendees per event
- Free time search only considers working hours by default

## Tips

- Always confirm event details before creating
- Suggest times based on free time search
- Include relevant details in event descriptions