"""Build/start/verify/clean the complete local Docker test environment."""

import argparse
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from tests.e2e.context import catalog_names
from tests.e2e.evidence import validate_suite, write_report
from tests.e2e.stack import ROOT, Stack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mealie-mcp-server:e2e")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    project = "mealie-mcp-e2e-" + uuid.uuid4().hex[:12]
    artifacts = ROOT / "artifacts/e2e" / project
    artifacts.mkdir(parents=True, exist_ok=False)
    stack = Stack(project, args.image, artifacts)
    report = {"status": "failed", "project": project, "artifacts": str(artifacts.relative_to(ROOT))}
    phase = "build"
    success = False
    cleanup = False
    with tempfile.TemporaryDirectory(prefix=project + "-") as directory:
        try:
            print("E2E: resolving installed runtime image", flush=True)
            report["runtime"] = stack.resolve_image(build=not args.no_build)
            phase = "start_mealie"
            print("E2E: starting isolated local Mealie", flush=True)
            stack.start_mealie()
            phase = "bootstrap"
            report["stack"] = stack.bootstrap(Path(directory))
            phase = "pytest"
            print("E2E: running all 78 tools through stdio/HTTP and both protocol eras", flush=True)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/integration/test_mealie_roundtrip.py",
                    "-m",
                    "live",
                    "-q",
                    "--junitxml=" + str(artifacts / "pytest.xml"),
                ],
                cwd=ROOT,
                env=stack.env,
                capture_output=True,
                text=True,
                timeout=1200,
            )
            (artifacts / "pytest.log").write_text(result.stdout + result.stderr)
            print((result.stdout + result.stderr)[-7000:], flush=True)
            reports = [
                json.loads(path.read_text()) for path in sorted(artifacts.glob("case-*.json"))
            ]
            if result.returncode:
                raise RuntimeError("E2E pytest failed; inspect pytest.log and case reports")
            phase = "coverage_gate"
            report["coverage"] = validate_suite(reports, catalog_names())
            success = True
        except Exception as error:
            report.update(failedPhase=phase, failureType=type(error).__name__)
            print("E2E failed during " + phase + "; inspect " + str(artifacts), flush=True)
        finally:
            print("E2E: removing only this run's containers, network and volumes", flush=True)
            try:
                cleanup = stack.cleanup()
            except Exception as error:
                report["cleanupFailureType"] = type(error).__name__
            if stack.cleanup_errors:
                report["cleanupErrors"] = stack.cleanup_errors
            report["cleanupPassed"] = cleanup
            report["status"] = "passed" if success and cleanup else "failed"
            write_report(artifacts / "summary.json", report, secrets=stack.secrets)
            write_report(ROOT / "artifacts/e2e-summary.json", report, secrets=stack.secrets)
    print(json.dumps(report, indent=2), flush=True)
    return 0 if success and cleanup else 1


if __name__ == "__main__":
    sys.exit(main())
