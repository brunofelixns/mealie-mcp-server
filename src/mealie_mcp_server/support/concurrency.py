"""A bounded worker pool preserving input order without one task per input."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import cast

from mealie_mcp_server.models.common import UNSET, UnsetType


async def map_with_concurrency[T, R](
    items: Sequence[T], limit: int, fn: Callable[[T], Awaitable[R]]
) -> list[R]:
    results: list[R | UnsetType] = [UNSET] * len(items)
    entries = iter(enumerate(items))

    async def worker() -> None:
        for index, item in entries:
            results[index] = await fn(item)

    await asyncio.gather(*(worker() for _ in range(max(1, min(limit, len(items))))))
    return cast(list[R], results)
