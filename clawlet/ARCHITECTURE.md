# Clawlet Architecture

_Deep dive into the core components and data flows._

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Channels (Telegram, Discord, ...)          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ inbound/outbound messages
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         MessageBus (async queues)                  │
├─────────────────────────────────────────────────────────────────────┤
│   inbound_queue  │  outbound_queue  │  max_size=1000                │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         AgentLoop                                   │
├─────────────────────────────────────────────────────────────────────┤
│  - History (RAM, capped MAX_HISTORY=100)                          │
│  - MemoryManager (persistence to MEMORY.md)                       │
│  - Storage (SQLite/Postgres for message history)                 │
│  - Provider (OpenRouter/Ollama/LMStudio)                          │
│  - Tools (registry)                                               │
│  - Circuit breaker + retry/backoff                               │
└─────────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
                ▼                               ▼
     ┌───────────────────┐       ┌────────────────────────┐
     │  LLM Provider     │       │   Storage Backend      │
     │  (OpenRouter)     │       │   (SQLite/Postgres)    │
     └───────────────────┘       └────────────────────────┘
                │                               │
                └───────────────┬───────────────┘
                                ▼
                    ┌─────────────────────────┐
                    │   Conversation History  │
                    │   (MEMORY.md + DB)      │
                    └─────────────────────────┘
```

---

## Core Components

### 1. MessageBus

Simple async queue for decoupling channels from the agent.

- `publish_inbound(msg)` – called by channels
- `consume_inbound()` – awaited by AgentLoop
- `publish_outbound(msg)` – called by agent
- `consume_outbound()` – used by channels to send replies

**Why queues?** Allows channels to run independently and buffer messages if the agent is busy.

---

### 2. AgentLoop

The heart of Clawlet. Runs a continuous loop:

1. Wait for inbound message
2. Build context (system prompt + recent history)
3. Call LLM provider (with retry/backoff + circuit breaker)
4. Detect tool calls in response
5. If tool calls: execute tools, append results, repeat (max_iterations)
6. If final response: append to history, publish outbound
7. Persist messages (storage + MEMORY.md)

**Key attributes:**

- `_history`: list of `Message` (RAM, capped at 100)
- `_session_id`: unique identifier for the current agent run (used in storage)
- `memory`: `MemoryManager` for long-term Markdown storage
- `storage`: `SQLiteStorage` or `PostgresStorage` for durable message history
- `_consecutive_errors` & `_circuit_open_until`: circuit breaker state

**Lifecycle:**

- Initialized with workspace, identity, provider, tools, storage_config
- `_initialize_storage()` called before first message or in `run()`
- `close()` performs cleanup: `memory.save_long_term()`, `storage.close()`, `provider.close()`

---

### 3. MemoryManager

Manages two tiers of memory:

- **Short-term**: `_short_term` list (kept in RAM, trimmed to `max_short_term`)
- **Long-term**: `MEMORY.md` file (Markdown, human-readable)

**Workflow:**

- `remember(key, value, category, importance)` adds to short-term
- `save_long_term()` writes selected memories to `MEMORY.md` (grouped by category)
- `recall(key)` checks short-term first, then long-term file content
- `recall_by_category(category)` returns combined memories filtered by category

**Persistence strategy:** Only messages with `importance >= threshold` are saved to avoid bloating `MEMORY.md`. Currently, all assistant messages (importance 7) and long user messages (importance boosted) are persisted.

---

### 4. Storage Backends

Abstract `StorageBackend` interface with implementations:

- `SQLiteStorage` (default): file-based, uses `aiosqlite`
- `PostgresStorage`: full PostgreSQL (not fully implemented yet)

**Schema (SQLite):**

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_messages_session ON messages(session_id, created_at DESC);
```

**Usage:**

- `store_message(session_id, role, content)` → inserts row, returns `id`
- `get_messages(session_id, limit)` → returns list of `Message` (chronological order)
- `close()` → closes DB connection

AgentLoop stores every inbound/outbound message here, enabling session reconstruction across restarts.

