# Adding New LLM Providers to Clawlet

## Overview

This document outlines the implementation plan for adding new LLM providers to Clawlet, expanding beyond the current three providers (OpenRouter, Ollama, LMStudio).

## Provider System Architecture

```mermaid
graph TB
    subgraph Configuration
        C[config.py] --> PC[ProviderConfig]
    end
    
    subgraph Providers
        OR[openrouter.py]
        OL[ollama.py]
        LS[lmstudio.py]
    end
    
    subgraph Factory
        PI[providers/__init__.py]
    end
    
    subgraph CLI
        CLI[cli/onboard.py]
    end
    
    PI --> OR
    PI --> OL
    PI --> LS
    CLI --> PI
```

## Complete Provider List (16 Total)

### Existing Providers (3)
| Provider | Type | API | Default Model |
|----------|------|-----|---------------|
| OpenRouter | Cloud | OpenAI-compatible | anthropic/claude-sonnet-4 |
| Ollama | Local | Ollama API | llama3.2 |
| LMStudio | Local | OpenAI-compatible | local-model |

### New Providers (13)

| # | Provider | Auth | Default Model | Format |
|---|----------|------|---------------|--------|
| 1 | **OpenAI** | API Key + OAuth | gpt-5 | OpenAI-compatible |
| 2 | **Anthropic** | API Key | claude-sonnet-5-20260203 | Anthropic API |
| 3 | **MiniMax** | API Key | abab7-preview | OpenAI-compatible |
| 4 | **Moonshot AI** | API Key | kimi-k2.5 | OpenAI-compatible |
| 5 | **Google** | API Key | gemini-3-pro | Google REST |
| 6 | **Qwen** | API Key | qwen4 | OpenAI-compatible |
| 7 | **Z.AI (GLM)** | API Key | glm-5 | OpenAI-compatible |
| 8 | **Copilot** | OAuth | gpt-4.2 | GitHub API |
| 9 | **Vercel AI Gateway** | API Key | openai/gpt-5 | Gateway (OpenAI) |
| 10 | **OpenCode Zen** | API Key | zen-3.0 | OpenAI-compatible |
| 11 | **Xiaomi** | API Key | mi-agent-2 | Custom |
| 12 | **Synthetic** | API Key | synthetic-llm-2 | OpenAI-compatible |
| 13 | **Venice AI** | API Key | venice-llama-4 | OpenAI-compatible |

---

## Detailed Model Lists by Provider (February 2026)

### 1. OpenAI

**API**: https://api.openai.com/v1

**Models**:
```python
OPENAI_MODELS = [
    # GPT-5 Series (Latest - February 2026)
    "gpt-5",                        # Default - Latest flagship
    "gpt-5-20260215",
    "gpt-5-thinking",
    "gpt-5-mini",
    
    # GPT-4.5 Series
    "gpt-4.5-preview",
    "gpt-4.5",
    "gpt-4.5-20260201",
    
    # GPT-4o Series
    "gpt-4o",
    "gpt-4o-2024-05-13",
    "gpt-4o-2024-08-06",
    "gpt-4o-2024-11-20",
    "gpt-4o-2025-01-29",
    "gpt-4o-mini",
    "gpt-4o-mini-2024-07-18",
    "gpt-4o-mini-2025-01-29",
    
    # GPT-4 Series
    "gpt-4-turbo",
    "gpt-4-turbo-2024-04-09",
    "gpt-4-1106-preview",
    "gpt-4-0125-preview",
    
    # o-Series (Reasoning)
    "o3",
    "o3-20260201",
    "o3-mini",
    "o3-mini-2025-01-31",
    "o1",
    "o1-2024-12-17",
    "o1-mini",
    "o1-mini-2024-09-12",
    
    # Embeddings
    "text-embedding-4",
    "text-embedding-3-small",
    "text-embedding-3-large",
]
```

**Default**: `gpt-5`

---

### 2. Anthropic

**API**: https://api.anthropic.com/v1

**Models**:
```python
ANTHROPIC_MODELS = [
    # Claude 5 Series (Latest - February 2026)
    "claude-sonnet-5-20260203",      # Default - Fennec, released Feb 3, 2026
    "claude-opus-5-20260201",
    "claude-haiku-5-20260215",
    
    # Claude 4 Series (2025)
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-4-5-20250619",
    "claude-opus-4-20250520",
    "claude-haiku-4-20250501",
    
    # Claude 3.5 Series (Legacy - retired Oct 2025)
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20240620",
    
    # Claude 3 Series (Legacy)
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]
```

