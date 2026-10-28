"""Finish an issued, verified mutation when its requester goes away."""

import asyncio
import logging
from collections.abc import Awaitable

import anyio

logger = logging.getLogger(__name__)


async def finish_verified_mutation[T](operation: Awaitable[T], *, cleanup_timeout: float = 35) -> T:
    task = asyncio.ensure_future(operation)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # FastMCP/AnyIO uses level cancellation; keep cleanup outside the cancelled scope.
        with anyio.CancelScope(shield=True):
            try:
                await asyncio.wait_for(asyncio.shield(task), cleanup_timeout)
            except TimeoutError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                logger.error("Verified mutation cleanup timed out; write outcome may be unknown.")
            except Exception as error:
                logger.warning("Verified mutation cleanup after cancellation: %s", error)
        raise
