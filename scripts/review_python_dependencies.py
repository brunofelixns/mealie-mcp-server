"""Review newly locked PyPI versions using GitHub's public advisory API.

uv.lock is not a documented GitHub dependency-graph format. This read-only
complement includes all locked versions, including transitive and dev packages.
It does not install packages or submit dependency snapshots. CI may explicitly
provide a read-only GH_ADVISORY_TOKEN for requests to the official endpoint.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_URL = "https://api.github.com/advisories"
NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")
VERSION = re.compile(
    r"(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?"
    r"(?:\.post[0-9]+)?(?:\.dev[0-9]+)?(?:\+[a-z0-9]+(?:[._-][a-z0-9]+)*)?",
    re.IGNORECASE,
)


class RejectAdvisoryRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise ValueError("GitHub advisory redirects are not permitted")


def locked_packages(contents: str) -> tuple[set[str], list[dict[str, str]]]:
    try:
        packages = tomllib.loads(contents)["package"]
    except (ValueError, KeyError) as error:
        raise ValueError("Invalid uv.lock package data") from error
    if not isinstance(packages, list) or not packages:
        raise ValueError("Invalid uv.lock package list")
    pypi = set()
    unsupported = []
    for package in packages:
        if not isinstance(package, dict):
            raise ValueError("Invalid uv.lock package record")
        name, version, source = (package.get(key) for key in ("name", "version", "source"))
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError("Invalid uv.lock package name")
        name = re.sub(r"[-_.]+", "-", name).lower()
        if not isinstance(source, dict) or len(source) != 1:
            raise ValueError("Invalid uv.lock package source")
        kind, location = next(iter(source.items()))
        if kind not in {"registry", "editable", "virtual", "path", "git", "url"} or not isinstance(
            location, str
        ):
            raise ValueError("Invalid uv.lock package source")
        if kind in {"editable", "virtual"} and location == ".":
            continue  # The repository itself is not an external PyPI dependency.
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            raise ValueError("Invalid uv.lock package version")
        identifier = f"{name}@{version}"
        if kind == "registry" and location.rstrip("/") == "https://pypi.org/simple":
            pypi.add(identifier)
        else:
            # Report the gap without exposing credential-bearing source URLs.
            unsupported.append({"package": identifier, "source": kind})
    return pypi, sorted(unsupported, key=lambda item: (item["package"], item["source"]))


def next_page(link: str | None, api_url: str, parameters: dict[str, str]) -> str | None:
    if not link:
        return None
    result = None
    for part in link.split(","):
        match = re.fullmatch(r'\s*<([^>]+)>;\s*rel="([^"]+)"\s*', part)
        if not match:
            raise ValueError("Invalid GitHub advisory pagination header")
        if "next" not in match[2].split():
            continue
        if result is not None:
            raise ValueError("Duplicate GitHub advisory pagination link")
        candidate = urllib.parse.urlsplit(match[1])
        endpoint = urllib.parse.urlsplit(api_url)
        query = urllib.parse.parse_qs(candidate.query)
        if (
            (candidate.scheme, candidate.netloc, candidate.path)
            != (endpoint.scheme, endpoint.netloc, endpoint.path)
            or candidate.fragment
            or any(query.get(key) != [value] for key, value in parameters.items())
        ):
            raise ValueError("Unsafe or incomplete GitHub advisory pagination link")
        result = match[1]
    return result


def advisory_findings(packages: list[str], api_url: str) -> list[dict[str, str]]:
    findings = {}
    opener = urllib.request.build_opener(RejectAdvisoryRedirects())
    # A test provider or alternate host must never receive CI credentials.
    token = os.environ.get("GH_ADVISORY_TOKEN") if api_url == API_URL else None
    if token and any(character in token for character in ("\r", "\n")):
        raise ValueError("Invalid GitHub advisory token environment value")
    for start in range(0, len(packages), 50):
        parameters = {
            "ecosystem": "pip",
            "type": "reviewed",
            "is_withdrawn": "false",
            "per_page": "100",
            "affects": ",".join(packages[start : start + 50]),
        }
        url = api_url + "?" + urllib.parse.urlencode(parameters)
        visited = set()
        while url:
            if url in visited or len(visited) >= 1000:
                raise ValueError("Cyclic or excessive GitHub advisory pagination")
            visited.add(url)
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "mealie-mcp-server-dependency-review",
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"
            request = urllib.request.Request(url, headers=headers)
            try:
                with opener.open(request, timeout=30) as response:
                    raw = response.read(10 * 1024 * 1024 + 1)
                    if len(raw) > 10 * 1024 * 1024:
                        raise ValueError("Oversized GitHub advisory response")
                    data = json.loads(raw)
                    link = response.headers.get("Link")
            except urllib.error.HTTPError as error:
                raise ValueError(f"GitHub advisory provider returned HTTP {error.code}") from error
            except (OSError, urllib.error.URLError, ValueError) as error:
                raise ValueError(
                    "GitHub advisory provider request or JSON parsing failed"
                ) from error
            if not isinstance(data, list):
                raise ValueError("Invalid GitHub advisory response: expected a list")
            for item in data:
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("ghsa_id"), str)
                    or not re.fullmatch(
                        r"GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}", item["ghsa_id"]
                    )
                    or item.get("severity") not in {"unknown", "low", "medium", "high", "critical"}
                    or "withdrawn_at" not in item
                ):
                    raise ValueError("Incomplete GitHub advisory record")
                if item["withdrawn_at"] is None and item["severity"] in {"high", "critical"}:
                    finding = {"ghsa": item["ghsa_id"], "severity": item["severity"]}
                    if item["ghsa_id"] in findings and findings[item["ghsa_id"]] != finding:
                        raise ValueError("Inconsistent GitHub advisory records")
                    findings[item["ghsa_id"]] = finding
            url = next_page(link, api_url, parameters)
    return [findings[key] for key in sorted(findings)]


def review_dependencies(
    root: Path, event_path: Path, *, api_url: str = API_URL
) -> dict[str, object]:
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
        base = event["pull_request"]["base"]["sha"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError("Cannot read the PR base commit from the event") from error
    if not isinstance(base, str) or not re.fullmatch(r"[0-9a-f]{40}", base):
        raise ValueError("Invalid PR base commit SHA")
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{base}:uv.lock"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise ValueError("Cannot read uv.lock at the PR base commit")
    baseline, _ = locked_packages(result.stdout)
    current, unsupported = locked_packages((root / "uv.lock").read_text(encoding="utf-8"))
    added = sorted(current - baseline)
    findings = advisory_findings(added, api_url)
    return {
        "baseCommit": base,
        "provider": "GitHub reviewed security advisories",
        "complete": True,
        "addedOrChanged": added,
        "unsupportedExternalSources": unsupported,
        "findings": findings,
        "passed": not findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--event", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/python-dependency-review.json")
    )
    args = parser.parse_args()
    try:
        if args.event is None:
            raise ValueError("Provide --event or GITHUB_EVENT_PATH")
        report = review_dependencies(args.root, args.event)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report = {"complete": False, "passed": False, "error": str(error)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
