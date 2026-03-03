"""Shared async execution helpers for benchmark modules."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from typing import Any


def run_async(coro: Any):
    """Run coroutine from sync code, including nested-loop contexts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        future: Future = Future()

        def _runner():
            try:
                future.set_result(asyncio.run(coro))
            except Exception as e:
                future.set_exception(e)

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join()
        return future.result()

    return asyncio.run(coro)

