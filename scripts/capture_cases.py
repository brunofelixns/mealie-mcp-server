"""Capture family cases from the pinned reference, never from the Python implementation.

Run inside the Dev Container: uv run python -m scripts.capture_cases FAMILY
"""

import argparse
import asyncio
import json

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from scripts.capture_reference import REFERENCE_IMAGE, UPSTREAM_COMMIT, dump
from tests.support.contracts import FIXTURES, assert_requests_match
from tests.support.fake_mealie import FakeMealie


async def capture(family: str, overwrite: bool) -> None:
    path = FIXTURES / "cases" / f"{family}.json"
    cases = json.loads(path.read_text())
    if not overwrite and any(case.get("expected_result") is not None for case in cases):
        raise ValueError("Baseline exists; compare differences before using --overwrite.")
    scenarios = json.loads((FIXTURES / "scenarios.json").read_text())
    requests = [request for case in cases for request in scenarios[case["scenario"]]["requests"]]
    with FakeMealie(requests) as fake:
        parameters = StdioServerParameters(
            command="docker",
            args=[
                "run",
                "--rm",
                "-i",
                "--network",
                "mealie-mcp-development_default",
                "--env",
                f"MEALIE_BASE_URL={fake.docker_url}",
                "--env",
                "MEALIE_API_KEY=reference-fixture-not-a-real-key",
                REFERENCE_IMAGE,
                "node",
                "dist/index.js",
            ],
        )
        async with Client(parameters, mode="legacy", read_timeout_seconds=30) as client:
            for case in cases:
                start = len(fake.recorded_requests)
                try:
                    result = await client.call_tool(case["tool"], case["arguments"])
                    case["expected_result"] = dump(result)
                except Exception as error:
                    if case.get("documented_difference") != "D07":
                        raise
                    case["expected_result"] = {
                        "protocolError": type(error).__name__,
                        "message": str(error),
                    }
                assert_requests_match(
                    fake.recorded_requests[start:],
                    case["expected_requests"],
                    case.get("request_order", "sequential"),
                )
    path.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"family": family, "cases": len(cases), "commit": UPSTREAM_COMMIT}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    asyncio.run(capture(args.family, args.overwrite))


if __name__ == "__main__":
    main()
