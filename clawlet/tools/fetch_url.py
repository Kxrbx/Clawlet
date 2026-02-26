"""
Fetch URL tool for retrieving page content directly.
"""

from __future__ import annotations

import html
import json
import re
from typing import Optional
from urllib.parse import urlparse

import httpx

from loguru import logger

from clawlet.tools.registry import BaseTool, ToolResult


class FetchUrlTool(BaseTool):
    """Tool to fetch and extract readable content from a URL."""

    USER_AGENT = "Clawlet/1.0 (+https://github.com/Kxrbx/Clawlet)"
    MAX_CHARS_HARD_LIMIT = 50000

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def name(self) -> str:
        return "fetch_url"

    @property
    def description(self) -> str:
        return (
            "Fetch content from an explicit URL and extract readable text. "
            "Use this first when the user gives a direct page link and asks to read/follow it."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "HTTP/HTTPS URL to fetch",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return (default: 12000, max: 50000)",
                },
            },
            "required": ["url"],
        }

    async def execute(self, url: str, max_chars: Optional[int] = None, **kwargs) -> ToolResult:
        parsed = urlparse((url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ToolResult(success=False, output="", error=f"Invalid URL: {url}")

        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.USER_AGENT},
            )

        limit = 12000 if max_chars is None else max_chars
        limit = max(1000, min(int(limit), self.MAX_CHARS_HARD_LIMIT))

        try:
            response = await self._client.get(url)
        except httpx.TimeoutException:
            return ToolResult(success=False, output="", error=f"Timed out fetching URL: {url}")
        except Exception as e:
            logger.error(f"fetch_url failed for {url}: {e}")
            return ToolResult(success=False, output="", error=f"Failed to fetch URL: {e}")

        content_type = (response.headers.get("content-type") or "").lower()
        if response.status_code >= 400:
            return ToolResult(
                success=False,
                output="",
                error=f"HTTP {response.status_code} while fetching {url}",
            )

        body_text = response.text or ""
        if not body_text.strip():
            return ToolResult(
                success=False,
                output="",
                error=f"URL returned empty content: {url}",
            )

        extracted_text, title = self._extract_text(body_text, content_type)
        if not extracted_text:
            extracted_text = body_text.strip()

        was_truncated = len(extracted_text) > limit
        extracted_text = extracted_text[:limit]

        lines = [
            f"URL: {str(response.url)}",
            f"Status: {response.status_code}",
            f"Content-Type: {content_type or 'unknown'}",
        ]
        if title:
            lines.append(f"Title: {title}")
        if was_truncated:
            lines.append(f"Note: content truncated to {limit} characters")
        lines.append("")
        lines.append(extracted_text)

        return ToolResult(
            success=True,
            output="\n".join(lines),
            data={
                "url": str(response.url),
                "status_code": response.status_code,
                "content_type": content_type,
                "title": title,
                "truncated": was_truncated,
                "chars": len(extracted_text),
            },
        )

    def _extract_text(self, raw: str, content_type: str) -> tuple[str, str]:
        """Return (text, title)."""
        title = ""

        if "application/json" in content_type:
            try:
                return json.dumps(json.loads(raw), ensure_ascii=False, indent=2), title
            except Exception:
                return raw.strip(), title

        if "text/html" in content_type or "<html" in raw.lower():
            title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.IGNORECASE | re.DOTALL)
            if title_match:
                title = html.unescape(title_match.group(1).strip())

            text = re.sub(
                r"<(script|style|noscript)[^>]*>.*?</\1>",
                " ",
                raw,
                flags=re.IGNORECASE | re.DOTALL,
            )
            text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
            text = re.sub(r"</\s*(p|div|li|tr|h[1-6]|section|article)\s*>", "\n", text, flags=re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = html.unescape(text)
            text = re.sub(r"[ \t]+\n", "\n", text)
            text = re.sub(r"\n[ \t]+", "\n", text)
            text = re.sub(r"[ \t]{2,}", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text.strip(), title

        return raw.strip(), title

