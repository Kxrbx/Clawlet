---
name: api_service
version: "1.0.0"
description: Integrate with [API_NAME] to [DESCRIPTION_OF_WHAT_IT_DOES]
author: your_name
requires:
  - api_key
  # - api_base_url  # Uncomment if needed
  # - api_timeout   # Uncomment if needed
tools:
  - name: get_data
    description: Retrieve data from the API
    parameters:
      - name: query
        type: string
        description: Search query or identifier
        required: true
      - name: limit
        type: integer
        description: Maximum number of results to return
        required: false
        default: 10
  - name: send_request
    description: Send a request to the API
    parameters:
      - name: endpoint
        type: string
        description: API endpoint to call
        required: true
      - name: method
        type: string
        description: HTTP method
        required: false
        default: "GET"
        enum:
          - "GET"
          - "POST"
          - "PUT"
          - "DELETE"
      - name: data
        type: object
        description: Request body data (for POST/PUT)
        required: false
---

# API Service Skill

This skill enables the agent to interact with [API_NAME].

## Overview

Brief description of the API and its capabilities:
- Capability 1
- Capability 2
- Capability 3

## Configuration

Before using this skill, configure it in your `config.yaml`:

```yaml
skills:
  api_service:
    api_key: "${API_SERVICE_KEY}"
    # api_base_url: "https://api.example.com"  # Optional custom URL
    # api_timeout: 30  # Optional timeout in seconds
```

Set the environment variable:
```bash
export API_SERVICE_KEY="your-api-key"
```

## Available Tools

### get_data

Use this tool to retrieve data from the API.

**Parameters:**
- `query` (required): The search query or identifier
- `limit` (optional): Maximum results (default: 10)

**Example:**
```
User: "Search for X in the API"
Agent: Uses get_data with query="X"
```

### send_request

Use this tool for advanced API operations.

**Parameters:**
- `endpoint` (required): API endpoint path
- `method` (optional): HTTP method (default: "GET")
- `data` (optional): Request body for POST/PUT

**Example:**
```
User: "Create a new resource with these properties"
Agent: Uses send_request with method="POST" and data={...}
```

## Usage Guidelines

1. **Authentication**: The API key is automatically included in requests
2. **Rate Limiting**: Be aware of API rate limits (X requests per minute)
3. **Error Handling**: Check for error responses and inform the user
4. **Data Validation**: Validate user input before sending to the API

## Examples

### Example 1: Basic Search
```
User: "Find information about X"
Agent: I'll search for that using the API.
[Calls get_data with query="X"]
Agent: Here's what I found: [results]
```

### Example 2: Creating a Resource
```
User: "Create a new entry with name 'Test' and value 123"
Agent: I'll create that entry for you.
[Calls send_request with method="POST", data={"name": "Test", "value": 123}]
Agent: Created successfully! The ID is [id].
```

### Example 3: Updating Data
```
User: "Update entry 456 to have value 789"
Agent: I'll update that entry.
[Calls send_request with endpoint="/entries/456", method="PUT", data={"value": 789}]
Agent: Entry 456 has been updated.
```

## Error Handling

Common errors and how to handle them:

| Error | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | Invalid API key | Check configuration |
| 429 Too Many Requests | Rate limit exceeded | Wait and retry |
| 404 Not Found | Resource doesn't exist | Verify the ID/query |
| 500 Server Error | API issue | Try again later |

## Limitations

- Maximum X requests per minute
- Response size limited to X MB
- Certain endpoints may require additional permissions
- [Any other limitations]

## Security Notes

- API keys are sensitive - never log or display them
- Use environment variables for credentials
- Validate user input to prevent injection
- Use HTTPS for all requests