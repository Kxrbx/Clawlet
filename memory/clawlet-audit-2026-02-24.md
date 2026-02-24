# 🔍 Clawlet Repository Deep Audit - Critical Issues

**Date:** 2026-02-24  
**Auditor:** Aiko (AI Mommy Helper)  
**Repository:** `/root/.openclaw/workspace/clawlet`  
**Scope:** Full codebase analysis for critical bugs, security issues, and broken functionality

---

## 📊 Executive Summary

Clawlet is a **partially implemented** AI agent framework with significant architectural gaps. While the code compiles and basic structures exist, **core functionality is broken or missing**. The most critical issue: **memory persistence is completely non-functional**.

**Risk Level:** 🔴 **HIGH** - Not production-ready without major fixes.

**Key Findings:**
- ❌ MemoryManager exists but is never instantiated → no persistence
- ❌ Dashboard API has multiple NameError bugs
- ❌ Storage backends (SQLite/PostgreSQL) are unused
- ❌ No test suite
- ⚠️ Dashboard API exposes secrets without authentication
- ⚠️ Configuration reload() method missing
- ⚠️ No dependency lockfile

---

## 🧠 1. Memory & Persistence (CRITICAL)

### Issue 1.1: MemoryManager Never Used
**File:** `clawlet/agent/memory.py`, `clawlet/agent/loop.py`  
**Severity:** 🔴 **CRITICAL** - Core feature broken

**What:** The `MemoryManager` class is fully implemented but is **never instantiated or called** by `AgentLoop`. The agent stores messages in `_history` (volatile) and discards them on restart.

**Impact:** All conversation history is lost between sessions. Long-term memory files (`MEMORY.md`) are never updated.

**Evidence:**
- `memory.py` defines `MemoryManager` with `remember()`, `save_long_term()`
- `loop.py` stores messages only in `self._history` (capped at 100)
- No import or usage of `MemoryManager` anywhere

**Fix Required:**
```python
# In AgentLoop.__init__:
self.memory = MemoryManager(workspace)

# In _process_message, after receiving user message:
self.memory.remember(key=f"msg_{len(self._history)}", value=user_message, category="conversation")

# Periodically or on shutdown:
self.memory.save_long_term()
```

---

### Issue 1.2: Storage Backends Unused
**Files:** `clawlet/storage/sqlite.py`, `clawlet/storage/postgres.py`  
**Severity:** 🔴 **CRITICAL** - Infrastructure dead code

**What:** SQLite and PostgreSQL storage implementations exist with proper schema, but are **never instantiated**.

**Impact:** No message archiving, no session recovery, no analytics.

**Fix Required:** Integrate `SQLiteStorage` or `PostgresStorage` into AgentLoop or MemoryManager.

---

## 🌐 2. Dashboard API (BROKEN)

### Issue 2.1: Undefined Global Variable `agent_process`
**File:** `clawlet/dashboard/api.py` (line 185, 203)  
**Severity:** 🔴 **CRITICAL** - Will crash on startup

**What:** The `start_agent()` endpoint uses `global agent_process` but `agent_process` is **never defined** at module level.

**Crash Scenario:**
```python
@app.post("/agent/start")
async def start_agent():
    global agent_process  # NameError: name 'agent_process' is not defined
    ...
```

**Fix:** Add at top of file (near line 80):
```python
agent_process: Optional[subprocess.Popen] = None
```

---

### Issue 2.2: NameError `cached` vs `cache`
**File:** `clawlet/dashboard/api.py` (line 306)  
**Severity:** 🔴 **CRITICAL** - Will crash when calling `/models`

**Bug:**
```python
cache = get_models_cache()
models = cache.get_models(force_refresh=force_refresh)
updated_at = cached.get("updated_at", "") if cached else ""  # NameError: 'cached' is not defined
```

**Fix:**
```python
cache_info = cache.get_cache_info() or {}
updated_at = cache_info.get("updated_at", "")
```

---

### Issue 2.3: Unused Import & Dead Code
**File:** `clawlet/dashboard/api.py` (line 302)  
**Severity:** 🟡 **MEDIUM** - Code hygiene

```python
from clawlet.providers.openrouter import OpenRouterProvider  # Never used
```

**Fix:** Remove import.

---

### Issue 2.4: Undefined `config.config_path`
**File:** `clawlet/dashboard/api.py` (line 229 in `update_config_yaml`)  
**Severity:** 🔴 **CRITICAL** - Config reload will fail

**What:** `config.reload()` is called, but the `Config` class has no `config_path` attribute. Also, `reload()` method is not defined in the Pydantic model.

**Fix:** Add `config_path: Path` field to Config class and implement `reload()` correctly.

---

### Issue 2.5: Unimplemented Endpoints (TODO)
**File:** `clawlet/dashboard/api.py` (lines 221, 337, 360)  
**Severity:** 🟡 **MEDIUM** - Incomplete features

**Endpoints with stubs:**
- `POST /agent/stop` - only sets flag, doesn't actually kill process
- `GET /logs` - returns hardcoded array
- `GET /console` - returns hardcoded array

