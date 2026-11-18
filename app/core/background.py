import asyncio
from collections.abc import Coroutine
from typing import Any

running: set[asyncio.Task] = set()


def run_in_background(coroutine: Coroutine[Any, Any, None]) -> None:
    """Start ``coroutine`` without waiting for it. The task stays in ``running`` until it
    finishes: a task nothing refers to can be collected before it is done."""
    task = asyncio.create_task(coroutine)
    running.add(task)
    task.add_done_callback(running.discard)
