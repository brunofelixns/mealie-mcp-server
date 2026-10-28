"""Generate documentation from the same curated catalog advertised by the server."""

import argparse
import json
import re
import sys
import tempfile
import tomllib
from pathlib import Path

GROUPS = {
    "recipes": "Recetas",
    "mealplans": "Planificación",
    "categories": "Categorías",
    "tags": "Etiquetas",
    "shopping_lists": "Compras",
    "foods": "Alimentos",
    "units": "Unidades",
    "equipment": "Equipamiento",
}
BEGIN, END = "<!-- BEGIN GENERATED TOOLS -->", "<!-- END GENERATED TOOLS -->"


def render(root: Path) -> dict[Path, str]:
    catalog = json.loads((root / "src/mealie_mcp_server/resources/tool-catalog.json").read_text())
    inventory = json.loads((root / "docs/migration/compatibility-inventory.json").read_text())
    tools = catalog["tools"]
    owners = {tool["name"]: tool["group"] for tool in inventory["tools"]}
    assert len(tools) == len({tool["name"] for tool in tools}) == 78
    assert set(owners) == {tool["name"] for tool in tools}
    unsupported = set(owners.values()) - GROUPS.keys()
    if unsupported:
        raise ValueError("Unsupported documentation groups: " + ", ".join(sorted(unsupported)))
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    section = [
        f"## Herramientas disponibles ({len(tools)})",
        "",
        f"Catálogo de la versión {version}. "
        "Consulta los [esquemas completos](docs/tools.md) y "
        "la [cobertura de API](docs/api-coverage.md).",
        "",
    ]
    coverage = [
        "# Cobertura de API",
        "",
        "Generado con `uv run python scripts/generate_docs.py`. "
        "Catálogo explícito de 78 herramientas; "
        "los tipos completos están en [tools.md](tools.md).",
        "",
        "| Familia | Herramientas |",
        "|---|---:|",
    ]
    reference = [
        "# Referencia MCP",
        "",
        "Generada desde resources/tool-catalog.json, el contrato público usado por el servidor. "
        "Se conservan nombres camelCase, obligatoriedad, annotations y metadata declaradas. "
        "No se añaden outputSchema ni structuredContent. "
        "El prompt weekly-meal-plan acepta preferences opcional.",
        "",
    ]
    grouped = {
        group: sorted(
            (tool for tool in tools if owners[tool["name"]] == group), key=lambda tool: tool["name"]
        )
        for group in GROUPS
    }
    section.extend(["| Familia | Herramientas |", "|---|---:|"])
    section.extend(f"| {title} | {len(grouped[group])} |" for group, title in GROUPS.items())
    section.extend([f"| **Total** | **{len(tools)}** |", ""])
    for group, title in GROUPS.items():
        members = grouped[group]
        section.extend(
            [
                "<details>",
                f"<summary><strong>{title}</strong> · {len(members)} herramientas</summary>",
                "",
                ", ".join("`" + tool["name"] + "`" for tool in members),
                "",
                "</details>",
                "",
            ]
        )
        coverage.append(f"| {title} | {len(members)} |")
    coverage.extend(["| **Total** | **78** |", ""])
    for tool in tools:
        name = tool["name"]
        endpoints = tool["endpoints"]
        if not endpoints:
            raise ValueError(f"Missing endpoint mapping: {name}")
        coverage.extend(
            [
                f"## `{name}`",
                "",
                tool["description"],
                "",
                *("- " + endpoint for endpoint in endpoints),
                "",
            ]
        )
        reference.extend(
            [
                "## " + name,
                "",
                tool["description"],
                "",
                "```json",
                json.dumps(tool["inputSchema"], ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    readme = (root / "README.md").read_text()
    if readme.count(BEGIN) != 1 or readme.count(END) != 1:
        raise ValueError("README needs one pair of generated-tools markers")
    readme = re.sub(
        re.escape(BEGIN) + r".*?" + re.escape(END),
        lambda _: BEGIN + "\n" + "\n".join(section).rstrip() + "\n" + END,
        readme,
        flags=re.DOTALL,
    )
    return {
        root / "README.md": readme,
        root / "API_COVERAGE.md": (
            "# Cobertura de API\n\nVer [la documentación generada](docs/api-coverage.md) "
            "y [los esquemas completos](docs/tools.md).\n"
        ),
        root / "docs/api-coverage.md": "\n".join(coverage),
        root / "docs/tools.md": "\n".join(reference),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render(args.root)
    stale = [
        path
        for path, content in expected.items()
        if not path.exists() or path.read_text() != content
    ]
    if args.check:
        if stale:
            print(
                "Generated docs are stale: "
                + ", ".join(str(path.relative_to(args.root)) for path in stale),
                file=sys.stderr,
            )
            return 1
    else:
        for path in stale:
            content = expected[path]
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=path.parent,
                    prefix="." + path.name + ".",
                    delete=False,
                ) as stream:
                    temporary = Path(stream.name)
                    stream.write(content)
                temporary.chmod(0o644)
                temporary.replace(path)
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
    print("Documentation checked: 78 tools, one prompt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