---

### 5. Identity & Configuration

**Identity files** (in workspace):

- `SOUL.md` – agent personality, values, tone
- `USER.md` – human preferences and context
- `MEMORY.md` – persisted memories (auto-updated)
- `HEARTBEAT.md` – scheduled periodic tasks

**Configuration** (`config.yaml`) loaded via `Config` (Pydantic). Supports:

- Provider selection (`openrouter`, `ollama`, `lmstudio`)
- Channel tokens (Telegram, Discord)
- Storage backend (sqlite/postgres)
- Agent settings (max_iterations, context_window, temperature)
- Heartbeat interval

`Config.reload()` allows hot‑reloading of configuration from the same file (preserves `config_path`).

---

### 6. Channels

Each channel implements `BaseChannel`:

- `start()` – connect to service (e.g., Telegram bot polling)
- `stop()` – disconnect
- `send(OutboundMessage)` – transmit reply

Channels publish inbound messages to the bus and consume outbound messages to send them.

---

### 7. Tools & Tool Calls

Tools are registered in `ToolRegistry`. AgentLoop detects tool calls in LLM responses via two patterns:

1. `<tool_call name="..." arguments='...'/>`
2. JSON block with `{"name": "...", "arguments": {...}}`

If tool calls found, they are executed sequentially and results appended to history. Loop continues until no more tool calls.

---

## Data Flow Example

1. User sends "What's the weather?"
2. TelegramChannel receives update → `InboundMessage` → `bus.publish_inbound()`
3. AgentLoop `consume_inbound()` → `_process_message()`
4. Add user message to `_history` + `storage.store_message()` + `memory.remember()`
5. Build context (system prompt + last 20 messages)
6. Call `provider.complete(messages)`
7. LLM returns: `<tool_call name="weather" arguments={"location":"Paris"}/>`
8. AgentLoop executes `weather` tool, gets result
9. Tool result appended to history + persisted
10. Loop continues → LLM generates final response "It's 20°C in Paris."
11. Final response appended to history + persisted, sent to `bus.publish_outbound()`
12. TelegramChannel consumes outbound → `send_message(chat_id, text)`

---

## Error Handling & Resilience

- **Retry/backoff**: on `httpx.HTTPStatusError` or `httpx.RequestError`, up to 3 attempts with exponential delay (2s, 4s, 8s).
- **Circuit breaker**: after 5 consecutive provider errors, circuit opens for 30s. All calls fail fast during open period.
- **Storage failures**: logged as warnings, agent continues (messages lost but not crashing).
- **Signal handling**: `SIGTERM`/`SIGINT` trigger graceful shutdown (`agent.close()` → save memory, close storage, close provider).

---

## Extensibility Points

- Add new channels: subclass `BaseChannel`, register in CLI
- Add new tools: create function, decorate with `@tool`, register in `ToolRegistry`
- Add new storage backends: implement `StorageBackend` abstract methods
- Custom identity: edit `SOUL.md` and `USER.md` without code changes
- Custom provider: implement `BaseProvider` (methods `complete`, `stream`, `close`)

---

## Security Considerations

- Config file checked for world-readable permissions (`chmod 600 ~/.clawlet/config.yaml`)
- Secrets masked in logs (`mask_secrets()` utility) – currently used in OpenRouter provider
- No authentication on dashboard (if enabled) – should be bound to localhost only in production
- Input validation: user messages truncated at 10 000 characters

---

## Performance Notes

- Message history loaded from storage on startup (max `MAX_HISTORY` messages)
- MemoryManager uses importance‑based filtering to keep `MEMORY.md` size manageable
- Storage operations are async (non‑blocking)
- Circuit breaker prevents thundering herd on unavailable provider

---

## Future Improvements (Out of Scope for Current Phases)

- Dashboard authentication (API key / JWT)
- Metrics endpoint (Prometheus format)
- Structured JSON logging
- Rate limiting per user
- Multi‑agent support with shared storage
- Hot‑reloading identity files (watchdog)
