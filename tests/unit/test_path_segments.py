"""Preserve the upstream query and route-segment contracts."""

import pytest

from mealie_mcp_server.mealie.client import build_query_string, encode_path_segment, format_params


@pytest.mark.parametrize("value", ["", " ", ".", "..", "../other", "a/b", "a\\b"])
def test_unsafe_segment_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        encode_path_segment(value)


def test_segment_is_encoded_once_and_trimmed() -> None:
    assert encode_path_segment(" soup?x=#à ") == "soup%3Fx%3D%23%C3%A0"
    assert encode_path_segment("%2F") == "%252F"


@pytest.mark.parametrize(
    "value, expected", [("\ufeffsoup\ufeff", "soup"), ("\x1csoup\x1c", "%1Csoup%1C")]
)
def test_segment_uses_javascript_whitespace_exactly(value, expected):
    assert encode_path_segment(value) == expected


def test_bom_only_segment_is_empty_under_javascript_trim():
    with pytest.raises(ValueError):
        encode_path_segment("\ufeff")


def test_format_params_distinguishes_false_and_empty() -> None:
    assert format_params(
        {"page": 1, "perPage": 50, "tags": ["a", "b"], "empty": [], "missing": None, "all": False}
    ) == {
        "page": "1",
        "perPage": "50",
        "tags": "a,b",
        "all": "false",
    }


def test_query_string_repeats_array_keys() -> None:
    assert build_query_string({"tags": ["a", "b"], "all": False, "search": "cheese & rice"}) == (
        "tags=a&tags=b&all=false&search=cheese+%26+rice"
    )


def test_query_numbers_follow_javascript_stringification_boundaries() -> None:
    assert format_params({"n": 1.0, "zero": -0.0, "small": 1e-7, "decimal": 1e20, "exp": 1e21}) == {
        "n": "1",
        "zero": "0",
        "small": "1e-7",
        "decimal": "100000000000000000000",
        "exp": "1e+21",
    }
