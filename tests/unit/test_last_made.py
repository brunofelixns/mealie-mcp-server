import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from mealie_mcp_server.services.last_made import resolve_last_made_timestamp

CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures/compatibility/last-made-reference.json").read_text()
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["label"])
def test_matches_original_with_fixed_clock_and_timezone(case):
    kwargs = {"now": datetime.fromisoformat(case["now"]), "zone": ZoneInfo(case["zone"])}
    if "error" in case:
        with pytest.raises(ValueError) as caught:
            resolve_last_made_timestamp(case["input"], **kwargs)
        assert str(caught.value) == case["error"]
    else:
        assert resolve_last_made_timestamp(case["input"], **kwargs) == case["expected"]