**Fix:** Implement actual log retrieval (e.g., tail log file) and process termination.

---

## ⚙️ 3. Configuration System

### Issue 3.1: Missing `reload()` Method
**File:** `clawlet/config.py`  
**Severity:** 🔴 **CRITICAL** - Dynamic config reload broken

**What:** `api.py` calls `config.reload()`, but `Config` (Pydantic model) has no such method.

**Fix:** Add to Config class:
```python
def reload(self, path: Path) -> None:
    with open(path) as f:
        data = yaml.safe_load(f)
    self.__dict__.update(Config(**data).__dict__)
```

---

### Issue 3.2: Placeholder API Key Can Bypass Validation
**File:** `clawlet/config.py` (OpenRouterConfig validator)  
**Severity:** 🟠 **HIGH** - Security risk

**What:** The validator checks for `"YOUR_OPENROUTER_API_KEY"` but if `api_key` is `None` or empty string from YAML, the field might be `None` before validation runs, causing unclear errors.

**Fix:** Strengthen validator:
```python
@field_validator('api_key')
@classmethod
def validate_api_key(cls, v: str) -> str:
    if not v or v.strip() in ("", "YOUR_OPENROUTER_API_KEY"):
        raise ValueError("OpenRouter API key is required")
    return v.strip()
```

---

### Issue 3.3: No File Permissions Validation
**Severity:** 🟡 **MEDIUM** - Security

**What:** Config file (containing API keys) is created with default umask. No warning if permissions are too open (world-readable).

**Fix:** Check `stat` on config file and warn if `others` have read/write.

---

## 🔒 4. Security Issues

### Issue 4.1: No Authentication on Dashboard API
**File:** `clawlet/dashboard/api.py`  
**Severity:** 🔴 **CRITICAL** - Complete lack of auth

**What:** FastAPI endpoints are publicly accessible with no authentication:
- `/settings` (read/write config)
- `/config/yaml` (exposes entire config including API keys)
- `/agent/start`, `/agent/stop` (process control)
- `/logs` (potential info leak)

**Impact:** Any local user can read API keys, modify configuration, start/stop agent.

**Fix:** Add API key or JWT middleware, or bind only to localhost (127.0.0.1) by default.

---

### Issue 4.2: Config YAML Endpoint Exposes Secrets
**File:** `clawlet/dashboard/api.py` (line ~250)  
**Severity:** 🔴 **CRITICAL**

**What:** `GET /config/yaml` returns raw YAML content. If enabled over network, this exposes:
- OpenRouter API key
- Telegram/Discord tokens
- Database passwords

**Fix:** Either:
- Remove endpoint entirely
- Mask sensitive fields
- Require strong authentication

---

### Issue 4.3: Hardcoded HTTP-Referer and X-Title
**File:** `clawlet/providers/openrouter.py` (line 58-59)  
**Severity:** 🟡 **LOW** - Potential spoofing

**What:** Fixed headers `HTTP-Referer: https://clawlet.ai` and `X-Title: Clawlet` may violate OpenRouter TOS if not your actual domain/app.

**Fix:** Make these configurable or remove.

---

## 🧪 5. Testing & Quality

### Issue 5.1: Zero Test Coverage
**Severity:** 🔴 **CRITICAL**

**What:** No `tests/` directory, no pytest/unittest files. All code changes are untested.

**Impact:** High risk of regressions, unknown behavior on edge cases.

**Fix:** Create test suite:
- `tests/unit/test_memory.py`
- `tests/unit/test_config.py`
- `tests/integration/test_agent_loop.py`
- `tests/api/test_dashboard.py`

---

## 📦 6. Dependencies & Build

### Issue 6.1: No Lockfile / Requirements.txt
**Severity:** 🔴 **CRITICAL** - Reproducibility broken

**What:** Project root has **no** `requirements.txt`, `pyproject.toml`, or `Pipfile`. Dependencies are unknown.

**Impact:** Cannot install in fresh environment; version drift causes bugs.

**Fix:** Generate requirements:
```bash
pip freeze > requirements.txt
# OR create pyproject.toml with dependencies
```

---

### Issue 6.2: Missing Import in CHANNELS (Type Hints)
**File:** `clawlet/channels/__init__.py`  
**Severity:** 🟡 **MEDIUM** - Import errors possible

**What:** Likely missing re-exports for channels. Need to verify.

---

## 🏗️ 7. Architectural Issues

### Issue 7.1: Separation of Concerns Violation
**Severity:** 🟠 **HIGH**

**What:** `AgentLoop` does too much:
- Message history management
- Tool execution
- LLM calls
- Context building
- No clear boundaries

**Impact:** Hard to test, maintain, extend.

**Fix:** Split responsibilities:
- `ConversationMemory` (persistence, context)
- `LLMOrchestrator` (provider calls, tool execution loop)
- `AgentCore` (orchestrates all)

---

### Issue 7.2: No Circuit Breaker / Retry on LLM Failures
**File:** `clawlet/agent/loop.py`  
**Severity:** 🟠 **HIGH** - Availability

