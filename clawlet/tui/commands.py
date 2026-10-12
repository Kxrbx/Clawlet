"""Textual command palette provider: the same commands as `/`, in ^p."""

from __future__ import annotations

from textual.command import Hit, Hits, Provider


class ClawletCommands(Provider):
    """Every hit runs through App.handle_slash_command (single behavior)."""

    async def search(self, query: str) -> Hits:
        from clawlet.tui.screens.main import SLASH_COMMANDS

        matcher = self.matcher(query)
        for name, desc in SLASH_COMMANDS:
            score = matcher.match(f"/{name}")
            if score > 0:
                yield Hit(score, matcher.highlight(f"/{name}"), self._run(name), help=desc)

    def _run(self, name: str):
        app = self.app

        def _hit() -> None:
            app.run_worker(app.handle_slash_command(f"/{name}"))

        return _hit
