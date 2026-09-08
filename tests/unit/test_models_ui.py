"""Regression: `clawlet models` search/show-all must use the current
_search_models/_show_all_models (model_ids, fallback) signatures.

Runs fully offline with mocked questionary answers.
"""

import asyncio

import pytest

import questionary

from clawlet.cli import models_ui
from clawlet.config import Config, OpenCodeZenConfig, ProviderConfig


def make_config() -> Config:
    return Config(
        provider=ProviderConfig(
            primary="opencode_zen",
            opencode_zen=OpenCodeZenConfig(api_key="x", model="zen-3.0"),
        )
    )


@pytest.fixture
def answers(monkeypatch):
    """Queue of mocked prompt answers; select answers must be valid choices."""
    queue: list = []

    class Q:
        def __init__(self, value):
            self.value = value

        async def ask_async(self):
            return self.value

    def fake_select(*args, **kwargs):
        choices = kwargs.get("choices") or args[1]
        value = queue.pop(0)
        assert value in choices, f"{value!r} not in {choices!r}"
        return Q(value)

    def fake_text(*args, **kwargs):
        return Q(queue.pop(0))

    monkeypatch.setattr(questionary, "select", fake_select)
    monkeypatch.setattr(questionary, "text", fake_text)
    return queue


def select_interactive():
    return asyncio.run(
        models_ui._select_model_interactive(make_config(), "opencode_zen", "zen-3.0")
    )


def test_models_search_path_returns_string_id(answers):
    # "Search models..." -> type "zen" -> pick first match. Must return a
    # plain model id string, never a dict.
    answers.extend(["Search models...", "zen", "zen-3.0"])
    assert select_interactive() == "zen-3.0"


def test_models_show_all_path_returns_string_id(answers):
    answers.extend(["Show all (4 models)", "zen-2.5"])
    assert select_interactive() == "zen-2.5"


def test_fetch_opencode_models_lists_static_ids():
    models = asyncio.run(models_ui._fetch_provider_models(make_config(), "opencode_zen"))
    assert [m["id"] for m in models] == [
        "zen-2.5",
        "zen-3.0",
        "zen-code-3.0",
        "zen-reasoning",
    ]
