import json
import subprocess

import pytest

from tests.containers import conftest


@pytest.mark.parametrize("arch", ["amd64", "arm64"])
def test_runtime_inspection_works_with_docker_api_148(monkeypatch, arch):
    monkeypatch.setenv("MCP_TEST_ARCH", arch)
    monkeypatch.setenv("MCP_TEST_IMAGE", "fixture-runtime:tested")

    def inspect(*arguments, **kwargs):
        if "--platform" in arguments:
            return subprocess.CompletedProcess(
                arguments, 1, "", '"--platform" requires API version 1.49'
            )
        assert arguments[:2] == ("image", "inspect")
        return subprocess.CompletedProcess(
            arguments, 0, json.dumps([{"Os": "linux", "Architecture": arch}]), ""
        )

    monkeypatch.setattr(conftest, "docker", inspect)
    assert conftest.runtime_image.__wrapped__() == "fixture-runtime:tested"


@pytest.mark.parametrize(
    "metadata",
    [{"Os": "windows", "Architecture": "amd64"}, {"Os": "linux", "Architecture": "arm64"}],
)
def test_compatible_inspection_still_rejects_the_wrong_platform(monkeypatch, metadata):
    monkeypatch.setenv("MCP_TEST_ARCH", "amd64")
    monkeypatch.setattr(
        conftest,
        "docker",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, json.dumps([metadata]), ""),
    )
    with pytest.raises(AssertionError, match="platform"):
        conftest.runtime_image.__wrapped__()
