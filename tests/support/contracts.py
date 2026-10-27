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


def load_cases(family: str) -> list[ContractCase]:
    raw = json.loads((FIXTURES / "cases" / f"{family}.json").read_text())
    return [ContractCase(**case) for case in raw]
