import importlib.util
import json
import subprocess
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/review_python_dependencies.py"


def load_reviewer():
    assert SCRIPT.exists(), "Direct Python dependency review is not implemented"
    spec = importlib.util.spec_from_file_location("review_python_dependencies", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lockfile(*packages):
    return "version = 1\n" + "".join(
        f'\n[[package]]\nname = "{name}"\nversion = "{version}"\nsource = {{ {source} }}\n'
        for name, version, source in packages
    )


PYPI = 'registry = "https://pypi.org/simple"'
SELF = ("mealie-mcp-server", "0.1.0", 'editable = "."')


@pytest.fixture
def repository(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    git("init", "-qb", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (tmp_path / "uv.lock").write_text(lockfile(SELF, ("Flask", "1.0.0", PYPI)))
    git("add", "uv.lock")
    git("commit", "-qm", "chore: baseline")
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"base": {"sha": git("rev-parse", "HEAD")}}}))
    return tmp_path, event


@pytest.fixture
def api_server():
    servers = []

    def start(responses):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(
                    {"path": self.path, "authorization": self.headers.get("Authorization")}
                )
                status, body, headers = responses.pop(0)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value.replace("{origin}", origin))
                self.end_headers()
                self.wfile.write(
                    body.encode() if isinstance(body, str) else json.dumps(body).encode()
                )

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        origin = f"http://127.0.0.1:{server.server_port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return origin + "/advisories", requests

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def advisory(severity="high", ghsa="GHSA-abcd-1234-efgh", withdrawn=None):
    return {"ghsa_id": ghsa, "severity": severity, "withdrawn_at": withdrawn}


def test_reviews_added_transitive_and_dev_versions_and_normalizes_names(repository, api_server):
    root, event = repository
    (root / "uv.lock").write_text(
        lockfile(
            SELF,
            ("flask", "1.0.0", PYPI),
            ("Transitive_Dep", "2.0.0", PYPI),
            ("dev.tool", "3.0.0", PYPI),
        )
    )
    endpoint, requests = api_server([(200, [], {})])
    report = load_reviewer().review_dependencies(root, event, api_url=endpoint)
    assert report["addedOrChanged"] == ["dev-tool@3.0.0", "transitive-dep@2.0.0"]
    assert report["findings"] == []
    assert report["unsupportedExternalSources"] == []
    assert report["passed"] is True
    assert len(requests) == 1
    query = parse_qs(urlsplit(requests[0]["path"]).query)
    assert query["affects"] == ["dev-tool@3.0.0,transitive-dep@2.0.0"]
    assert query["ecosystem"] == ["pip"]
    assert query["type"] == ["reviewed"]
    assert requests[0]["authorization"] is None


def test_changed_version_is_audited_and_high_or_critical_findings_fail(repository, api_server):
    root, event = repository
    (root / "uv.lock").write_text(lockfile(SELF, ("flask", "2.0.0", PYPI)))
    endpoint, _ = api_server(
        [(200, [advisory(), advisory("critical", "GHSA-aaaa-bbbb-cccc"), advisory("medium")], {})]
    )
    report = load_reviewer().review_dependencies(root, event, api_url=endpoint)
    assert report["addedOrChanged"] == ["flask@2.0.0"]
    assert report["passed"] is False
    assert {item["severity"] for item in report["findings"]} == {"high", "critical"}


def test_follows_pagination_before_accepting_an_empty_first_page(repository, api_server):
    root, event = repository
    (root / "uv.lock").write_text(lockfile(SELF, ("flask", "2.0.0", PYPI)))
    query = "ecosystem=pip&type=reviewed&is_withdrawn=false&per_page=100&affects=flask%402.0.0"
    endpoint, requests = api_server(
        [
            (200, [], {"Link": f'<{{origin}}/advisories?{query}&after=cursor>; rel="next"'}),
            (200, [advisory()], {}),
        ]
    )
    report = load_reviewer().review_dependencies(root, event, api_url=endpoint)
    assert len(requests) == 2
    assert report["passed"] is False


@pytest.mark.parametrize(
    "response",
    [
        (503, {"message": "unavailable"}, {}),
        (200, "not json", {}),
        (200, {"message": "not an advisory list"}, {}),
        (200, [{"ghsa_id": "GHSA-abcd-1234-efgh"}], {}),
        (200, [advisory("unexpected")], {}),
        (200, [], {"Link": "malformed pagination"}),
        (200, [], {"Link": '<https://other.invalid/advisories?after=1>; rel="next"'}),
        (200, [], {"Link": '<{origin}/advisories?after=1>; rel="next"'}),
    ],
)
def test_provider_or_pagination_failure_is_never_a_clean_review(repository, api_server, response):
    root, event = repository
    (root / "uv.lock").write_text(lockfile(SELF, ("flask", "2.0.0", PYPI)))
    endpoint, _ = api_server([response])
    with pytest.raises(ValueError, match="advisory"):
        load_reviewer().review_dependencies(root, event, api_url=endpoint)