**Default**: `claude-sonnet-5-20260203`

---

### 3. MiniMax

**API**: https://api.minimax.chat/v1

**Models**:
```python
MINIMAX_MODELS = [
    # abab7 Series (Latest - February 2026)
    "abab7-preview",              # Default - Enhanced long text, math, writing
    "abab7-chat",
    "abab7-thinking",
    "abab7-mini",
    
    # M2.5 Series (February 2026)
    "minimax-m2.5",
    "minimax-m2.5-thinking",
    
    # abab6 Series
    "abab6.5s-chat",
    "abab6.5-chat",
    "abab6-chat",
    "abab6-thinking",
    
    # Multimodal
    "abab7-video",
    "abab7-speech",
    "abab6.5",
]
v-chat```

**Default**: `abab7-preview`

---

### 4. Moonshot AI (Kimi)

**API**: https://api.moonshot.ai/v1

**Models**:
```python
MOONSHOT_MODELS = [
    # Kimi K2/K2.5 Series (Latest - January 2026)
    "kimi-k2.5",                  # Default - 1T parameter MoE, agent swarms
    "kimi-k2.5-thinking",
    "kimi-k2.5-open",
    "kimi-k2",
    
    # Kimi K1/K1.5 Series
    "kimi-k1.5-long-thinking-chat",
    "kimi-k1.5-chat",
    "kimi-k1.5-long-context-chat",
    "kimi-k1-thinking",
    
    # Kimi Linear (Upcoming)
    "kimi-linear",
    
    # Legacy Kimi Series
    "kimi-vl-next-chat",
    "kimi-vl-a3b-chat",
    "moonshot-v1-128k",
    "moonshot-v1-32k",
    "moonshot-v1-8k",
]
```

**Default**: `kimi-k2.5`

---

### 5. Google Gemini

**API**: https://generativelanguage.googleapis.com/v1beta

**Models**:
```python
GOOGLE_MODELS = [
    # Gemini 4 Series (Latest - February 2026)
    "gemini-4-pro",              # Default - Latest flagship
    "gemini-4-flash",
    "gemini-4-thinking",
    
    # Gemini 3 Series (December 2025)
    "gemini-3-pro",
    "gemini-3-flash",
    "gemini-3-thinking",
    
    # Gemini 2.5 Series (Legacy - 2025)
    "gemini-2.5-pro-preview-06-05",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    
    # Gemini 3 Deep Think (December 2025)
    "gemini-3-deep-think",
]
```

**Default**: `gemini-4-pro`

---

### 6. Qwen (Alibaba)

**API**: https://dashscope.aliyuncs.com/compatible-mode/v1

**Models**:
```python
QWEN_MODELS = [
    # Qwen4 Series (Latest - February 2026)
    "qwen4",                     # Default - Latest flagship
    "qwen4-thinking",
    "qwen4-mini",
    "qwen4-longcontext",
    
    # Qwen3 Series
    "qwen3-235b-a22b",
    "qwen3-30b-a3b",
    "qwen3-8b",
    "qwen3-4b",
    "qwen3-1.5b",
    "qwen3-0.5b",
    
    # Qwen3 Thinking Models
    "qwen3-30b-a3b-thinking",
    "qwen3-8b-thinking",
    
    # Qwen3 Omni (Multimodal)
    "qwen3-omni-flash-2025-12-01",
    "qwen3-omni-flash-2025-09-15",
    
    # Qwen2.5 Series
    "qwen2.5-72b-instruct",
    "qwen2.5-32b-instruct",
    "qwen2.5-14b-instruct",
    "qwen2.5-7b-instruct",
    "qwen2.5-3b-instruct",
    
    # Qwen Plus/Turbo (Legacy)
    "qwen-plus",
    "qwen-plus-latest",
    "qwen-turbo",
]
```

**Default**: `qwen4`

---

### 7. Z.AI (GLM)

**API**: https://open.bigmodel.cn/api/paas/v4

