"""Exercise the distributed wheel, independently of the source checkout."""

import subprocess
from pathlib import Path

from tests.support.version import PROJECT_VERSION


def test_package_version_matches_metadata(tmp_path: Path) -> None:
    """Catch a wheel missing the import package or reporting another distribution version."""
    repository = Path(__file__).resolve().parents[2]
    wheel_dir = tmp_path / "wheels"
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    wheel = next(wheel_dir.glob("*.whl"))
    environment = tmp_path / "installed"
    subprocess.run(["uv", "venv", str(environment)], check=True, capture_output=True)
    executable = environment / "bin" / "python"
    subprocess.run(
        ["uv", "pip", "install", "--python", str(executable), "--no-deps", str(wheel)],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        [
            str(executable),
            "-I",
            "-c",
            "import sys; from importlib.metadata import version; "
            "import mealie_mcp_server as package; "
            "assert package.version() == version('mealie-mcp-server') == sys.argv[1]; "
            "print(package.__file__)",
            PROJECT_VERSION,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert str(environment) in result.stdout
    assert str(repository / "src") not in result.stdout
