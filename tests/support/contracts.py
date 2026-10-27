"""Declarative contract cases; runtime comparator is added with the MCP adapter."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "compatibility"


@dataclass(frozen=True)
class ContractCase:
    tool: str
    arguments: dict[str, Any]
    scenario: str
    expected_requests: list[dict[str, Any]]
    expected_result: dict[str, Any]
    documented_difference: str | None = None
    expected_python_result: dict[str, Any] | None = None


def load_cases(family: str) -> list[ContractCase]:
    raw = json.loads((FIXTURES / "cases" / f"{family}.json").read_text())
    return [ContractCase(**case) for case in raw]


def _typed_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str)):
        return (type(value).__name__, value)
    if isinstance(value, (int, float)):
        return ("number", value)
    if isinstance(value, list):
        return ("array", [_typed_json(item) for item in value])
    return ("object", {key: _typed_json(item) for key, item in value.items()})


def _content(blocks: list[dict[str, Any]], *, is_error: bool) -> list[Any]:
    normalized = []
    for block in blocks:
        item = dict(block)
        if item.get("type") == "text" and not is_error:
            try:
                item["text"] = _typed_json(json.loads(item["text"]))
            except ValueError, TypeError:
                pass
        normalized.append(item)
    return normalized


async def assert_contract_matches(server: Any, case: ContractCase, fake: Any) -> None:
    from fastmcp import Client

    async with Client(server) as client:
        result = await client.call_tool(case.tool, case.arguments, raise_on_error=False)
    if case.expected_python_result is not None:
        assert case.documented_difference in {"D06", "D07"}
        expected = case.expected_python_result
    else:
        expected = case.expected_result
    is_error = bool(expected.get("isError", False))
    assert result.is_error == is_error
    actual_blocks = [
        block.model_dump(mode="json", by_alias=True, exclude_unset=True) for block in result.content
    ]
    assert _content(actual_blocks, is_error=is_error) == _content(
        expected["content"], is_error=is_error
    )
    assert _typed_json(result.structured_content) == _typed_json(expected.get("structuredContent"))
    assert fake.recorded_requests == case.expected_requests
    assert not fake.errors
