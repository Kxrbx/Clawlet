"""Tool-call pipeline for the agent loop: parsing, repair, execution, targeting.

Behavior-only mixin: all state lives on :class:`~clawlet.agent.loop.AgentLoop`
(tool registry, aliases, circuit-breaker buckets, http context, runtime policy)
and the PLACEHOLDER_PATTERNS / URL_PATTERN class constants are read via ``self``.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from loguru import logger

from clawlet.agent.models import Message, ToolCall
from clawlet.metrics import get_metrics
from clawlet.providers.base import LLMResponse
from clawlet.tools.registry import ToolResult, validate_tool_params
from clawlet.runtime import ToolCallEnvelope
from clawlet.workspace_layout import get_workspace_layout

UTC_TZ = timezone.utc


class ToolPipelineMixin:
    """From raw model output to executed tool results."""

    # ------------------------------------------------------------------
    # URL fetch targeting
    # ------------------------------------------------------------------

    def _extract_explicit_urls(self, user_message: str) -> list[str]:
        """Extract normalized explicit URLs from user message."""
        urls: list[str] = []
        seen: set[str] = set()
        for raw in self.URL_PATTERN.findall(user_message or ""):
            candidate = raw.rstrip("`.,);!?'\"")
            if not candidate:
                continue
            lowered = candidate.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            urls.append(candidate)
        return urls

    def _prioritize_explicit_url_fetch(
        self,
        tool_calls: list[ToolCall],
        explicit_urls: list[str],
        tool_calls_used: int,
    ) -> list[ToolCall]:
        """Force URL fetch first for explicit-link requests on the first tool step."""
        if not tool_calls or not explicit_urls or tool_calls_used > 0:
            return tool_calls
        if self._is_authenticated_api_url(explicit_urls[0]):
            return tool_calls
        if self.tools.get("fetch_url") is None:
            return tool_calls

        wanted = {u.lower() for u in explicit_urls}
        for tc in tool_calls:
            mapped_name = self._tool_aliases.get(tc.name, tc.name)
            if mapped_name != "fetch_url":
                continue
            arg_url = str((tc.arguments or {}).get("url", "")).strip().lower()
            if arg_url and arg_url in wanted:
                return tool_calls

        forced = ToolCall(
            id="forced_fetch_url_first",
            name="fetch_url",
            arguments={"url": explicit_urls[0]},
        )
        logger.info(
            f"Applying URL-first policy: forcing fetch_url for explicit URL {explicit_urls[0]}"
        )
        return [forced]

    @staticmethod
    def _is_authenticated_api_url(url: str) -> bool:
        lowered = (url or "").strip().lower()
        return "/api/" in lowered

    # ------------------------------------------------------------------
    # Guided external-action targeting
    # ------------------------------------------------------------------

    def _is_action_oriented_request(self, user_message: str, is_heartbeat: bool) -> bool:
        if is_heartbeat:
            return True
        lowered = (user_message or "").strip().lower()
        action_markers = (
            "introduce yourself",
            "engage with others",
            "engage ",
            "post ",
            "comment ",
            "reply ",
            "perform",
            "do it",
            "check moltbook",
            "heartbeat check",
            "update your credentials",
            "update the api key",
            "introduce yourself on",
        )
        return any(marker in lowered for marker in action_markers)

    def _is_guided_external_action_mission(self, user_message: str, is_heartbeat: bool) -> bool:
        if is_heartbeat:
            return True
        lowered = (user_message or "").strip().lower()
        cues = (
            "engage with others",
            "engage ",
            "engage with",
            "reply to others",
            "reply to",
            "comment on posts",
            "post something",
            "check notifications",
            "social",
            "interact with",
            "do whatever you want",
        )
        return any(cue in lowered for cue in cues)

    def _guided_next_tool_call(
        self,
        *,
        user_message: str,
        is_heartbeat: bool,
        tool_calls_used: int,
    ) -> Optional[ToolCall]:
        if not self._is_guided_external_action_mission(user_message, is_heartbeat):
            return None

        if not self._recent_http_context:
            return None

        latest_key = str(self._recent_http_context.get("_latest_host") or "").strip().lower()
        if not latest_key:
            return None
        bucket = self._recent_http_context.get(latest_key) or {}
        if not isinstance(bucket, dict):
            return None

        fetched_urls = {str(url).strip() for url in list(bucket.get("fetched_urls") or []) if str(url).strip()}
        quick_links = dict(bucket.get("quick_links") or {})
        suggestions = list(bucket.get("suggested_endpoints") or [])
        known_ids = dict(bucket.get("known_ids") or {})

        def _materialize(endpoint: str) -> str:
            value = str(endpoint or "").strip()
            if not value:
                return ""
            for placeholder, replacement in (
                (":id", known_ids.get("id")),
                (":postId", known_ids.get("post_id") or known_ids.get("id")),
                (":post_id", known_ids.get("post_id") or known_ids.get("id")),
                (":commentId", known_ids.get("comment_id")),
                (":comment_id", known_ids.get("comment_id")),
            ):
                if replacement and placeholder in value:
                    value = value.replace(placeholder, str(replacement))
            return value

        candidate_paths: list[str] = []
        for suggestion in suggestions:
            endpoint = _materialize(str(suggestion or ""))
            if endpoint:
                candidate_paths.append(endpoint)
        for key in ("notifications", "dm_conversations", "feed", "profile", "post_comments", "post_detail"):
            endpoint = _materialize(str(quick_links.get(key, "") or ""))
            if endpoint:
                candidate_paths.append(endpoint)

        base_url = str(bucket.get("base_url") or "").rstrip("/")
        auth_profile = str(bucket.get("auth_profile") or "").strip()
        for candidate in candidate_paths:
            normalized = candidate.strip()
            if not normalized or not normalized.startswith("/"):
                continue
            full_url = f"{base_url}{normalized}" if base_url else normalized
            if full_url in fetched_urls:
                continue
            arguments = {"method": "GET", "url": full_url}
            if auth_profile:
                arguments["auth_profile"] = auth_profile
            return ToolCall(
                id="guided_external_observation",
                name="http_request",
                arguments=arguments,
            )

        return None

    def _is_low_value_exploration_tool(
        self,
        tool_call: ToolCall,
        user_message: str,
        is_heartbeat: bool,
        tool_calls_used: int,
    ) -> bool:
        if not self._is_action_oriented_request(user_message, is_heartbeat):
            return False

        mapped_name = self._tool_aliases.get(tool_call.name, tool_call.name)
        arguments = dict(tool_call.arguments or {})
        path = str(arguments.get("path", "") or "")
        normalized_path = path.lower()
        normalized_name = Path(path).name.lower()
        url = str(arguments.get("url", "") or "").strip().lower()

        if mapped_name == "list_skills":
            return True
        if mapped_name == "get_context":
            return True
        if mapped_name == "web_search" and tool_calls_used > 0 and self._is_guided_external_action_mission(user_message, is_heartbeat):
            return True
        if mapped_name == "read_file" and normalized_name == "skill.md":
            return True
        if mapped_name == "read_file" and normalized_name == "heartbeat.md":
            return is_heartbeat and tool_calls_used > 0
        if is_heartbeat and self._is_disallowed_heartbeat_mutation_tool(tool_call):
            return True
        if mapped_name == "read_file" and normalized_name == "credentials.json":
            if "/.config/" in normalized_path or normalized_path.startswith(".config/"):
                return True
        if mapped_name == "read_file" and normalized_path.endswith("/config.yaml"):
            return True
        if mapped_name == "read_file" and normalized_path.endswith("/config.yml"):
            return True
        if mapped_name == "list_dir" and normalized_path in {
            "/root/.clawlet",
            "/root/.clawlet/workspace",
            "workspace",
        }:
            return True
        if mapped_name == "fetch_url" and is_heartbeat and self._is_low_value_heartbeat_url(url):
            return True
        if (
            mapped_name == "fetch_url"
            and tool_calls_used > 0
            and self._is_guided_external_action_mission(user_message, is_heartbeat)
            and self._is_low_value_action_url(url)
        ):
            return True
        if is_heartbeat and tool_calls_used > 0 and mapped_name in {"read_file", "list_dir"}:
            return True
        return False

    @staticmethod
    def _is_low_value_heartbeat_url(url: str) -> bool:
        lowered = (url or "").strip().lower()
        if not lowered:
            return False
        return any(
            lowered.endswith(suffix)
            for suffix in ("/skill.md", "/heartbeat.md", "/rules.md", "/messaging.md")
        )

    @staticmethod
    def _is_low_value_action_url(url: str) -> bool:
        lowered = (url or "").strip().lower()
        if not lowered:
            return False
        if "github.com" in lowered and any(part in lowered for part in {"/blob/", "/tree/", "/readme", "/api"}):
            return True
        if any(host in lowered for host in {"docs.github.com", "developer.mozilla.org", "docs.", "/developers", "/documentation"}):
            return True
        return False

    # ------------------------------------------------------------------
    # Tool-call parsing / promotion
    # ------------------------------------------------------------------

    def _should_promote_tools_for_parsed_calls(
        self,
        user_message: str,
        tool_calls: list[ToolCall],
        history: Optional[list[Message]] = None,
    ) -> bool:
        """Decide whether to re-run with tools enabled after parser detected tool calls."""
        if not tool_calls:
            return False

        lowered = (user_message or "").strip().lower()
        if not lowered:
            return False
        if self._is_trivial_chat_message(lowered) and not self._has_recent_incomplete_action_context(history or []):
            return False

        # Only promote when parsed calls are to known tools (or aliases).
        for tc in tool_calls:
            mapped = self._tool_aliases.get(tc.name, tc.name)
            if self.tools.get(mapped) is None:
                return False

        if self._has_recent_incomplete_action_context(history or []):
            return True

        # Require at least one action cue in the user's message.
        action_cues = (
            "list", "liste", "show", "read", "lire", "open", "find", "trouve",
            "search", "recherche", "look up", "run", "execute", "exécuter",
            "workspace", "espace de travail", "file", "folder", "dossier", "directory",
            "web", "contenu", "content",
            "url", "http://", "https://", "install", "create", "edit", "write",
        )
        return any(cue in lowered for cue in action_cues)

    def _dedupe_tool_calls(self, tool_calls: list[ToolCall]) -> list[ToolCall]:
        """Remove duplicate tool calls while preserving original order."""
        out: list[ToolCall] = []
        seen: set[str] = set()
        for tc in tool_calls:
            try:
                key = f"{tc.name}:{json.dumps(tc.arguments or {}, sort_keys=True, default=str)}"
            except Exception:
                key = f"{tc.name}:{str(tc.arguments)}"
            if key in seen:
                continue
            seen.add(key)
            out.append(tc)
        return out

    def _rewrite_specialized_tool_call(self, tool_call: ToolCall) -> ToolCall:
        """Convert brittle shell-based HTTP calls into structured tool calls when possible."""
        normalized = self._normalize_special_file_path(tool_call)
        if normalized is not tool_call:
            tool_call = normalized
        normalized_tick = self._normalize_heartbeat_tick_write(tool_call)
        if normalized_tick is not tool_call:
            tool_call = normalized_tick
        if tool_call.name != "shell":
            return tool_call
        if self.tools.get("http_request") is None:
            return tool_call

        command = str((tool_call.arguments or {}).get("command", "") or "").strip()
        rewritten_args = self._parse_curl_shell_command(command)
        if not rewritten_args:
            return tool_call

        logger.info("Rewriting shell curl into structured http_request call")
        return ToolCall(id=tool_call.id, name="http_request", arguments=rewritten_args)

    def _normalize_special_file_path(self, tool_call: ToolCall) -> ToolCall:
        """Collapse known workspace-relative identity paths onto the real workspace root."""
        if tool_call.name not in {"read_file", "write_file", "edit_file"}:
            return tool_call
        arguments = dict(tool_call.arguments or {})
        raw_path = str(arguments.get("path", "") or "").strip()
        if not raw_path:
            return tool_call

        normalized = raw_path.replace("\\", "/").lower()
        if not normalized.endswith("/heartbeat.md") and normalized != "heartbeat.md":
            return tool_call

        candidate = get_workspace_layout(self.workspace).heartbeat_path
        if not candidate.exists():
            return tool_call

        if raw_path == str(candidate) or raw_path == "HEARTBEAT.md":
            return tool_call

        arguments["path"] = str(candidate)
        logger.info(f"Normalizing HEARTBEAT.md path: {raw_path} -> {candidate}")
        return ToolCall(id=tool_call.id, name=tool_call.name, arguments=arguments)

    def _normalize_heartbeat_tick_write(self, tool_call: ToolCall) -> ToolCall:
        """Repair heartbeat writes that try to persist a bogus Moltbook last-check timestamp."""
        if tool_call.name != "write_file":
            return tool_call
        if not self._current_heartbeat_metadata:
            return tool_call

        arguments = dict(tool_call.arguments or {})
        raw_path = str(arguments.get("path", "") or "").strip()
        if not raw_path:
            return tool_call

        layout = get_workspace_layout(self.workspace)
        normalized = raw_path.replace("\\", "/").lower()
        target_suffix = "/.moltbook/lastmoltbookcheck"
        expected_path = str(layout.project_dir / ".moltbook" / "lastMoltbookCheck")
        if not (
            normalized.endswith(target_suffix)
            or raw_path == expected_path
            or raw_path == ".moltbook/lastMoltbookCheck"
        ):
            return tool_call

        tick_at = str(self._current_heartbeat_metadata.get("heartbeat_tick_at") or "").strip()
        canonical = tick_at
        if tick_at:
            try:
                parsed = datetime.fromisoformat(tick_at)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC_TZ)
                canonical = parsed.astimezone(UTC_TZ).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                canonical = ""
        if not canonical:
            canonical = datetime.now(UTC_TZ).strftime("%Y-%m-%dT%H:%M:%SZ")

        changed = False
        if raw_path != expected_path:
            arguments["path"] = expected_path
            changed = True
        if str(arguments.get("content", "") or "").strip() != canonical:
            arguments["content"] = canonical
            changed = True
        if not changed:
            return tool_call

        logger.info(f"Normalizing heartbeat lastMoltbookCheck write: {raw_path} -> {expected_path} ({canonical})")
        return ToolCall(id=tool_call.id, name=tool_call.name, arguments=arguments)

    def _is_disallowed_heartbeat_mutation_tool(self, tool_call: ToolCall) -> bool:
        if not self._current_heartbeat_metadata:
            return False

        mapped_name = self._tool_aliases.get(tool_call.name, tool_call.name)
        arguments = dict(tool_call.arguments or {})
        raw_path = str(arguments.get("path", "") or "").strip()
        normalized_path = raw_path.replace("\\", "/").lower()
        heartbeat_path = str(get_workspace_layout(self.workspace).heartbeat_path).replace("\\", "/").lower()
        blocked_suffixes = {"/heartbeat.md", "/.moltbook/lastmoltbookcheck"}

        if mapped_name in {"write_file", "edit_file"}:
            if normalized_path == heartbeat_path or any(normalized_path.endswith(suffix) for suffix in blocked_suffixes):
                return True

        if mapped_name == "shell":
            command = str(arguments.get("command", "") or "").strip().lower()
            if "heartbeat.md" in command or "lastmoltbookcheck" in command:
                return True

        return False

    # ------------------------------------------------------------------
    # curl -> http_request rewriting
    # ------------------------------------------------------------------

    def _parse_curl_shell_command(self, command: str) -> Optional[dict]:
        """Best-effort parser for common curl invocations emitted by the model."""
        text = (command or "").strip()
        if "curl" not in text.lower():
            return None

        url_match = re.search(r"(https?://[^\s\"']+)", text, re.IGNORECASE)
        if not url_match:
            return None

        method_match = re.search(r"(?:^|\s)-X\s+([A-Za-z]+)\b", text)
        data_payload = self._extract_json_payload_from_curl(text)
        header_pairs = self._extract_headers_from_curl(text)
        method = (method_match.group(1).upper() if method_match else ("POST" if data_payload is not None else "GET"))

        args: dict[str, object] = {
            "method": method,
            "url": url_match.group(1),
        }
        if header_pairs:
            args["headers"] = header_pairs
        if data_payload is not None:
            args["json_body"] = data_payload
        return args

    def _extract_headers_from_curl(self, command: str) -> dict[str, str]:
        """Extract simple header pairs from a curl command string."""
        headers: dict[str, str] = {}
        for match in re.finditer(r"(?:^|\s)-H\s+", command):
            start = match.end()
            quote = command[start] if start < len(command) and command[start] in {"'", '"'} else ""
            if quote:
                start += 1
                end = command.find(quote, start)
                if end == -1:
                    continue
                raw = command[start:end]
            else:
                next_space = command.find(" ", start)
                end = len(command) if next_space == -1 else next_space
                raw = command[start:end]
            if ":" not in raw:
                continue
            key, value = raw.split(":", 1)
            headers[key.strip()] = value.strip()
        return headers

    def _extract_json_payload_from_curl(self, command: str) -> Optional[dict]:
        """Extract a JSON object from curl -d/--data payloads without relying on shell parsing."""
        data_flag = re.search(r"(?:^|\s)(?:-d|--data(?:-raw)?)\s+", command)
        if not data_flag:
            return None

        start = command.find("{", data_flag.end())
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        end = -1
        for index in range(start, len(command)):
            char = command[index]
            if in_string:
                if escape:
                    escape = False
                    continue
                if char == "\\":
                    escape = True
                    continue
                if char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
                continue
            if char == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break

        if end == -1:
            return None

        raw_json = command[start:end]
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    # ------------------------------------------------------------------
    # Template-placeholder sanitization
    # ------------------------------------------------------------------

    def _sanitize_template_placeholders(self, content: str) -> str:
        """Remove obvious template/example placeholders from user-facing replies."""
        raw_placeholder_hits = sum(
            len(re.findall(pattern, content or "", flags=re.IGNORECASE))
            for pattern in self.PLACEHOLDER_PATTERNS
        )
        cleaned = self._sanitize_context_placeholders(content)
        cleaned = re.sub(r"Bearer\s+the configured value\b", "a configured API key", cleaned)
        cleaned = re.sub(r"Bearer\s+your current API key\b", "your current API key", cleaned)
        cleaned = re.sub(r"moltbook_sk_[A-Za-z0-9_\-]+", "[redacted]", cleaned)
        cleaned = re.sub(r"sk-or-v1-[A-Za-z0-9]+", "[redacted]", cleaned)
        cleaned = re.sub(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b", "[redacted]", cleaned)
        word_count = len(re.findall(r"\b\w+\b", content or ""))
        if raw_placeholder_hits >= 3 and word_count <= raw_placeholder_hits + 2:
            return self._rewrite_placeholder_heavy_response("")
        elif self._contains_placeholder_artifacts(cleaned):
            cleaned = self._rewrite_placeholder_heavy_response(cleaned)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _sanitize_context_placeholders(self, content: str) -> str:
        """Remove obvious template/example placeholders from model-facing context."""
        cleaned = content or ""
        replacements = [
            (r"Bearer\s+YOUR_API_KEY\b", "Bearer the configured value"),
            (r"Bearer\s+VOTRE_CLE_API\b", "Bearer the configured value"),
            (r"Bearer\s+<[^>]*(?:api[_\s-]*key|clé[_\s-]*api|cle[_\s-]*api|token|bearer)[^>]*>", "Bearer the configured value"),
            (r"\bYOUR_[A-Z0-9_]+\b", "the configured value"),
            (r"\bVOTRE_[A-Z0-9_]+\b", "the configured value"),
            (r"\bMOLTY_NAME\b", "the target molty"),
            (r"\bPOST_ID\b", "the target post ID"),
            (r"\bCOMMENT_ID\b", "the target comment ID"),
            (r"\bCURSOR_FROM_PREVIOUS_RESPONSE\b", "the next page cursor"),
            (r"\bYourAgentName\b", "the configured agent name"),
            (r"\bYourName\b", "the current name"),
            (r"\byour-human@example\.com\b", "the owner's email address"),
            (r"\bmoltbook_xxx\b", "a Moltbook API key"),
            (r"\bmoltbook_claim_xxx\b", "a Moltbook claim URL token"),
            (r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){0,4}(?:_ID|_KEY|_TOKEN|_NAME|_VALUE|_EMAIL|_URL|_HANDLE)\b", "the live value"),
            (r"uuid\.\.\.", "the target resource"),
            (r"\[Your [^\]]+\]", "your actual details"),
            (r"\[Preferred [^\]]+\]", "your preferred name"),
            (r"\[(?:insert|replace|set|use|enter|provide)[^\]]+\]", "the real value"),
            (r"\[Optional\]", ""),
            (r"<[^>]*(?:api[_\s-]*key|clé[_\s-]*api|cle[_\s-]*api|token|bearer)[^>]*>", "a configured API key"),
            (r"<[^>]*(?:post[_\s-]*id|comment[_\s-]*id|molty|name|nom)[^>]*>", "the real target details"),
            (r"<[A-Z][A-Z0-9 _-]{1,48}>", "the real value"),
        ]
        for pattern, replacement in replacements:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _contains_placeholder_artifacts(self, content: str) -> bool:
        text = content or ""
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in self.PLACEHOLDER_PATTERNS)

    def _tool_args_contain_template_placeholders(self, tool_name: str, args: dict) -> bool:
        """Detect templated values that should never be executed as live tool inputs."""
        def _walk(value) -> bool:
            if isinstance(value, dict):
                return any(_walk(v) or _walk(k) for k, v in value.items())
            if isinstance(value, list):
                return any(_walk(item) for item in value)
            if not isinstance(value, str):
                return False
            text = value.strip()
            if not text:
                return False
            if self._contains_placeholder_artifacts(text):
                return True
            patterns = (
                r"\bYOUR_API_KEY_HERE\b",
                r"\bYOUR_[A-Z0-9_]+\b",
                r"\bVOTRE_[A-Z0-9_]+\b",
                r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){0,4}(?:_ID|_KEY|_TOKEN|_NAME|_VALUE|_EMAIL|_URL|_HANDLE)\b",
                r"\bMOLTY_NAME\b",
                r"\bPOST_ID\b",
                r"\bCOMMENT_ID\b",
                r"\bCURSOR_FROM_PREVIOUS_RESPONSE\b",
                r"\bYourAgentName\b",
                r"\bYourName\b",
                r"\[Your [^\]]+\]",
                r"\[Preferred [^\]]+\]",
                r"\[(?:insert|replace|set|use|enter|provide)[^\]]+\]",
                r"\[Optional\]",
                r"<[A-Z][A-Z0-9 _-]{1,48}>",
                r"<[^>]*(?:api[_\s-]*key|clé[_\s-]*api|cle[_\s-]*api|token|bearer|post[_\s-]*id|comment[_\s-]*id|molty|name|nom)[^>]*>",
            )
            return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

        if tool_name not in {"http_request", "shell", "fetch_url", "write_file", "edit_file"}:
            return False
        return _walk(args)

    def _rewrite_placeholder_heavy_response(self, content: str) -> str:
        """Fallback rewrite when a response still reads like a template."""
        text = content or ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        kept: list[str] = []
        for line in lines:
            if self._contains_placeholder_artifacts(line):
                continue
            kept.append(line)
        if kept:
            return "\n\n".join(kept)
        return (
            "I need the real target details from the live context before I can complete that action. "
            "I will use the actual values on the next attempt."
        )

    # ------------------------------------------------------------------
    # Tool-call extraction + execution
    # ------------------------------------------------------------------

    def _extract_provider_tool_calls(self, response: LLMResponse) -> list[ToolCall]:
        """Normalize provider-native tool calls into internal ToolCall objects."""
        if not response.tool_calls:
            return []

        normalized: list[ToolCall] = []
        for i, call in enumerate(response.tool_calls):
            if not isinstance(call, dict):
                continue

            call_id = call.get("id") or f"provider_call_{i}"
            function_payload = call.get("function", {}) if isinstance(call.get("function"), dict) else {}
            name = function_payload.get("name") or call.get("name")
            raw_arguments = function_payload.get("arguments", call.get("arguments", {}))

            if not name:
                logger.warning("Skipping provider tool call without name")
                continue

            if isinstance(raw_arguments, str):
                try:
                    raw_arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    logger.warning(f"Skipping tool call '{name}' due to invalid JSON arguments")
                    continue

            if not isinstance(raw_arguments, dict):
                raw_arguments = {"value": raw_arguments}

            normalized.append(ToolCall(id=call_id, name=name, arguments=raw_arguments))

        if normalized:
            logger.info(f"Using {len(normalized)} provider-native tool call(s)")

        return normalized

    def _render_tool_result(self, result: ToolResult) -> str:
        """Render tool output for conversation history."""
        raw = result.output if result.success else f"Error: {result.error}"
        cleaned = self._sanitize_context_placeholders(raw)
        cleaned = re.sub(r"moltbook_sk_[A-Za-z0-9_\-]+", "[redacted]", cleaned)
        cleaned = re.sub(r"sk-or-v1-[A-Za-z0-9]+", "[redacted]", cleaned)
        cleaned = re.sub(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b", "[redacted]", cleaned)
        return cleaned

    def _tool_call_signature(self, tool_call: ToolCall) -> str:
        """Stable signature for duplicate-call suppression within a single turn."""
        try:
            args = json.dumps(tool_call.arguments or {}, sort_keys=True, default=str)
        except Exception:
            args = str(tool_call.arguments)
        return f"{tool_call.name}:{args}"

    def _extract_tool_calls(self, content: str) -> list[ToolCall]:
        """Extract tool calls from LLM response content."""
        # Fast path: raw JSON tool payloads.
        stripped = (content or "").strip()
        if stripped and (stripped.startswith("{") or stripped.startswith("[")):
            try:
                raw = json.loads(stripped)
                if isinstance(raw, dict) and "name" in raw:
                    args = raw.get("arguments", raw.get("parameters", {}))
                    if not isinstance(args, dict):
                        args = {"value": args}
                    return [ToolCall(id="call_raw_json_0", name=raw["name"], arguments=args)]
                if isinstance(raw, list):
                    out: list[ToolCall] = []
                    for i, item in enumerate(raw):
                        if not isinstance(item, dict) or "name" not in item:
                            continue
                        args = item.get("arguments", item.get("parameters", {}))
                        if not isinstance(args, dict):
                            args = {"value": args}
                        out.append(ToolCall(id=f"call_raw_json_{i}", name=item["name"], arguments=args))
                    if out:
                        return out
            except json.JSONDecodeError:
                pass

        from clawlet.agent.tool_parser import ToolCallParser

        parsed = ToolCallParser().parse(content or "")
        if parsed:
            return [ToolCall(id=p.id, name=p.name, arguments=p.arguments) for p in parsed]
        return []

    async def _execute_tool(self, tool_call: ToolCall, approved: bool = False) -> ToolResult:
        """Execute a tool call with circuit breaker protection."""
        # Use the already-mapped name from the tool call (set in the loop)
        # But also check for aliases in case this method is called directly
        requested_tool_name = tool_call.name
        tool_name = self._tool_aliases.get(requested_tool_name, requested_tool_name)
        if tool_name != requested_tool_name:
            logger.info(f"Mapping tool alias '{requested_tool_name}' -> '{tool_name}'")
            tool_call.name = tool_name  # Update the tool call name
        now = datetime.now(UTC_TZ)
        raw_args = dict(tool_call.arguments or {})
        failure_key = self._tool_failure_key(tool_name, raw_args)

        # Check if circuit is open for this tool
        if failure_key in self._tool_circuit_open_until:
            if now < self._tool_circuit_open_until[failure_key]:
                # Circuit is open, skip execution
                logger.warning(f"Circuit open for tool bucket '{failure_key}'. Skipping execution.")
                await self._publish_progress_update(
                    "tool_failed",
                    f"Skipped `{tool_name}` because it is temporarily unavailable.",
                    detail="circuit open",
                )
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Tool '{tool_name}' is temporarily unavailable due to repeated failures.",
                    data={"transient": True, "failure_key": failure_key},
                )
            else:
                # Circuit timeout expired, reset
                logger.info(f"Circuit breaker timeout for tool bucket '{failure_key}' expired, allowing test call")
                self._tool_circuit_open_until.pop(failure_key, None)
                self._tool_failures[failure_key] = 0  # reset failures

        logger.info(f"Executing tool: {tool_name} with args: {tool_call.arguments}")
        await self._publish_progress_update("tool_started", f"Running `{tool_name}`.", detail=tool_name)

        if self.tools.get(tool_name) is None:
            logger.warning(f"Rejected unknown tool call: {tool_name}")
            self._tool_stats["calls_rejected"] += 1
            await self._publish_progress_update("tool_failed", f"Rejected unknown tool `{tool_name}`.", detail=tool_name)
            return ToolResult(success=False, output="", error=f"Unknown tool: {tool_name}")

        # Validate tool invocation before execution.
        tool = self.tools.get(tool_name)
        schema = tool.parameters_schema if tool else None
        execution_target_raw = str(raw_args.pop("_execution_target", "local")).strip().lower()
        execution_target = "remote" if execution_target_raw == "remote" else "local"
        lane = str(raw_args.pop("_lane", "")).strip().lower()
        cacheable_override_raw = raw_args.pop("_cacheable", None)
        cacheable_override: Optional[bool] = None
        if isinstance(cacheable_override_raw, bool):
            cacheable_override = cacheable_override_raw

        valid, error_msg, sanitized = validate_tool_params(
            tool_name=tool_name,
            params=raw_args,
            schema=schema,
        )
        if not valid:
            logger.warning(f"Rejected tool call for '{tool_name}': {error_msg}")
            self._tool_stats["calls_rejected"] += 1
            await self._publish_progress_update(
                "tool_failed",
                f"Rejected invalid call for `{tool_name}`.",
                detail=error_msg,
            )
            return ToolResult(success=False, output="", error=f"Invalid tool call: {error_msg}")
        args = dict(sanitized.get("params", raw_args))
        repaired_args = self._repair_templated_tool_args(tool_name, args)
        if repaired_args is not None:
            logger.info(f"Applied deterministic repair to templated args for '{tool_name}'")
            args = repaired_args
        if self._tool_args_contain_template_placeholders(tool_name, args):
            error_msg = "Tool call contains template placeholders instead of live values"
            logger.warning(f"Rejected templated tool call for '{tool_name}': {args}")
            self._tool_stats["calls_rejected"] += 1
            await self._publish_progress_update(
                "tool_failed",
                f"Rejected templated call for `{tool_name}`.",
                detail=error_msg,
            )
            return ToolResult(success=False, output="", error=error_msg)
        envelope = ToolCallEnvelope(
            run_id=self._current_run_id or self._next_run_id(self._session_id or "session"),
            session_id=self._session_id or "session",
            tool_call_id=tool_call.id,
            tool_name=tool_name,
            arguments=args,
            execution_mode=self._runtime_policy.infer_mode(tool_name, args),
            workspace_path=str(self.workspace),
            timeout_seconds=self.runtime_config.default_tool_timeout_seconds,
            max_retries=self.runtime_config.default_tool_retries,
            cacheable=cacheable_override,
            execution_target=execution_target,  # type: ignore[arg-type]
            lane=lane,
        )

        try:
            result, meta = await self._tool_runtime.execute(envelope, approved=approved)
            self._tool_stats["calls_executed"] += 1
            logger.debug(
                f"Tool runtime metadata: {tool_name} -> {asdict(meta)}"
            )
        except Exception as e:
            # Unexpected exception, wrap in ToolResult
            result = ToolResult(success=False, output="", error=str(e))

        if result.success:
            # Reset failure count on success
            if failure_key in self._tool_failures:
                self._tool_failures[failure_key] = 0
            if tool_name == "http_request":
                self._remember_http_request_context(args, result)
            logger.info(f"Tool {tool_name} succeeded: {result.output[:100]}...")
            await self._publish_progress_update("tool_completed", f"Completed `{tool_name}`.", detail=tool_name)
        else:
            self._tool_stats["calls_failed"] += 1
            result_data = result.data if isinstance(result.data, dict) else {}
            is_transient_failure = bool(result_data.get("transient")) or "temporarily unavailable" in (
                (result.error or "").lower()
            )
            failures = self._tool_failures.get(failure_key, 0)
            if is_transient_failure:
                failures += 1
                self._tool_failures[failure_key] = failures
            # Increment tool error metric
            get_metrics().inc_tool_errors()
            logger.warning(
                f"Tool {tool_name} failed: {result.error} "
                f"(bucket={failure_key}, transient={is_transient_failure}, failures: {failures})"
            )
            await self._publish_progress_update(
                "tool_failed",
                f"`{tool_name}` failed.",
                detail=result.error or result.output[:200],
            )

            if is_transient_failure and failures >= self._tool_failure_threshold:
                # Trip circuit breaker
                open_until = now + timedelta(seconds=self._tool_circuit_timeout_seconds)
                self._tool_circuit_open_until[failure_key] = open_until
                logger.error(
                    f"Circuit breaker tripped for tool bucket '{failure_key}'! "
                    f"Open until {open_until.isoformat()}"
                )

        return result

    def _tool_failure_key(self, tool_name: str, args: dict) -> str:
        if tool_name != "http_request":
            return tool_name
        method = str(args.get("method", "GET") or "GET").strip().upper()
        url = str(args.get("url", "") or "").strip()
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path or "/"
        return f"{tool_name}:{method}:{host}{path}"

    # ------------------------------------------------------------------
    # http_request context memory + deterministic arg repairs
    # ------------------------------------------------------------------

    def _remember_http_request_context(self, args: dict, result: ToolResult) -> None:
        if not result.success:
            return
        url = str(args.get("url", "") or "").strip()
        if not url:
            return
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return

        bucket = self._recent_http_context.setdefault(host, {})
        self._recent_http_context["_latest_host"] = host
        path = parsed.path or "/"
        bucket["base_url"] = f"{parsed.scheme}://{host}" if parsed.scheme else ""
        fetched_urls = list(bucket.get("fetched_urls") or [])
        normalized_url = str(parsed._replace(query=parsed.query or "").geturl())
        if normalized_url not in fetched_urls:
            fetched_urls.append(normalized_url)
        bucket["fetched_urls"] = fetched_urls[-12:]

        def _remember(key: str, value) -> None:
            if isinstance(value, str) and value.strip():
                known_ids = dict(bucket.get("known_ids") or {})
                known_ids[key] = value.strip()
                bucket["known_ids"] = known_ids

        match = re.search(r"/posts/([^/]+)", path)
        if match:
            _remember("post_id", match.group(1))
        comment_match = re.search(r"/comments/([^/]+)", path)
        if comment_match:
            _remember("comment_id", comment_match.group(1))

        requested_auth_profile = str(args.get("auth_profile", "") or "").strip()
        if requested_auth_profile and not self._contains_placeholder_artifacts(requested_auth_profile):
            bucket["auth_profile"] = requested_auth_profile

        try:
            payload = json.loads(result.output or "{}")
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return

        for key, value in payload.items():
            if isinstance(key, str) and key.endswith("_id"):
                _remember(key, value)
            elif key == "id":
                _remember("id", value)

        post = payload.get("post")
        if isinstance(post, dict):
            _remember("post_id", post.get("id"))

        quick_links = payload.get("quick_links")
        if isinstance(quick_links, dict):
            filtered: dict[str, str] = {}
            for key, value in quick_links.items():
                if isinstance(value, str) and value.strip().startswith(("GET ", "POST ", "PATCH ", "DELETE ")):
                    method, _, endpoint = value.strip().partition(" ")
                    if method.upper() == "GET" and endpoint.startswith("/"):
                        filtered[str(key)] = endpoint.strip()
            if filtered:
                bucket["quick_links"] = filtered

        suggested_endpoints: list[str] = list(bucket.get("suggested_endpoints") or [])
        for field in ("what_to_do_next", "next_actions", "recommended_actions"):
            value = payload.get(field)
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, str):
                    continue
                match = re.search(r"\bGET\s+(/[^\s`]+)", item)
                if match:
                    endpoint = match.group(1).strip()
                    if endpoint not in suggested_endpoints:
                        suggested_endpoints.append(endpoint)
        if suggested_endpoints:
            bucket["suggested_endpoints"] = suggested_endpoints[-12:]

        activities = payload.get("activity_on_your_posts")
        if isinstance(activities, list):
            for activity in activities:
                if not isinstance(activity, dict):
                    continue
                post_id = activity.get("post_id")
                _remember("post_id", post_id)
                break

        comments = payload.get("comments")
        if isinstance(comments, list):
            for comment in comments:
                if not isinstance(comment, dict):
                    continue
                _remember("comment_id", comment.get("id"))
                _remember("post_id", comment.get("post_id"))
                break

        posts = payload.get("posts")
        if isinstance(posts, list):
            for post in posts:
                if not isinstance(post, dict):
                    continue
                post_id = str(post.get("id", "") or "").strip()
                if post_id:
                    _remember("post_id", post_id)
                    break

    def _repair_moltbook_http_request(self, repaired: dict) -> bool:
        changed = False
        bucket = self._recent_http_context.get("moltbook", {})

        auth_profile = repaired.get("auth_profile")
        if isinstance(auth_profile, str):
            lowered = auth_profile.strip().lower()
            if lowered in {"moltbook_api_key", "moltbook-key", "moltbook_token"}:
                repaired["auth_profile"] = "moltbook"
                changed = True
            elif self._contains_placeholder_artifacts(auth_profile):
                repaired["auth_profile"] = "moltbook"
                changed = True

        url = str(repaired.get("url", "") or "")
        if url:
            replacements = {
                ":postId": bucket.get("last_post_id"),
                ":post_id": bucket.get("last_post_id"),
                "POST_ID": bucket.get("last_post_id"),
                "/:id": f"/{bucket['last_post_id']}" if bucket.get("last_post_id") else None,
                ":commentId": bucket.get("last_comment_id"),
                ":comment_id": bucket.get("last_comment_id"),
                "COMMENT_ID": bucket.get("last_comment_id"),
                "MOLTY_NAME": bucket.get("last_molty_name"),
            }
            fixed_url = url
            for needle, replacement in replacements.items():
                if replacement and needle in fixed_url:
                    fixed_url = fixed_url.replace(needle, replacement)
            if fixed_url != url:
                repaired["url"] = fixed_url
                changed = True

        body = repaired.get("json_body")
        if isinstance(body, dict):
            field_replacements = {
                "postId": bucket.get("last_post_id"),
                "post_id": bucket.get("last_post_id"),
                "parentId": bucket.get("last_comment_id"),
                "parent_id": bucket.get("last_comment_id"),
                "commentId": bucket.get("last_comment_id"),
                "comment_id": bucket.get("last_comment_id"),
                "molty": bucket.get("last_molty_name"),
                "molty_name": bucket.get("last_molty_name"),
            }
            for key, replacement in field_replacements.items():
                value = body.get(key)
                if (
                    replacement
                    and isinstance(value, str)
                    and (self._contains_placeholder_artifacts(value) or value in {"POST_ID", "COMMENT_ID", "MOLTY_NAME"})
                ):
                    body[key] = replacement
                    changed = True

        return changed

    def _repair_templated_tool_args(self, tool_name: str, args: dict) -> Optional[dict]:
        if not self._tool_args_contain_template_placeholders(tool_name, args):
            return None
        if tool_name != "http_request":
            return None

        repaired = json.loads(json.dumps(args))
        changed = False
        headers = repaired.get("headers")
        if isinstance(headers, dict):
            auth_value = str(headers.get("Authorization", "") or "")
            if auth_value and self._contains_placeholder_artifacts(auth_value):
                headers.pop("Authorization", None)
                changed = True

        url = str(repaired.get("url", "") or "")
        parsed = urlparse(url)
        if (parsed.hostname or "").lower() == "www.moltbook.com":
            changed = self._repair_moltbook_http_request(repaired) or changed

        body = repaired.get("json_body")
        if isinstance(body, dict):
            placeholder_keys = [
                key for key, value in body.items()
                if isinstance(value, str) and self._contains_placeholder_artifacts(value)
            ]
            for key in placeholder_keys:
                body.pop(key, None)
                changed = True

        return repaired if changed else None

    def _summarize_heartbeat_tool_result(self, tool_name: str, result: ToolResult) -> str:
        return self._response_policy.summarize_heartbeat_tool_result(tool_name, result)

    def _requires_confirmation(self, tool_call: ToolCall) -> str:
        """Return a non-empty reason if the tool call should require explicit user confirmation."""
        return self._runtime_policy.confirmation_reason(tool_call.name, tool_call.arguments or {}, approved=False)

    # ------------------------------------------------------------------
    # Parallel / serial batch execution
    # ------------------------------------------------------------------

    def _should_parallelize_tool_calls(self, tool_calls: list[ToolCall]) -> bool:
        """Allow safe parallel execution for batches of read-only local tool calls."""
        if not self._enable_parallel_read_batches:
            return False
        if len(tool_calls) < 2:
            return False
        for tc in tool_calls:
            if not self._is_parallel_tool_call(tc):
                return False
        return True

    def _is_parallel_tool_call(self, tool_call: ToolCall) -> bool:
        """True when this tool call is safe for read-only parallel execution."""
        args = dict(tool_call.arguments or {})
        if str(args.get("_execution_target", "local")).strip().lower() == "remote":
            return False
        lane = str(args.get("_lane", "")).strip().lower()
        if lane.startswith("serial:"):
            return False
        mode = self._runtime_policy.infer_mode(tool_call.name, args)
        return mode == "read_only"

    def _plan_tool_execution_groups(self, tool_calls: list[ToolCall]) -> list[tuple[str, list[ToolCall]]]:
        """Group calls into deterministic execution blocks: parallel-read-only or serial."""
        if not self._enable_parallel_read_batches:
            return [("serial", [tc]) for tc in tool_calls]
        groups: list[tuple[str, list[ToolCall]]] = []
        pending_parallel: list[ToolCall] = []

        def _flush_parallel():
            nonlocal pending_parallel
            if not pending_parallel:
                return
            if len(pending_parallel) == 1:
                groups.append(("serial", [pending_parallel[0]]))
            else:
                groups.append(("parallel", list(pending_parallel)))
            pending_parallel = []

        for tc in tool_calls:
            if self._is_parallel_tool_call(tc):
                pending_parallel.append(tc)
                continue
            _flush_parallel()
            groups.append(("serial", [tc]))

        _flush_parallel()
        return groups

    async def _execute_tool_calls_optimized(self, tool_calls: list[ToolCall]) -> list[tuple[ToolCall, ToolResult]]:
        """Execute mixed batches with parallel read-only groups and serial fallback."""
        if not tool_calls:
            return []

        out: list[tuple[ToolCall, ToolResult]] = []
        for mode, chunk in self._plan_tool_execution_groups(tool_calls):
            if mode == "parallel":
                self._tool_stats["parallel_batches"] = int(self._tool_stats.get("parallel_batches", 0)) + 1
                self._tool_stats["parallel_batch_tools"] = int(self._tool_stats.get("parallel_batch_tools", 0)) + len(
                    chunk
                )
                out.extend(await self._execute_tool_batch_parallel(chunk))
                continue
            self._tool_stats["serial_batches"] = int(self._tool_stats.get("serial_batches", 0)) + 1
            for tc in chunk:
                out.append((tc, await self._execute_tool(tc)))
        return out

    async def _execute_tool_batch_parallel(self, tool_calls: list[ToolCall]) -> list[tuple[ToolCall, ToolResult]]:
        """Execute tool calls concurrently and preserve call order for history determinism."""
        limit = max(1, min(self._max_parallel_read_tools, len(tool_calls)))
        semaphore = asyncio.Semaphore(limit)

        async def _run(tc: ToolCall) -> ToolResult:
            async with semaphore:
                try:
                    return await self._execute_tool(tc)
                except Exception as e:
                    return ToolResult(success=False, output="", error=str(e))

        logger.info(
            f"Executing {len(tool_calls)} read-only tool calls in parallel batch "
            f"(max_parallel={limit})"
        )
        results = await asyncio.gather(*[_run(tc) for tc in tool_calls])
        return list(zip(tool_calls, results))
