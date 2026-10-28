import copy
import json
from pathlib import Path

import pytest

from tests.e2e.evidence import validate_case, validate_suite, write_report

CATALOG = Path(__file__).resolve().parents[2] / "src/mealie_mcp_server/resources/tool-catalog.json"
NAMES = {tool["name"] for tool in json.loads(CATALOG.read_text())["tools"]}
IMAGE = "sha256:" + "a" * 64


def complete_case(transport="stdio", protocol="2026-07-28"):
    return {
        "status": "passed",
        "transport": transport,
        "protocolVersion": protocol,
        "imageId": IMAGE,
        "checks": ["catalog_78", "prompt", "transport_connected", "owned_data_removed"]
        + (["http_auth_401"] if transport == "http" else []),
        "tools": [
            {
                "tool": name,
                "outcome": "security_rejection"
                if name == "set_recipe_image_from_file"
                else "positive",
                "checks": ["private_address_refused", "image_unchanged"]
                if name == "set_recipe_image_from_file"
                else ["result_verified"],
            }
            for name in sorted(NAMES)
        ],
        "inputRejections": [
            {"tool": name, "checks": ["unknown_field_rejected", "value_redacted"]}
            for name in sorted(NAMES)
        ],
    }


def test_complete_evidence_distinguishes_77_positives_and_security_rejection():
    report = complete_case()
    assert validate_case(report, NAMES) == {
        "tools": 78,
        "positive": 77,
        "securityRejections": 1,
        "inputRejections": 78,
    }


@pytest.mark.parametrize(
    "defect", ["missing", "duplicate", "provider_error", "no_checks", "missing_rejection", "failed"]
)
def test_incomplete_or_unverified_evidence_never_passes(defect):
    report = complete_case()
    if defect == "missing":
        report["tools"].pop()
    elif defect == "duplicate":
        report["tools"][-1] = copy.deepcopy(report["tools"][0])
    elif defect == "provider_error":
        report["tools"][0]["outcome"] = "expected_provider_error"
    elif defect == "no_checks":
        report["tools"][0]["checks"] = []
    elif defect == "missing_rejection":
        report["inputRejections"].pop()
    else:
        report["status"] = "failed"
    with pytest.raises(ValueError):
        validate_case(report, NAMES)


def test_suite_requires_all_four_transport_protocol_pairs_and_same_image():
    reports = [
        complete_case(transport, protocol)
        for transport in ("stdio", "http")
        for protocol in ("2026-07-28", "2025-11-25")
    ]
    assert validate_suite(reports, NAMES)["totalToolPaths"] == 312
    with pytest.raises(ValueError):
        validate_suite(reports[:-1], NAMES)
    reports[-1]["imageId"] = "sha256:" + "b" * 64
    with pytest.raises(ValueError):
        validate_suite(reports, NAMES)


@pytest.mark.parametrize("leak", ["known_secret", "credential_field"])
def test_secret_guard_refuses_to_write_sensitive_report(tmp_path, leak):
    report = complete_case()
    secret = "fixture-personal-token-that-must-not-be-recorded"
    if leak == "known_secret":
        report["detail"] = secret
    else:
        report["authorization"] = "anything"
    path = tmp_path / "report.json"
    with pytest.raises(ValueError):
        write_report(path, report, secrets=(secret,))
    assert not path.exists()
