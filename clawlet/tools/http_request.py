"""
Generic structured HTTP request tool.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

from clawlet.tools.registry import BaseTool, ToolResult


class HttpRequestTool(BaseTool):
    """Execute HTTP requests without fragile shell quoting."""

    USER_AGENT = "Clawlet/1.0 (+https://github.com/Kxrbx/Clawlet)"
    BUILTIN_AUTH_PROFILES = {
        "moltbook": {
            "bearer_token_path": "~/.config/moltbook/credentials.json",
            "env_var": "MOLTBOOK_API_KEY",
            "header_name": "Authorization",
            "header_prefix": "Bearer ",
        }
    }
    AUTH_PLACEHOLDER_PATTERNS = (
        r"\bYOUR_[A-Z0-9_]+\b",
        r"\bVOTRE_[A-Z0-9_]+\b",
        r"<[^>]*(?:api[_\s-]*key|clé[_\s-]*api|cle[_\s-]*api|token|bearer)[^>]*>",
    )

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        client: Optional[httpx.AsyncClient] = None,
        workspace: Optional[Path] = None,
        auth_profiles: Optional[dict[str, dict]] = None,
    ):
        self.timeout = timeout
        self._client = client
        self.workspace = Path(workspace).expanduser() if workspace else None
        self.auth_profiles = dict(auth_profiles or {})

    @property
    def name(self) -> str:
        return "http_request"

    @property
    def description(self) -> str:
        return (
            "Perform a structured HTTP request with method, URL, headers, and optional JSON body. "
            "Prefer this over shell/curl for API calls or JSON posts. "
            "Use an explicit auth_profile when you want local credentials injected."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "method": {"type": "string", "description": "HTTP method such as GET or POST."},
                "url": {"type": "string", "description": "Full HTTP or HTTPS URL."},
                "headers": {"type": "object", "description": "Optional request headers."},
                "json_body": {"type": "object", "description": "Optional JSON request body."},
                "auth_profile": {
                    "type": "string",
                    "description": "Optional local auth profile name for auto-loading stored bearer credentials.",
                },
            },
            "required": ["method", "url"],
        }

    async def execute(
        self,
        method: str,
        url: str,
        headers: Optional[dict] = None,
        json_body: Optional[dict] = None,
        auth_profile: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        normalized_method = (method or "GET").strip().upper()
        normalized_url = (url or "").strip()
        if not normalized_url.startswith(("http://", "https://")):
            return ToolResult(success=False, output="", error=f"Invalid URL: {normalized_url}")

        client = self._client
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout, follow_redirects=True)
            self._client = client

        request_headers = {"User-Agent": self.USER_AGENT}
        if isinstance(headers, dict):
            for key, value in headers.items():
                if value is None:
                    continue
                request_headers[str(key)] = str(value)
        request_headers, auth_context = self._apply_local_auth(
            normalized_url,
            request_headers,
            auth_profile=auth_profile,
        )

        request_json = dict(json_body) if isinstance(json_body, dict) else json_body

        try:
            response = await client.request(normalized_method, normalized_url, headers=request_headers, json=request_json)
        except httpx.TimeoutException:
            return ToolResult(
                success=False,
                output="",
                error=f"Timed out requesting {normalized_url}",
                data=self._build_error_data(normalized_method, normalized_url, transient=True, timeout=True),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"HTTP request failed: {e}",
                data=self._build_error_data(normalized_method, normalized_url, transient=True),
            )

        response, request_headers, auth_context = await self._retry_with_alternate_auth_on_401(
            client=client,
            method=normalized_method,
            url=normalized_url,
            headers=request_headers,
            json_body=request_json,
            response=response,
            auth_context=auth_context,
        )

        repaired_payload = self._repair_json_body_from_validation_error(
            normalized_method,
            normalized_url,
            request_json,
            response,
        )
        if repaired_payload is not None and repaired_payload != request_json:
            try:
                response = await client.request(
                    normalized_method,
                    normalized_url,
                    headers=request_headers,
                    json=repaired_payload,
                )
                request_json = repaired_payload
            except httpx.TimeoutException:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Timed out requesting {normalized_url}",
                    data=self._build_error_data(normalized_method, normalized_url, transient=True, timeout=True),
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"HTTP request failed: {e}",
                    data=self._build_error_data(normalized_method, normalized_url, transient=True),
                )

        rendered = self._render_response(response)
        if response.status_code >= 400:
            transient = self._is_transient_status(response.status_code)
            return ToolResult(
                success=False,
                output=rendered,
                error=f"HTTP {response.status_code} for {normalized_url}",
                data=self._build_error_data(
                    normalized_method,
                    str(response.url),
                    status_code=response.status_code,
                    transient=transient,
                ),
            )

        self._persist_validated_auth(
            normalized_url,
            request_headers,
            auth_context=auth_context,
        )
        return ToolResult(
            success=True,
            output=rendered,
            data=self._build_error_data(
                normalized_method,
                str(response.url),
                status_code=response.status_code,
                transient=False,
            ),
        )

    def _apply_local_auth(
        self,
        url: str,
        headers: dict[str, str],
        auth_profile: Optional[str] = None,
    ) -> tuple[dict[str, str], dict]:
        requested_profile = (auth_profile or "").strip()
        profile = requested_profile
        if not profile or self._looks_like_placeholder(profile) or profile.lower() in {"the live value", "live value"}:
            profile = self._infer_auth_profile(url)
        if not profile:
            return headers, {}

        auth_value = headers.get("Authorization", "")
        if auth_value and not self._looks_like_placeholder(auth_value):
            return headers, {"profile": profile, "source": "explicit", "candidates": []}

        candidates = self._load_auth_candidates(profile)
        if not candidates:
            return headers, {"profile": profile, "source": "", "candidates": []}
        candidate = candidates[0]

        updated = dict(headers)
        updated[candidate["header_name"]] = candidate["header_value"]
        return updated, {
            "profile": profile,
            "source": candidate["source"],
            "candidates": candidates,
            "candidate_index": 0,
        }

    def _load_auth_candidates(self, profile: str) -> list[dict[str, str]]:
        settings = dict(self.auth_profiles.get(profile) or {})
        if not settings:
            settings = dict(self.BUILTIN_AUTH_PROFILES.get(profile) or {})
        if not settings:
            return []

        header_name = str(settings.get("header_name") or "Authorization").strip() or "Authorization"
        header_prefix = str(settings.get("header_prefix") or "Bearer ")
        candidates: list[dict[str, str]] = []
        seen_tokens: set[str] = set()

        def _remember(source: str, token: str) -> None:
            normalized = (token or "").strip()
            if not normalized or self._looks_like_placeholder(normalized) or normalized in seen_tokens:
                return
            seen_tokens.add(normalized)
            candidates.append(
                {
                    "source": source,
                    "header_name": header_name,
                    "header_value": f"{header_prefix}{normalized}" if header_prefix else normalized,
                    "token": normalized,
                }
            )

        env_var = str(settings.get("env_var") or "").strip()
        if env_var:
            import os

            token = str(os.environ.get(env_var, "") or "").strip()
            if token:
                _remember(f"env:{env_var}", token)

        token_path = str(settings.get("bearer_token_path") or "").strip()
        if not token_path:
            return candidates

        for path in self._resolve_token_paths(token_path):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            for key in ("api_key", "bearer_token", "token", "access_token"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    _remember(f"file:{path}", value.strip())
                    break
        return candidates

    def _resolve_token_paths(self, token_path: str) -> list[Path]:
        candidate = Path(token_path)
        if candidate.is_absolute():
            path = candidate.expanduser()
            return [path] if path.exists() else []

        candidates: list[Path] = []
        expanded = candidate.expanduser()
        if expanded.exists():
            candidates.append(expanded)

        if self.workspace:
            workspace_root = self.workspace.expanduser().resolve()
            relative = token_path.lstrip("~/")
            workspace_candidates = [
                workspace_root / relative,
                workspace_root / "workspace" / relative,
            ]
            for path in workspace_candidates:
                if path.exists() and path not in candidates:
                    candidates.append(path)
        return candidates

    async def _retry_with_alternate_auth_on_401(
        self,
        *,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: object,
        response: httpx.Response,
        auth_context: dict,
    ) -> tuple[httpx.Response, dict[str, str], dict]:
        if response.status_code != 401:
            return response, headers, auth_context
        profile = str(auth_context.get("profile") or "").strip()
        candidates = list(auth_context.get("candidates") or [])
        if not profile or len(candidates) <= 1:
            return response, headers, auth_context
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict) or "invalid api key" not in str(payload.get("message", "")).lower():
            return response, headers, auth_context

        current_index = int(auth_context.get("candidate_index", 0) or 0)
        for next_index in range(current_index + 1, len(candidates)):
            candidate = candidates[next_index]
            retried_headers = dict(headers)
            retried_headers[candidate["header_name"]] = candidate["header_value"]
            retry_response = await client.request(method, url, headers=retried_headers, json=json_body)
            if retry_response.status_code < 400:
                return retry_response, retried_headers, {
                    "profile": profile,
                    "source": candidate["source"],
                    "candidates": candidates,
                    "candidate_index": next_index,
                }
        return response, headers, auth_context

    def _persist_validated_auth(self, url: str, headers: dict[str, str], *, auth_context: dict) -> None:
        profile = str(auth_context.get("profile") or self._infer_auth_profile(url)).strip()
        if profile != "moltbook":
            return
        auth_value = str(headers.get("Authorization", "") or "").strip()
        if not auth_value.lower().startswith("bearer "):
            return
        token = auth_value[7:].strip()
        if not token or self._looks_like_placeholder(token):
            return
        target = self._preferred_token_write_path(profile)
        if target is None:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"api_key": token}
        if target.exists():
            try:
                current = json.loads(target.read_text(encoding="utf-8"))
            except Exception:
                current = {}
            if isinstance(current, dict):
                for key, value in current.items():
                    if key != "api_key":
                        payload[key] = value
                if current.get("api_key") == token:
                    return
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _preferred_token_write_path(self, profile: str) -> Optional[Path]:
        settings = dict(self.auth_profiles.get(profile) or {})
        if not settings:
            settings = dict(self.BUILTIN_AUTH_PROFILES.get(profile) or {})
        token_path = str(settings.get("bearer_token_path") or "").strip()
        if not token_path:
            return None
        candidate = Path(token_path)
        if candidate.is_absolute():
            return candidate.expanduser()
        if self.workspace:
            workspace_root = self.workspace.expanduser().resolve()
            return workspace_root / token_path.lstrip("~/")
        return candidate.expanduser()

    @staticmethod
    def _infer_auth_profile(url: str) -> str:
        host = (urlparse(url).netloc or "").lower()
        if host in {"moltbook.com", "www.moltbook.com"}:
            return "moltbook"
        return ""

    @classmethod
    def _looks_like_placeholder(cls, value: str) -> bool:
        import re

        text = (value or "").strip()
        if not text:
            return False
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in cls.AUTH_PLACEHOLDER_PATTERNS)

    @staticmethod
    def _render_response(response: httpx.Response) -> str:
        content_type = (response.headers.get("content-type") or "").lower()
        text = response.text or ""
        if "application/json" in content_type:
            try:
                payload = json.loads(text)
                return json.dumps(payload, ensure_ascii=False, indent=2)
            except Exception:
                pass
        return text.strip() or "(no output)"

    @staticmethod
    def _is_transient_status(status_code: int) -> bool:
        return status_code == 429 or status_code >= 500

    @staticmethod
    def _build_error_data(
        method: str,
        url: str,
        *,
        status_code: Optional[int] = None,
        transient: bool,
        timeout: bool = False,
    ) -> dict:
        parsed = urlparse(url)
        return {
            "method": method.upper(),
            "url": url,
            "path": parsed.path,
            "status_code": status_code,
            "transient": transient,
            "timeout": timeout,
        }

    def _repair_json_body_from_validation_error(
        self,
        method: str,
        url: str,
        json_body: object,
        response: httpx.Response,
    ) -> Optional[dict]:
        if method.upper() not in {"POST", "PUT", "PATCH"}:
            return None
        if response.status_code != 400 or not isinstance(json_body, dict):
            return None
        payload = self._parse_json_response(response)
        if not isinstance(payload, dict):
            return None
        messages = payload.get("message")
        if isinstance(messages, str):
            message_list = [messages]
        elif isinstance(messages, list):
            message_list = [str(item) for item in messages]
        else:
            return None

        repaired = dict(json_body)
        changed = False
        for message in message_list:
            match = re.search(r"property\s+([A-Za-z0-9_]+)\s+should not exist", message, re.IGNORECASE)
            if match:
                field = match.group(1)
                if field in repaired:
                    repaired.pop(field, None)
                    changed = True
                continue

            match = re.search(r"([A-Za-z0-9_]+)\s+must be a string", message, re.IGNORECASE)
            if match:
                field = match.group(1)
                if field in repaired and repaired[field] is not None and not isinstance(repaired[field], str):
                    repaired[field] = str(repaired[field])
                    changed = True

        if not changed:
            return None
        return repaired

    @staticmethod
    def _parse_json_response(response: httpx.Response) -> Optional[dict]:
        try:
            payload = response.json()
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None