**Models**:
```python
ZAI_MODELS = [
    # GLM-5 Series (Latest - February 11, 2026)
    "glm-5",                     # Default - 745B params, enhanced coding
    "glm-5-alltools",
    "glm-5-thinking",
    "glm-5-plus",
    "glm-5-air",
    "glm-5-airx",
    
    # GLM-4 Series
    "glm-4.7",
    "glm-4.7-alltools",
    "glm-4.7-thinking",
    "glm-4.7-plus",
    "glm-4.7-air",
    "glm-4-airx",
    
    # GLM-4V (Vision)
    "glm-5v",
    "glm-5v-plus",
    
    # GLM 3 Turbo
    "glm-3-turbo",
    "glm-3-turbo-chat",
]
```

**Default**: `glm-5`

---

### 8. GitHub Copilot

**API**: https://api.github.com/copilot

**Models**:
```python
COPILOT_MODELS = [
    # GPT-4.2 Series (Latest - February 2026)
    "gpt-4.2",
    "gpt-4.2-mini",
    "gpt-4.2-thinking",
    
    # GPT-4.1 Series
    "gpt-4.1",
    "gpt-4.1-2025-01-29",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    
    # GPT-4o Series
    "gpt-4o",
    "gpt-4o-mini",
    
    # Claude 5 Series (February 2026)
    "claude-sonnet-5-20260203",
    "claude-haiku-5-20260215",
    
    # Claude 4 Series
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-20250520",
    
    # Gemini 4 Series
    "gemini-4-pro",
    "gemini-3-flash",
    
    # Azure Models
    "azure/gpt-5",
    "azure/gpt-4o",
]
```

**Default**: `gpt-4.2`

---

### 9. Vercel AI Gateway

**API**: https://gateway.ai.cloudflare.com/v1

**Models** (Unified across 100+ providers):
```python
VERCEL_MODELS = [
    # OpenAI Models
    "openai/gpt-5",
    "openai/gpt-5-mini",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/o3",
    "openai/o3-mini",
    
    # Anthropic Models
    "anthropic/claude-sonnet-5-20260203",
    "anthropic/claude-opus-5-20260201",
    "anthropic/claude-haiku-5-20260215",
    
    # Google Models
    "google/gemini-4-pro",
    "google/gemini-3-pro",
    
    # Meta Llama 4 Series
    "meta/llama-4-scout",
    "meta/llama-4-maverick",
    
    # Llama 3 Series
    "meta/llama-3.1-405b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3-70b-instruct",
    "meta/llama-3-8b-instruct",
    
    # Mistral Models
    "mistral/mistral-large",
    "mistral/mistral-small",
    "mistral/mistral-3",
    
    # DeepSeek Models
    "deepseek/deepseek-r1",
    "deepseek/deepseek-v3",
    
    # Cohere Models
    "cohere/command-r-plus",
    "cohere/command-r",
]
```

**Default**: `openai/gpt-5`

---

### 10. OpenCode Zen

**API**: https://api.opencode.ai/v1

**Models**:
```python
OPENCODE_ZEN_MODELS = [
    "zen-3.0",                   # Default - Latest
    "zen-3.0-thinking",
    "zen-2.5",
    "zen-2.5-thinking",
    "zen-2.0",
    "zen-code",
]
```

**Default**: `zen-3.0`

---

### 11. Xiaomi

**API**: https://api.xiaomi.com/v1

**Models**:
```python
XIAOMI_MODELS = [
    "mi-agent-2",               # Default - Latest
    "mi-agent-2-thinking",
    "mi-agent-1",
    "mi-mini",
    "mi-mini-thinking",
]
```

**Default**: `mi-agent-2`

---

### 12. Synthetic

**API**: https://api.synthetic.ai/v1

**Models**:
```python
SYNTHETIC_MODELS = [
    # Llama 4 Series
    "meta-llama/llama-4-scout",
    "meta-llama/llama-4-maverick",
    
    # Llama 3 Series
    "meta-llama/llama-3.1-405b-instruct",
    "meta-llama/llama-3.1-70b-instruct",
    "meta-llama/llama-3-70b-instruct",
    "meta-llama/llama-3-8b-instruct",
    
    # DeepSeek Series
    "deepseek/deepseek-r1",
    "deepseek/deepseek-v3",
    
    # Mistral Series
    "mistral/mistral-large",
    "mistral/mistral-3",
    
    # Qwen4 Series
    "qwen/qwen4",
    "qwen/qwen4-mini",
    
    # Default
    "synthetic-llm-2",
    "synthetic-llm",
]
```