**What:** LLM provider errors bubble up and crash message processing. No exponential backoff, no circuit breaker.

**Fix:** Integrate `tenacity` or custom retry logic in `_process_message`.

---

### Issue 7.3: In-Memory Queues Lose Messages on Crash
**File:** `clawlet/bus/queue.py`  
**Severity:** 🟡 **MEDIUM**

**What:** `asyncio.Queue` is volatile. If agent crashes, queued outbound messages are lost.

**Fix:** Persist outbound queue to disk (SQLite) and replay on restart.

---

## 🧩 8. Feature Completeness

### Issue 8.1: Tool System Incomplete
**Files:** `clawlet/tools/`  
**Severity:** 🟡 **MEDIUM**

**What:** Tools exist (files, shell, web_search) but:
- No permission model (can run any shell command)
- No timeout enforcement on long-running tools
- No rate limiting

**Fix:** Add tool permissions config, timeouts, quotas.

---

### Issue 8.2: Identity System Static
**File:** `clawlet/agent/identity.py`  
**Severity:** 🟡 **LOW**

**What:** Identity loads static files but has no runtime updates (cannot change SOUL.md without restart).

**Fix:** Watch files for changes and reload.

---

### Issue 8.3: No Metrics/Monitoring Export
**Severity:** 🟡 **LOW**

**What:** No Prometheus metrics, no structured logging output for aggregation.

**Fix:** Add `/metrics` endpoint (Prometheus format).

---

## 🚨 9. Stability Risks

### Issue 9.1: Unbounded History Growth
**File:** `clawlet/agent/loop.py`  
**Severity:** 🟡 **MEDIUM**

**What:** `_history` list capped at 100, but no persistence. Could cause OOM if bug prevents trim.

**Fix:** Ensure `_trim_history` is called after every message.

---

### Issue 9.2: No Health Check for Agent Process
**File:** `clawlet/agent/loop.py`  
**Severity:** 🟠 **HIGH**

**What:** Dashboard `/agent/status` returns static dict, not actual agent liveness. If agent crashes, status still shows `running=True`.

**Fix:** Track actual process/thread health; update status on heartbeat.

---

### Issue 9.3: Async Client Not Closed on Errors
**File:** `clawlet/providers/openrouter.py`  
**Severity:** 🟡 **MEDIUM**

**What:** `_client` may leak if `complete()` raises before return. Should use context manager or `try/finally`.

---

## 📝 10. Documentation Gaps

- No `ARCHITECTURE.md` explaining component interactions
- No deployment guide (Dockerfile missing)
- No security hardening guide
- API endpoints not documented (Swagger exists but lacks descriptions)
- No troubleshooting guide for common errors
- No contributor guide

---

## ✅ What Actually Works

1. **Basic LLM calls** via OpenRouter/Ollama/LMStudio
2. **Telegram channel** (if token configured)
3. **Configuration loading** from YAML (with env var substitution)
4. **Onboarding wizard** (interactive setup)
5. **FastAPI dashboard** (if bugs fixed and auth added)

---

## 🛠️ Recommended Fix Priority

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| P0 | MemoryManager not used | Medium | High |
| P0 | Dashboard API NameErrors | Low | High |
| P0 | No dependency lockfile | Low | High |
| P0 | Dashboard API auth | Medium | High |
| P1 | Config reload() missing | Low | Medium |
| P1 | Storage backends unused | Medium | Medium |
| P1 | Zero test coverage | High | High |
| P2 | Unimplemented endpoints | Low | Low |
| P2 | Identity file watcher | Medium | Low |
| P3 | Metrics endpoint | Low | Low |

---

## 🔧 Quick Wins (Fix in <30 min)

1. Add `agent_process = None` global in `dashboard/api.py`
2. Fix `cached` → `cache_info` in `/models` endpoint
3. Remove unused OpenRouterProvider import
4. Generate `requirements.txt` with all deps
5. Add basic test: `test_config_loading()`

---

## 📈 Long-Term Refactoring

1. Integrate MemoryManager + Storage into AgentLoop
2. Split AgentLoop into separate concerns
3. Implement proper retry/circuit breaker
4. Add persistent message queue
5. Implement agent process supervision (PID tracking, restart)
6. Add authentication/authorization layer
7. Create Dockerfile and docker-compose.yml
8. Add logging to structured JSON format
9. Implement graceful shutdown (signal handling)
10. Add comprehensive integration tests

---

## 🎯 Bottom Line

**Clawlet is a promising skeleton but not production-grade.** It lacks:
- **Persistence** (memory, messages, configs)
- **Reliability** (crashes on common API calls)
- **Security** (no auth, secrets exposed)
- **Testability** (zero tests)
- **Observability** (no metrics, health checks superficial)

**Do not deploy** without fixing P0 issues first. The framework needs 2-4 weeks of focused engineering to be stable.

---

**End of Audit**  
**Confidence:** High (static analysis + code review)  
**Next Steps:** Prioritize P0 fixes, add tests, implement persistence.
