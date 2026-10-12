"""Skill-install intent detection for the agent loop.

Behavior-only mixin: all state lives on :class:`~clawlet.agent.loop.AgentLoop`
(including the INSTALL_KEYWORDS class constant read via ``self``).
"""

from __future__ import annotations

import re
from typing import Optional

from clawlet.agent.models import Message, ToolCall


class SkillInstallIntentMixin:
    """Detect and route explicit ``install <skill>`` requests."""

    async def _maybe_handle_direct_skill_install(
        self,
        user_message: str,
        history: list[Message],
    ) -> Optional[str]:
        """Handle explicit skill-install requests without re-entering discovery loops."""
        lowered = user_message.strip().lower()
        if not lowered:
            return None

        if not any(keyword in lowered for keyword in self.INSTALL_KEYWORDS):
            return None
        if "skill" not in lowered and "clawhub" not in lowered:
            return None

        direct_github_url = self._extract_github_url(user_message)
        if direct_github_url and self.tools.get("install_skill"):
            tc = ToolCall(
                id="direct_install_skill_url",
                name="install_skill",
                arguments={"github_url": direct_github_url},
            )
            result = await self._execute_tool(tc)
            if result.success:
                return result.output
            return f"Install failed: {result.error or result.output}"
        # Let the normal reasoning/tool loop handle ambiguous install requests.
        return None

    def _extract_skill_target(self, user_message: str) -> Optional[str]:
        """Extract a likely skill target from natural language install requests."""
        text = user_message.strip()
        if not text:
            return None

        # Examples:
        # "install skilltree", "ok install SkillTree", "please add clawai-town skill"
        # "installe ce skill ...", "installer skilltree", "ajoute ce skill ..."
        m = re.search(r"(?:install|installer|installe|add|ajoute|setup|set up)\s+(.+)", text, re.IGNORECASE)
        if not m:
            return None

        candidate = m.group(1).strip().strip("`'\".,!?")
        candidate = re.sub(
            r"\b(skill|please|now|for me|ce|cette|le|la|les|moi)\b",
            "",
            candidate,
            flags=re.IGNORECASE,
        ).strip()
        candidate = re.sub(r"https://github\.com/[^\s)]+", "", candidate, flags=re.IGNORECASE).strip()
        candidate = re.sub(r"\s+", " ", candidate).strip(" -")
        return candidate or None

    def _extract_github_url(self, text: str) -> Optional[str]:
        """Extract first GitHub repo URL from a text snippet."""
        if not text:
            return None
        m = re.search(r"https://github\.com/[^\s)]+", text, re.IGNORECASE)
        if not m:
            return None
        return m.group(0).rstrip(".,)")

    def _is_skill_install_intent(self, text: str) -> bool:
        """Detect install intent for skills in both EN/FR phrasing."""
        lowered = (text or "").strip().lower()
        if not lowered:
            return False
        has_install = any(word in lowered for word in ("install", "installer", "installe", "add", "ajoute", "setup", "set up"))
        has_skill_context = any(word in lowered for word in ("skill", "github", "clawhub"))
        return has_install and has_skill_context

    def _find_github_url_for_target(self, target: str, history: list[Message]) -> Optional[str]:
        """Find a GitHub URL in recent conversation matching the requested target."""
        target_tokens = set(self._slugify(target).split("-"))
        for msg in reversed(history[-30:]):
            urls = re.findall(r"https://github\.com/[^\s)]+", msg.content or "")
            for url in urls:
                cleaned = url.rstrip(".,)")
                slug = cleaned.rstrip("/").split("/")[-1].replace(".git", "")
                slug_tokens = set(self._slugify(slug).split("-"))
                if target_tokens and (target_tokens <= slug_tokens or slug_tokens <= target_tokens):
                    return cleaned
        return None

    def _find_clawhub_slug_for_target(self, target: str, history: list[Message]) -> Optional[str]:
        """Find a previously suggested `clawhub install <slug>` command for the target."""
        target_slug = self._slugify(target)
        target_tokens = set(target_slug.split("-"))
        for msg in reversed(history[-30:]):
            installs = re.findall(r"clawhub\s+install\s+([a-zA-Z0-9._-]+)", msg.content or "", re.IGNORECASE)
            for candidate in installs:
                slug = self._slugify(candidate)
                slug_tokens = set(slug.split("-"))
                if target_tokens and (target_tokens <= slug_tokens or slug_tokens <= target_tokens):
                    return slug
        return None

    def _slugify(self, value: str) -> str:
        """Normalize potential skill names into a safe slug."""
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        return slug