**Default**: `synthetic-llm-2`

---

### 13. Venice AI

**API**: https://api.venice.ai/api/v1

**Models**:
```python
VENICE_MODELS = [
    # Llama 4 Series (Latest - February 2026)
    "venice-llama-4",            # Default - Latest
    "venice-llama-4-thinking",
    "venice-llama-4-maverick",
    
    # Llama 3 Series
    "llama-3.1-405b-venice-edition",
    "llama-3.3-70b-venice-edition",
    "llama-3-70b-instruct",
    "llama-3-8b-instruct",
    
    # Dolphin Mistral
    "dolphin-mistral-24b-venice-edition",
    
    # DeepSeek
    "deepseek-r1-venice",
    "deepseek-v3-venice",
    
    # Qwen
    "qwen-4-venice",
    
    # Reasoning
    "venice-reasoning-2",
    "venice-reasoning",
    
    # Vision
    "venice-vision-2",
    "venice-vision",
    
    # Default (Uncensored)
    "venice-uncensored",
    "venice-uncensored-2",
]
```

**Default**: `venice-llama-4`

---

## Implementation Plan

### Phase 1: Configuration & Factory (Week 1)

#### 1.1 Update `clawlet/config.py`

Add 13 new Pydantic config classes with model defaults.

#### 1.2 Update `clawlet/providers/__init__.py`

Add 13 new factory functions for lazy loading.

### Phase 2: Provider Implementations (Weeks 1-2)

Create 13 new provider files with:
- `complete()` method
- `stream()` method
- `list_models()` method
- Default model constants

### Phase 3: CLI Onboarding (Week 2)

Update `clawlet/cli/onboard.py`:
- Expand provider menu to 16 options
- Add provider-specific configuration prompts
- Include model selection with smart defaults

## File Changes Summary

| File | Changes |
|------|---------|
| `clawlet/config.py` | Add 13 config classes, update ProviderConfig |
| `clawlet/providers/__init__.py` | Add 13 factory functions |
| `clawlet/providers/openai.py` | New - OpenAI provider |
| `clawlet/providers/anthropic.py` | New - Anthropic provider |
| `clawlet/providers/minimax.py` | New - MiniMax provider |
| `clawlet/providers/moonshot.py` | New - Moonshot AI provider |
| `clawlet/providers/google.py` | New - Google Gemini provider |
| `clawlet/providers/qwen.py` | New - Qwen provider |
| `clawlet/providers/zai.py` | New - Z.AI GLM provider |
| `clawlet/providers/copilot.py` | New - GitHub Copilot provider |
| `clawlet/providers/vercel.py` | New - Vercel AI Gateway provider |
| `clawlet/providers/opencode_zen.py` | New - OpenCode Zen provider |
| `clawlet/providers/xiaomi.py` | New - Xiaomi provider |
| `clawlet/providers/synthetic.py` | New - Synthetic provider |
| `clawlet/providers/venice.py` | New - Venice AI provider |
| `clawlet/cli/onboard.py` | Expand to 16 providers |

## Environment Variables

```bash
# Cloud Providers
OPENAI_API_KEY
ANTHROPIC_API_KEY
MINIMAX_API_KEY
MOONSHOT_API_KEY
GOOGLE_API_KEY
QWEN_API_KEY
ZAI_API_KEY
COPILOT_ACCESS_TOKEN
VERCEL_API_KEY
OPENCODE_ZEN_API_KEY
XIAOMI_API_KEY
SYNTHETIC_API_KEY
VENICE_API_KEY
```

## Key 2026 Model Releases Summary

| Provider | Latest Model | Release Date |
|----------|--------------|--------------|
| OpenAI | GPT-5 | February 2026 |
| Anthropic | Claude Sonnet 5 | February 3, 2026 |
| MiniMax | abab7, M2.5 | February 2026 |
| Moonshot AI | Kimi K2.5 | January 2026 |
| Google | Gemini 4 | February 2026 |
| Qwen | Qwen4 | February 2026 |
| Z.AI | GLM-5 | February 11, 2026 |
| GitHub Copilot | GPT-4.2 | February 2026 |
| Meta | Llama 4 Scout/Maverick | Early 2026 |
