from types import SimpleNamespace

import pytest

from tests.e2e import stack as module


@pytest.mark.parametrize("failure", ["logs", "disconnect", "down"])
def test_cleanup_attempts_teardown_even_when_an_earlier_step_raises(tmp_path, monkeypatch, failure):
    stack = module.Stack("mealie-mcp-e2e-0123456789ab", "runtime:test", tmp_path)
    stack.started = stack.connected = True
    stack.controller = "this-controller"
    attempted = []

    def compose_run(*args, **kwargs):
        step = "logs" if args[0] == "logs" else "down"
        attempted.append(step)
        if step == failure:
            raise OSError("simulated log storage or daemon failure")
        return SimpleNamespace(returncode=0, stdout="")

    def docker(*args, **kwargs):
        if args[:2] == ("network", "disconnect"):
            attempted.append("disconnect")
            if failure == "disconnect":
                raise OSError("simulated disconnect failure")
        if args[:2] == ("network", "inspect"):
            attempted.append("verify_network_removed")
            return SimpleNamespace(returncode=1, stdout="")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(stack, "compose_run", compose_run)
    monkeypatch.setattr(module, "docker", docker)
    assert stack.cleanup() is False
    assert attempted == ["logs", "disconnect", "down", "verify_network_removed"]
    assert stack.cleanup_errors == [failure + ":OSError"]
