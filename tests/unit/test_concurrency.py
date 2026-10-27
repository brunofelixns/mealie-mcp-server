import asyncio

from mealie_mcp_server.support.concurrency import map_with_concurrency


async def test_bounded_workers_preserve_output_order() -> None:
    active = peak = 0
    gate = asyncio.Event()

    async def work(value: int) -> int:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 4:
            gate.set()
        await gate.wait()
        await asyncio.sleep(0)
        active -= 1
        return value * 2

    result = await asyncio.wait_for(map_with_concurrency(list(range(12)), 4, work), timeout=2)
    assert result == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
    assert peak == 4