def test_reports_non_pypi_sources_without_exposing_their_urls(repository, api_server):
    root, event = repository
    (root / "uv.lock").write_text(
        lockfile(
            SELF,
            ("flask", "1.0.0", PYPI),
            ("local-helper", "1.0.0", 'path = "../helper"'),
            ("git-helper", "2.0.0", 'git = "https://credential@example.invalid/repo"'),
            ("private-helper", "3.0.0", 'registry = "https://token@example.invalid/simple"'),
        )
    )
    endpoint, requests = api_server([])
    report = load_reviewer().review_dependencies(root, event, api_url=endpoint)
    assert report["addedOrChanged"] == []
    assert report["unsupportedExternalSources"] == [
        {"package": "git-helper@2.0.0", "source": "git"},
        {"package": "local-helper@1.0.0", "source": "path"},
        {"package": "private-helper@3.0.0", "source": "registry"},
    ]
    assert "credential" not in json.dumps(report)
    assert "token" not in json.dumps(report)
    assert requests == []


@pytest.mark.parametrize(
    "sha", ["main", "--help", "a" * 39, "a" * 40 + ":README.md", "$(touch marker)"]
)
def test_invalid_base_sha_fails_before_git_or_network(repository, sha):
    root, event = repository
    event.write_text(json.dumps({"pull_request": {"base": {"sha": sha}}}))
    with pytest.raises(ValueError, match="base commit"):
        load_reviewer().review_dependencies(root, event)
    assert not (root / "marker").exists()


@pytest.mark.parametrize(
    "contents",
    [
        "not toml",
        "version = 1",
        '[[package]]\nname = "dep"\nversion = "1.0"',
        '[[package]]\nname = "dep@extra"\nversion = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }',
        '[[package]]\nname = "dep"\nversion = "1.0,other@1"\n'
        'source = { registry = "https://pypi.org/simple" }',
    ],
)
def test_malformed_lock_data_is_never_a_clean_review(repository, contents):
    root, event = repository
    (root / "uv.lock").write_text(contents)
    with pytest.raises(ValueError, match="lock"):
        load_reviewer().review_dependencies(root, event)


def test_unchanged_or_removed_versions_need_no_advisory_request(repository, api_server):
    root, event = repository
    (root / "uv.lock").write_text(lockfile(SELF))
    endpoint, requests = api_server([])
    report = load_reviewer().review_dependencies(root, event, api_url=endpoint)
    assert report["passed"] is True
    assert requests == []


def test_cli_writes_machine_readable_evidence_for_an_unchanged_lock(repository):
    root, event = repository
    output = root / "artifacts/python-dependency-review.json"
    assert SCRIPT.exists(), "Direct Python dependency review is not implemented"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--event",
            str(event),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())["passed"] is True


def test_batches_many_packages_without_losing_any_exact_version(api_server):
    endpoint, requests = api_server([(200, [], {}), (200, [], {})])
    packages = [f"package-{number}@1.0.0" for number in range(51)]
    assert load_reviewer().advisory_findings(packages, endpoint) == []
    queried = [
        package
        for request in requests
        for package in parse_qs(urlsplit(request["path"]).query)["affects"][0].split(",")
    ]
    assert queried == packages


def test_withdrawn_advisories_do_not_block_a_new_version(api_server):
    endpoint, _ = api_server([(200, [advisory(withdrawn="2026-11-01T00:00:00Z")], {})])
    assert load_reviewer().advisory_findings(["flask@2.0.0"], endpoint) == []


def test_cli_failure_retains_failed_evidence_instead_of_a_clean_report(repository):
    root, event = repository
    event.write_text('{"pull_request":{"base":{"sha":"main"}}}')
    output = root / "artifacts/python-dependency-review.json"
    assert SCRIPT.exists(), "Direct Python dependency review is not implemented"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--event",
            str(event),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    report = json.loads(output.read_text())
    assert report["passed"] is False
    assert report["complete"] is False
    assert "base commit" in report["error"]


def test_explicit_ci_token_is_sent_only_to_the_official_advisory_endpoint(api_server, monkeypatch):
    endpoint, _ = api_server([(200, [], {})])
    reviewer = load_reviewer()
    emitted = []
    real_open = urllib.request.OpenerDirector.open

    def capture_request(opener, request, *args, **kwargs):
        emitted.append((request.full_url, request.get_header("Authorization")))
        return real_open(opener, urllib.request.Request(endpoint), *args, **kwargs)

    monkeypatch.setenv("GH_ADVISORY_TOKEN", "fixture-advisory-token")
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", capture_request)
    assert reviewer.advisory_findings(["flask@2.0.0"], reviewer.API_URL) == []
    assert len(emitted) == 1
    assert emitted[0][0].startswith("https://api.github.com/advisories?")
    assert emitted[0][1] == "Bearer fixture-advisory-token"


def test_injected_provider_never_receives_the_ci_token(api_server, monkeypatch):
    endpoint, requests = api_server([(200, [], {})])
    monkeypatch.setenv("GH_ADVISORY_TOKEN", "fixture-advisory-token")
    assert load_reviewer().advisory_findings(["flask@2.0.0"], endpoint) == []
    assert requests[0]["authorization"] is None


def test_provider_redirect_is_not_followed(api_server):
    redirected, redirected_requests = api_server([(200, [], {})])
    endpoint, _ = api_server([(302, "", {"Location": redirected})])
    with pytest.raises(ValueError, match="advisory"):
        load_reviewer().advisory_findings(["flask@2.0.0"], endpoint)
    assert redirected_requests == []
