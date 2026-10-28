import pytest

from tests.support.contracts import assert_requests_match

A = {"method": "POST", "path": "/api/example", "body": {"quantity": 0}}
B = {"method": "POST", "path": "/api/example", "body": {"quantity": 2}}


def test_sequential_contract_still_rejects_phase_reordering():
    with pytest.raises(AssertionError):
        assert_requests_match([B, A], [A, B])


def test_explicit_concurrent_contract_preserves_count_and_number_semantics():
    actual_a = {**A, "body": {"quantity": 0.0}}
    assert_requests_match([B, actual_a, B], [A, B, B], "concurrent")


def test_concurrent_comparison_never_drops_duplicates_or_boolean_types():
    with pytest.raises(AssertionError):
        assert_requests_match([A, B], [A, B, B], "concurrent")
    with pytest.raises(AssertionError):
        assert_requests_match([{**A, "body": {"quantity": False}}], [A], "concurrent")


def test_unknown_order_mode_rejected():
    with pytest.raises(AssertionError):
        assert_requests_match([A], [A], "ignore")
