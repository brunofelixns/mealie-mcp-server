import asyncio
import base64
import json
import os
import sys

import pytest
from fastmcp import Client as FastMCPClient
from fastmcp.client.transports import StdioTransport
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from tests.support.fake_mealie import FakeMealie


def environment(fake, **extra):
    clean = {
        key: value for key, value in os.environ.items() if not key.startswith(("MEALIE_", "MCP_"))
    }
    return {
        **clean,
        "MEALIE_BASE_URL": fake.server_url,
        "MEALIE_API_KEY": "fixture-stdio-mealie-key",
        "MCP_AUTH_TOKEN_FILE": "/missing/stdio-ignores-this",
        "NO_PROXY": "127.0.0.1,localhost",
        **extra,
    }


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_official_sdk_stdio_catalog_prompt_and_tool(mode):
    with FakeMealie("categories.basic") as fake:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mealie_mcp_server", "--transport", "stdio"],
            env=environment(fake, MCP_TRANSPORT="http"),
        )
        async with Client(params, mode=mode, read_timeout_seconds=20) as client:
            assert client.protocol_version == ("2025-11-25" if mode == "legacy" else "2026-07-28")
            catalog = await client.list_tools()
            assert len(catalog.tools) == 78
            assert catalog.tools[0].name == "get_recipes"
            prompt = await client.get_prompt("weekly-meal-plan", {"preferences": "vegetarian"})
            assert [message.role for message in prompt.messages] == ["assistant", "user"]
            result = await client.call_tool("get_categories", {"page": 1, "perPage": 20})
            assert not result.is_error
            assert json.loads(result.content[0].text)["items"][0]["name"] == "Dinner"


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_fastmcp_stdio_roundtrip(mode):
    with FakeMealie("categories.basic") as fake:
        transport = StdioTransport(
            command=sys.executable, args=["-m", "mealie_mcp_server"], env=environment(fake)
        )
        async with FastMCPClient(transport, mode=mode, timeout=20) as client:
            assert len(await client.list_tools()) == 78
            result = await client.call_tool("get_categories", {"page": 1, "perPage": 20})
            assert not result.is_error


async def test_stdio_accepts_full_10mib_image_frame():
    image = b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024 - 8)
    encoded = base64.b64encode(image).decode()
    spec = {
        "method": "PUT",
        "path": "/api/recipes/soup/image",
        "query": {},
        "body": {
            "fields": {"extension": "png"},
            "files": {
                "image": {
                    "filename": "image.png",
                    "content_type": "application/octet-stream",
                    "base64": encoded,
                }
            },
        },
        "response": {"image": "v1"},
    }
    with FakeMealie([spec]) as fake:
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "mealie_mcp_server"], env=environment(fake)
        )
        async with Client(params, read_timeout_seconds=30) as client:
            result = await client.call_tool(
                "set_recipe_image", {"slug": "soup", "imageBase64": encoded, "extension": "png"}
            )
            assert not result.is_error


@pytest.mark.parametrize("shutdown", ["eof", "sigterm", "sigint"])
async def test_stdout_is_only_jsonrpc_and_shutdown_closes_live_pool(shutdown):
    with FakeMealie("categories.basic", keep_alive=True) as fake:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "mealie_mcp_server",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment(fake, MEALIE_MCP_DEBUG="true"),
            limit=2 * 1024 * 1024,
        )
        stderr = asyncio.create_task(process.stderr.read())
        frames = []

        async def send(message):
            process.stdin.write(json.dumps(message).encode() + b"\n")
            await process.stdin.drain()

        async def response(identifier):
            async with asyncio.timeout(20):
                while True:
                    line = await process.stdout.readline()
                    assert line, "Unexpected EOF before JSON-RPC response"
                    frame = json.loads(line)
                    assert frame["jsonrpc"] == "2.0"
                    frames.append(frame)
                    if frame.get("id") == identifier:
                        return frame

        try:
            await send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "stdio-wire-test", "version": "1"},
                    },
                }
            )
            initialized = await response(1)
            assert initialized["result"]["serverInfo"]["version"] == "2.1.0"
            await send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            await send(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "get_categories", "arguments": {"page": 1, "perPage": 20}},
                }
            )
            called = await response(2)
            assert json.loads(called["result"]["content"][0]["text"])["total"] == 1
            assert not fake.connection_closed.is_set()
            if shutdown == "eof":
                process.stdin.close()
            elif shutdown == "sigterm":
                process.terminate()
            else:
                import signal

                process.send_signal(signal.SIGINT)
            await asyncio.wait_for(process.wait(), 15)
            assert process.returncode == 0
            assert await asyncio.to_thread(fake.connection_closed.wait, 2)
            remaining = await process.stdout.read()
            for line in remaining.splitlines():
                assert json.loads(line)["jsonrpc"] == "2.0"
            diagnostics = (await stderr).decode()
            assert "Mealie client closed" in diagnostics
            assert "fixture-stdio-mealie-key" not in diagnostics
            assert len(frames) >= 2
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            if not stderr.done():
                await stderr
