"""The real provider contract must pass before bootstrapping any mutable data."""

import copy
import json
import re
import sys
from types import SimpleNamespace

import httpx2 as httpx
import pytest

from tests.e2e import runner
from tests.e2e import stack as stack_module


def provider_schema():
    root = stack_module.ROOT
    fixture = json.loads((root / "tests/fixtures/mealie330/provider-contract.json").read_bytes())
    schema = copy.deepcopy(fixture["openapi"])
    catalog = json.loads((root / "src/mealie_mcp_server/resources/tool-catalog.json").read_bytes())
    for tool in catalog["tools"]:
        for endpoint in tool["endpoints"]:
            method, path, *_ = endpoint.split()
            route = next(
                (
                    old
                    for old in schema["paths"]
                    if re.sub(r"\{[^}]+\}", "{}", old.rstrip("/"))
                    == re.sub(r"\{[^}]+\}", "{}", path.rstrip("/"))
                ),
                path,
            )
            schema["paths"].setdefault(route, {}).setdefault(method.lower(), {})
    return schema


@pytest.mark.parametrize("drift", [False, True])
def test_stack_audits_downloaded_openapi_and_saves_per_run_evidence_before_credentials(
    tmp_path, monkeypatch, drift
):
    schema = provider_schema()
    if drift:
        schema["components"]["schemas"]["RecipeStep"]["properties"]["durationSeconds"]["anyOf"][0][
            "type"
        ] = "string"
    raw = json.dumps(schema).encode()
    requests = []

    def serve(request):
        requests.append(request)
        return httpx.Response(200, content=raw)

    real_client = httpx.Client

    def client(**kwargs):
        assert kwargs["trust_env"] is False
        return real_client(**kwargs, transport=httpx.MockTransport(serve))

    monkeypatch.setattr(stack_module.httpx, "Client", client)
    stack = stack_module.Stack("mealie-mcp-e2e-0123456789ab", "runtime:test", tmp_path)
    if drift:
        with pytest.raises(RuntimeError, match="API audit failed"):
            stack.audit_api()
    else:
        result = stack.audit_api()
        assert result["contractChecked"] is True
        assert result["contractErrors"] == []
    assert stack.secrets == ()
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/openapi.json"
    assert "authorization" not in requests[0].headers
    assert (tmp_path / "openapi.json").read_bytes() == raw
    report = json.loads((tmp_path / "api-audit.json").read_bytes())
    assert bool(report["contractErrors"]) is drift
    assert len(report["openapiSha256"]) == len(report["contractSha256"]) == 64


@pytest.mark.parametrize("audit_passes", [False, True])
def test_runner_gates_bootstrap_on_audit_and_always_cleans_owned_stack(
    tmp_path, monkeypatch, audit_passes
):
    events = []

    class DisposableStack:
        secrets = ()
        cleanup_errors = []
        env = {}

        def __init__(self, project, image, artifacts):
            self.artifacts = artifacts

        def resolve_image(self, *, build):
            events.append("resolve_image")
            return {}

        def start_mealie(self):
            events.append("start_mealie")

        def audit_api(self):
            events.append("audit_api")
            if not audit_passes:
                raise RuntimeError("API audit failed")
            return {"contractChecked": True, "contractErrors": []}

        def bootstrap(self, directory):
            events.append("bootstrap")
            (directory / "mutated-provider").write_text("bootstrap may mutate disposable data")
            return {}

        def cleanup(self):
            events.append("cleanup")
            return True

    def pytest_run(*args, **kwargs):
        events.append("pytest")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "Stack", DisposableStack)
    monkeypatch.setattr(runner.subprocess, "run", pytest_run)
    monkeypatch.setattr(runner, "validate_suite", lambda reports, names: {})
    monkeypatch.setattr(sys, "argv", ["runner", "--no-build"])
    result = runner.main()
    summary = json.loads((tmp_path / "artifacts/e2e-summary.json").read_bytes())
    assert summary["cleanupPassed"] is True
    if audit_passes:
        assert result == 0
        assert events == [
            "resolve_image",
            "start_mealie",
            "audit_api",
            "bootstrap",
            "pytest",
            "cleanup",
        ]
        assert summary["apiAudit"]["contractChecked"] is True
    else:
        assert result == 1
        assert events == ["resolve_image", "start_mealie", "audit_api", "cleanup"]
        assert summary["failedPhase"] == "api_audit"
