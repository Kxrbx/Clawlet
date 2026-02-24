---
name: notes
version: 1.0.0
description: Create and manage personal notes and reminders
author: clawlet
requires: []
tools:
  - name: create_note
    description: Create a new note
    parameters:
      - name: title
        type: string
        description: Note title
        required: true
      - name: content
        type: string
        description: Note content/body
        required: true
      - name: tags
        type: string
        description: Comma-separated tags for organization
        required: false
      - name: folder
        type: string
        description: Folder to store the note in
        required: false
        default: "default"
  - name: list_notes
    description: List notes with optional filtering
    parameters:
      - name: tags
        type: string
        description: Filter by tags (comma-separated)
        required: false
      - name: folder
        type: string
        description: Filter by folder
        required: false
      - name: search
        type: string
        description: Search query for title/content
        required: false
      - name: limit
        type: integer
        description: Maximum number of notes to return
        required: false
        default: 20
  - name: get_note
    description: Get a specific note by ID
    parameters:
      - name: note_id
        type: string
        description: ID of the note to retrieve
        required: true
  - name: update_note
    description: Update an existing note
    parameters:
      - name: note_id
        type: string
        description: ID of the note to update
        required: true
      - name: title
        type: string
        description: New title (optional)
        required: false
      - name: content
        type: string
        description: New content (optional)
        required: false
      - name: append
        type: boolean
        description: If true, append content instead of replacing
        required: false
        default: false
      - name: tags
        type: string
        description: New tags (comma-separated, optional)
        required: false
  - name: delete_note
    description: Delete a note
    parameters:
      - name: note_id
        type: string
        description: ID of the note to delete
        required: true
  - name: create_reminder
    description: Create a reminder linked to a note
    parameters:
      - name: note_id
        type: string
        description: ID of the note to link (optional)
        required: false
      - name: message
        type: string
        description: Reminder message
        required: true
      - name: remind_at
        type: string
        description: When to remind (ISO 8601 or natural language like 'tomorrow at 3pm')
        required: true
---

# Notes Skill

Use this skill to create and manage personal notes and reminders.

## Usage

This skill helps users capture and organize information quickly:

1. `create_note` - Capture new information
2. `list_notes` - Find existing notes
3. `get_note` - Read a specific note
4. `update_note` - Modify existing notes
5. `delete_note` - Remove notes
6. `create_reminder` - Set time-based reminders

## Examples

- "Note that the WiFi password is 'hunter2'"
- "Create a note about the meeting agenda"
- "What notes do I have about the project?"
- "Remind me to call mom tomorrow at 5pm"
- "Add to my shopping list note: milk and eggs"

## Organization

Notes can be organized using:

- **Folders**: Group related notes together
- **Tags**: Add labels for cross-cutting concerns
- **Search**: Find notes by content or title

## Default Behavior

- Notes without a specified folder go to "default"
- Tags are optional but recommended
- Search is case-insensitive

## Tips

- Use descriptive titles for easier searching
- Tag notes with relevant topics
- Use folders for project-specific notes
- Link reminders to notes for context

## Limitations

- No rich text formatting (plain text only)
- No inline images or attachments
- Maximum note size: 64KB
- Reminders require the agent to be running at the specified time