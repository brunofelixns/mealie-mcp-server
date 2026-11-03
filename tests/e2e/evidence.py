"""Fail closed on partial coverage, unexpected errors, or credential disclosure."""

import json
import re
from pathlib import Path

FILE_TOOL = "set_recipe_image_from_file"
AI_TOOLS = {"import_recipe_with_ai", "import_recipe_with_ai_with_progress"}
PROTOCOLS = ("2026-07-28", "2025-11-25")
PAIRS = {(transport, protocol) for transport in ("stdio", "http") for protocol in PROTOCOLS}


def _complete_records(records, names, *, rejected=False):
    if not isinstance(records, list) or len(records) != len(names):
        raise ValueError("Incomplete tool evidence")
    found = [record.get("tool") for record in records]
    if set(found) != names or len(set(found)) != len(found):
        raise ValueError("Missing or duplicated tool evidence")
    for record in records:
        checks = record.get("checks")
        if not isinstance(checks, list) or not checks or not all(checks):
            raise ValueError("Tool evidence requires completed assertions")
        if rejected:
            if not {"unknown_field_rejected", "value_redacted"} <= set(checks):
                raise ValueError("Incomplete argument-rejection evidence")
            continue
        expected = "security_rejection" if record["tool"] == FILE_TOOL else "positive"
        if record["tool"] in AI_TOOLS and record.get("outcome") == "configuration_rejection":
            if not {"provider_ai_unconfigured", "write_not_replayed"} <= set(checks):
                raise ValueError("AI tools require verified provider configuration and no replay")
            continue
        if record.get("outcome") != expected:
            raise ValueError("Unexpected tool outcome: " + str(record.get("tool")))
        if expected == "security_rejection" and not {
            "private_address_refused",
            "image_unchanged",
        } <= set(checks):
            raise ValueError("File tool requires the specific SSRF and unchanged-image assertions")


def validate_case(report: dict, names: set[str]) -> dict:
    if report.get("status") != "passed":
        raise ValueError("E2E case did not finish successfully")
    if (report.get("transport"), report.get("protocolVersion")) not in PAIRS:
        raise ValueError("Unexpected transport/protocol")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(report.get("imageId"))):
        raise ValueError("An immutable runtime image ID is required")
    required = {"catalog_78", "prompt", "transport_connected", "owned_data_removed"}
    if report["transport"] == "http":
        required.add("http_auth_401")
    if not required <= set(report.get("checks", [])):
        raise ValueError("Missing global E2E assertions")
    _complete_records(report.get("tools"), names)
    _complete_records(report.get("inputRejections"), names, rejected=True)
    configured_rejections = sum(
        item.get("outcome") == "configuration_rejection" for item in report["tools"]
    )
    return {
        "tools": len(names),
        "positive": len(names) - 1 - configured_rejections,
        "securityRejections": 1,
        "configurationRejections": configured_rejections,
        "inputRejections": len(names),
    }


def validate_suite(reports: list[dict], names: set[str]) -> dict:
    pairs = [(report.get("transport"), report.get("protocolVersion")) for report in reports]
    if len(reports) != 4 or set(pairs) != PAIRS:
        raise ValueError("All four distinct transport/protocol pairs are required")
    coverage = [validate_case(report, names) for report in reports]
    if len({report["imageId"] for report in reports}) != 1:
        raise ValueError("HTTP and stdio must use the same immutable runtime image")
    return {
        "status": "passed",
        "cases": 4,
        "toolsPerCase": len(names),
        "totalToolPaths": 4 * len(names),
        "positivePaths": sum(item["positive"] for item in coverage),
        "securityRejections": 4,
        "configurationRejections": sum(item["configurationRejections"] for item in coverage),
        "inputRejections": 4 * len(names),
    }


def write_report(path: Path, report: dict, *, secrets: tuple[str, ...] = ()) -> None:
    sensitive = {"authorization", "api_key", "apikey", "access_token", "auth_token", "password"}

    def inspect(value):
        if isinstance(value, dict):
            if sensitive & {str(key).lower() for key in value}:
                raise ValueError("Credential field refused in E2E report")
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    inspect(report)
    content = json.dumps(report, ensure_ascii=False, indent=2)
    if any(secret and secret in content for secret in secrets) or re.search(
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", content
    ):
        raise ValueError("Credential value refused in E2E report")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + "\n")
