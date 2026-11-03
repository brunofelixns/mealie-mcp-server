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
ENGLISH_GROUPS = {
    "recipes": "Recipes",
    "mealplans": "Meal planning",
    "categories": "Categories",
    "tags": "Tags",
    "shopping_lists": "Shopping lists",
    "foods": "Foods",
    "units": "Units",
    "equipment": "Equipment",
}
BEGIN, END = "<!-- BEGIN GENERATED TOOLS -->", "<!-- END GENERATED TOOLS -->"


def render(root: Path) -> dict[Path, str]:
    catalog = json.loads((root / "src/mealie_mcp_server/resources/tool-catalog.json").read_text())
    inventory = json.loads((root / "docs/migration/compatibility-inventory.json").read_text())
    tools = catalog["tools"]
    owners = {tool["name"]: tool["group"] for tool in inventory["tools"]}
    assert len(tools) == len({tool["name"] for tool in tools})
    assert set(owners) == {tool["name"] for tool in tools}
    unsupported = set(owners.values()) - GROUPS.keys()
    if unsupported:
        raise ValueError("Unsupported documentation groups: " + ", ".join(sorted(unsupported)))
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    sections = {
        "README.md": [
            f"## Available tools ({len(tools)})",
            "",
            f"Catalog for version {version}. "
            "See the [full schemas](docs/tools.md) and "
            "[API coverage](docs/api-coverage.md) (in Spanish). <!-- x-release-please-version -->",
            "",
        ],
        "docs/README.es.md": [
            f"## Herramientas disponibles ({len(tools)})",
            "",
            f"Catálogo de la versión {version}. "
            "Consulta los [esquemas completos](tools.md) y "
            "la [cobertura de API](api-coverage.md). <!-- x-release-please-version -->",
            "",
        ],
    }
    coverage = [
        "# Cobertura de API",
        "",
        "Generado con `uv run python scripts/generate_docs.py`. "
        f"Catálogo explícito de {len(tools)} herramientas; "
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
    for relative, section in sections.items():
        spanish = relative == "docs/README.es.md"
        titles = GROUPS if spanish else ENGLISH_GROUPS
        section.extend(
            ["| Familia | Herramientas |" if spanish else "| Family | Tools |", "|---|---:|"]
        )
        section.extend(f"| {title} | {len(grouped[group])} |" for group, title in titles.items())
        section.extend([f"| **Total** | **{len(tools)}** |", ""])
        for group, title in titles.items():
            members = grouped[group]
            noun = "herramientas" if spanish else "tools"
            section.extend(
                [
                    "<details>",
                    f"<summary><strong>{title}</strong> · {len(members)} {noun}</summary>",
                    "",
                    ", ".join("`" + tool["name"] + "`" for tool in members),
                    "",
                    "</details>",
                    "",
                ]
            )
    coverage.extend(f"| {title} | {len(grouped[group])} |" for group, title in GROUPS.items())
    coverage.extend([f"| **Total** | **{len(tools)}** |", ""])
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
    rendered = {
        root / "API_COVERAGE.md": (
            "# API coverage\n\nSee the [generated documentation](docs/api-coverage.md) "
            "and [full schemas](docs/tools.md), maintained in Spanish.\n"
        ),
        root / "docs/api-coverage.md": "\n".join(coverage),
        root / "docs/tools.md": "\n".join(reference),
    }
    for relative, section in sections.items():
        readme = (root / relative).read_text()
        if readme.count(BEGIN) != 1 or readme.count(END) != 1:
            raise ValueError(f"{relative} needs one pair of generated-tools markers")
        rendered[root / relative] = re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END),
            lambda _, section=section: BEGIN + "\n" + "\n".join(section).rstrip() + "\n" + END,
            readme,
            flags=re.DOTALL,
        )
    return rendered


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
    count = len(
        json.loads((args.root / "src/mealie_mcp_server/resources/tool-catalog.json").read_text())[
            "tools"
        ]
    )
    print(f"Documentation checked: {count} tools, one prompt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
