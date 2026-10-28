"""Real loopback ASGI server; each test owns its socket and shutdown."""

import asyncio
import socket
from contextlib import asynccontextmanager

import uvicorn


@asynccontextmanager
async def serve_http(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="critical",
            access_log=False,
            timeout_graceful_shutdown=40,
            proxy_headers=False,
        )
    )
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(15):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("HTTP server exited before startup")
                await asyncio.sleep(0.01)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 45)
        sock.close()
