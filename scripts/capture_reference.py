"""Capture the immutable TypeScript oracle through the official Python MCP client."""

import argparse
import asyncio
import json
import subprocess
from importlib.metadata import version
from pathlib import Path
from typing import Any

from mcp import Client
from mcp.client.stdio import StdioServerParameters

UPSTREAM_COMMIT = "d027e1b4a314d781a322f1f91e37840f01464d77"
REFERENCE_IMAGE = "mealie-mcp-reference:upstream-d027e1b"


def dump(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True, exclude_unset=True)


async def capture(image: str) -> dict[str, Any]:
    parameters = StdioServerParameters(
        command="docker",
        args=[
            "run",
            "--rm",
            "-i",
            "--env",
            "MEALIE_BASE_URL=http://mealie-unconfigured.invalid",
            "--env",
            "MEALIE_API_KEY=reference-fixture-not-a-real-key",
            image,
            "node",
            "dist/index.js",
        ],
    )
    async with Client(parameters, mode="legacy", read_timeout_seconds=30) as client:
        catalog = dump(await client.list_tools())
        while catalog.get("nextCursor"):
            page = dump(await client.list_tools(cursor=catalog["nextCursor"]))
            catalog["tools"].extend(page["tools"])
            catalog["nextCursor"] = page.get("nextCursor")
        prompts = dump(await client.list_prompts())
        prompts["expanded"] = dump(await client.get_prompt("weekly-meal-plan"))
        prompts["withPreferences"] = dump(
            await client.get_prompt("weekly-meal-plan", {"preferences": "vegetarian"})
        )
        try:
            resources = dump(await client.list_resources())
        except Exception as error:
            if getattr(error, "code", None) != -32601:
                raise
            resources = {"unsupported": True, "code": -32601}
        return {
            "catalog": catalog,
            "prompts": prompts,
            "instructions": client.instructions or "",
            "resources": resources,
            "protocolVersion": client.protocol_version,
            "serverInfo": dump(client.server_info),
            "capabilities": dump(client.server_capabilities),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", choices=[UPSTREAM_COMMIT], default=UPSTREAM_COMMIT)
    parser.add_argument("--image", default=REFERENCE_IMAGE)
    parser.add_argument("--output", type=Path, default=Path("tests/fixtures/compatibility"))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output = args.output
    names = ["catalog.json", "prompts.json", "instructions.txt", "upstream-manifest.json"]
    if not args.overwrite and any((output / name).exists() for name in names):
        parser.error("Capture already exists; compare the baseline before using --overwrite.")
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True
    ).strip()
    data = asyncio.run(capture(args.image))
    output.mkdir(parents=True, exist_ok=True)
    for name in ["catalog", "prompts"]:
        (output / f"{name}.json").write_text(
            json.dumps(data[name], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (output / "instructions.txt").write_text(data["instructions"], encoding="utf-8")
    manifest = {
        "commit": UPSTREAM_COMMIT,
        "image": args.image,
        "imageId": image_id,
        "captureClientVersion": version("mcp"),
        "protocolVersion": data["protocolVersion"],
        "serverInfo": data["serverInfo"],
        "capabilities": data["capabilities"],
        "resources": data["resources"],
        "testsExecuted": False,
    }
    (output / "upstream-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Captured {len(data['catalog']['tools'])} upstream tools in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
