import asyncio
import os
import signal
import socket
import sys

import httpx2 as httpx

from tests.integration.test_http import TOKEN
from tests.support.fake_mealie import FakeMealie


async def test_http_cli_starts_and_sigterm_closes_without_sensitive_logs():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    clean = {
        key: value for key, value in os.environ.items() if not key.startswith(("MEALIE_", "MCP_"))
    }
    with FakeMealie("no_requests") as fake:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "mealie_mcp_server",
            "--transport",
            "http",
            "--port",
            str(port),
            "--debug",
            "--log-level",
            "DEBUG",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                **clean,
                "MEALIE_BASE_URL": fake.server_url,
                "MEALIE_API_KEY": "fixture-secret-mealie",
                "MCP_AUTH_TOKEN": TOKEN,
            },
        )
        diagnostics = asyncio.create_task(process.stderr.read())
        try:
            async with httpx.AsyncClient() as http:
                async with asyncio.timeout(20):
                    while True:
                        assert process.returncode is None
                        try:
                            response = await http.get(f"http://127.0.0.1:{port}/readyz")
                            if response.status_code == 200:
                                break
                        except httpx.ConnectError:
                            pass
                        await asyncio.sleep(0.02)
            process.terminate()
            await asyncio.wait_for(process.wait(), 10)
            # Uvicorn re-raises the handled termination signal after lifespan cleanup.
            assert process.returncode == -signal.SIGTERM
            assert not await process.stdout.read()
            logs = (await diagnostics).decode()
            assert "Mealie client closed" in logs
            assert TOKEN not in logs and "fixture-secret-mealie" not in logs
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            await diagnostics
