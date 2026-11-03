"""Compare a local provider OpenAPI document with explicit catalog dependencies.

The default versioned contract checks a focused request/response schema subset.
This is not proof of complete API support or runtime feature completeness. It
never fetches credentials, calls a provider or rewrites compatibility captures.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "tests/fixtures/mealie330/provider-contract.json"
CATALOG = ROOT / "src/mealie_mcp_server/resources/tool-catalog.json"
METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
SCHEMA_ANNOTATIONS = {
    "title",
    "description",
    "default",
    "examples",
    "example",
    "$comment",
    "deprecated",
    "readOnly",
    "writeOnly",
    "contentMediaType",
    "contentEncoding",
}
# Every allowed assertion has comparison logic below. A new schema assertion must
# gain explicit semantics and regression tests before it can pass this guard.
SUPPORTED_SCHEMA_KEYWORDS = SCHEMA_ANNOTATIONS | {
    "type",
    "format",
    "enum",
    "const",
    "anyOf",
    "properties",
    "required",
    "items",
    "additionalProperties",
    "minimum",
    "exclusiveMinimum",
    "maximum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "minProperties",
    "maxProperties",
    "pattern",
    "multipleOf",
    "uniqueItems",
}
RECIPE_PREFIXES = (
    "/api/recipes",
    "/api/comments",
    "/api/shared/recipes",
    "/api/media/recipes",
    "/api/households/self/recipes",
    "/api/households/recipe-actions",
    "/api/households/cookbooks",
    "/api/households/mealplans",
    "/api/parser",
    "/api/users/self/favorites",
    "/api/users/self/ratings",
)
# Native batch aliases are deliberately not presented as identical contracts.
ALTERNATIVES = {
    "PUT /api/households/cookbooks": ["update_cookbook"],
    "PUT /api/recipes": [
        "update_recipe_metadata_batch",
        "update_recipe_ingredients_batch",
        "update_recipe_instructions_batch",
        "update_recipe_taxonomy_batch",
        "update_recipe_tools_batch",
    ],
    "PATCH /api/recipes": ["update_recipe_metadata_batch"],
    "POST /api/recipes/bulk-actions/tag": ["update_recipe_taxonomy_batch"],
    "POST /api/recipes/bulk-actions/categorize": ["update_recipe_taxonomy_batch"],
    "POST /api/recipes/bulk-actions/settings": ["update_recipe_metadata_batch"],
}


def normalized(endpoint: str) -> str:
    method, path, *_ = endpoint.split()
    return method.upper() + " " + re.sub(r"\{[^}]+\}", "{}", path.rstrip("/"))


def _json_equal(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _json_equal(left[key], right[key]) for key in left
        )
    return left == right


def _resolve(node: dict, document: dict) -> dict:
    """Resolve local JSON pointers only, without network or filesystem access."""
    visited = set()
    while "$ref" in node:
        ref = node["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in visited:
            raise ValueError("Unresolvable local reference")
        if set(node) - ({"$ref"} | SCHEMA_ANNOTATIONS):
            raise ValueError("Unsupported validation siblings on reference")
        visited.add(ref)
        node = document
        for token in ref[2:].split("/"):
            if re.search(r"~(?![01])", token):
                raise ValueError("Invalid JSON pointer escape")
            token = token.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or token not in node:
                raise ValueError("Unresolvable local reference")
            node = node[token]
    if not isinstance(node, dict):
        raise ValueError("Invalid schema object")
    return node


def _schema_errors(expected, actual, reference, provider, path, direction, seen=None):
    """Check focused fields; input sets may grow and output guarantees may strengthen."""
    try:
        expected, actual = _resolve(expected, reference), _resolve(actual, provider)
    except ValueError, TypeError:
        return [path + ": invalid or unsupported reference/schema"]
    if (set(expected) | set(actual)) - SUPPORTED_SCHEMA_KEYWORDS:
        # Unknown keyword names and values can themselves contain private content.
        return [path + ": unsupported schema validation keyword"]
    pair = (id(expected), id(actual), direction)
    seen = set() if seen is None else seen
    if pair in seen:
        return []
    seen = seen | {pair}
    errors = []

    def fail(facet):
        errors.append(path + ": incompatible " + facet)

    for union in ("anyOf",):
        if union not in expected and union not in actual:
            continue
        # A union with validation siblings needs full intersection semantics.
        annotations = {union} | SCHEMA_ANNOTATIONS
        if (union in expected and set(expected) - annotations) or (
            union in actual and set(actual) - annotations
        ):
            return [path + ": unsupported union validation siblings"]
        before, after = expected.get(union, [expected]), actual.get(union, [actual])
        source, targets = (before, after) if direction == "request" else (after, before)
        for branch in source:
            candidates = (
                (branch, target) if direction == "request" else (target, branch)
                for target in targets
            )
            if not any(
                not _schema_errors(a, b, reference, provider, path, direction, seen)
                for a, b in candidates
            ):
                fail(union)
        return errors

    before, after = expected.get("type"), actual.get("type")
    if before != after:
        compatible_numeric = (before, after) == (
            ("integer", "number") if direction == "request" else ("number", "integer")
        )
        if not compatible_numeric:
            fail("type")
    narrow, broad = (expected, actual) if direction == "request" else (actual, expected)
    for facet in ("enum", "const"):
        if facet in broad:
            wanted = broad[facet] if facet == "enum" else [broad[facet]]
            got = narrow.get(facet, []) if facet == "enum" else [narrow.get(facet)]
            if facet not in narrow or any(
                not any(_json_equal(value, allowed) for allowed in wanted) for value in got
            ):
                fail(facet)
    for facet in ("minimum", "exclusiveMinimum", "minLength", "minItems", "minProperties"):
        if facet in broad and (facet not in narrow or narrow[facet] < broad[facet]):
            fail(facet)
    for facet in ("maximum", "exclusiveMaximum", "maxLength", "maxItems", "maxProperties"):
        if facet in broad and (facet not in narrow or narrow[facet] > broad[facet]):
            fail(facet)
    for facet in ("format", "pattern", "multipleOf", "uniqueItems"):
        if facet in broad and narrow.get(facet) != broad[facet]:
            fail(facet)
    old_required, new_required = set(expected.get("required", [])), set(actual.get("required", []))
    if new_required - old_required if direction == "request" else old_required - new_required:
        fail("required")
    for name, value in expected.get("properties", {}).items():
        child_path = path + ".properties." + name
        if name not in actual.get("properties", {}):
            errors.append(child_path + ": missing selected field")
        else:
            errors.extend(
                _schema_errors(
                    value,
                    actual["properties"][name],
                    reference,
                    provider,
                    child_path,
                    direction,
                    seen,
                )
            )
    if "items" in expected:
        errors.extend(
            _schema_errors(
                expected["items"],
                actual.get("items", {}),
                reference,
                provider,
                path + ".items",
                direction,
                seen,
            )
        )
    before, after = (
        expected.get("additionalProperties", True),
        actual.get("additionalProperties", True),
    )
    if isinstance(before, bool) and isinstance(after, bool):
        if (before and not after) if direction == "request" else (after and not before):
            fail("additionalProperties")
    elif before != after:
        fail("additionalProperties")
    return errors


def contract_errors(schema: dict, contract: dict) -> list[str]:
    if contract.get("contractVersion") != 1:
        return ["contractVersion: unsupported contract format"]
    reference = contract["openapi"]
    version = reference["info"]["version"]
    if schema["info"]["version"] != version:
        return ["providerVersion: expected " + version]
    errors = []

    def compare(expected, actual, path, direction):
        errors.extend(_schema_errors(expected, actual, reference, schema, path, direction))

    def content(expected, actual, path, direction):
        for media, value in expected.get("content", {}).items():
            if media not in actual.get("content", {}):
                errors.append(path + ": missing content type " + media)
                continue
            for key in ("schema", "itemSchema"):
                if key in value:
                    compare(value[key], actual["content"][media].get(key, {}), path, direction)

    for route, item in reference["paths"].items():
        for method, expected in item.items():
            if method not in METHODS:
                continue
            path = method.upper() + " " + route
            actual = schema["paths"].get(route, {}).get(method)
            if actual is None:
                errors.append(path + ": missing selected operation")
                continue
            if "requestBody" in expected:
                old_body, new_body = expected["requestBody"], actual.get("requestBody", {})
                if new_body.get("required", False) and not old_body.get("required", False):
                    errors.append(path + ".requestBody: incompatible required")
                content(old_body, new_body, path + ".requestBody", "request")
            elif actual.get("requestBody", {}).get("required", False):
                errors.append(path + ".requestBody: new required body")
            old_params = {(p["in"], p["name"]): p for p in expected.get("parameters", [])}
            new_params = {(p["in"], p["name"]): p for p in actual.get("parameters", [])}
            for key, value in old_params.items():
                if key not in new_params:
                    errors.append(path + ".parameters." + key[1] + ": missing selected parameter")
                else:
                    if new_params[key].get("required", False) and not value.get("required", False):
                        errors.append(path + ".parameters." + key[1] + ": incompatible required")
                    compare(
                        value.get("schema", {}),
                        new_params[key].get("schema", {}),
                        path + ".parameters." + key[1],
                        "request",
                    )
            if any(
                p.get("required", False) for key, p in new_params.items() if key not in old_params
            ):
                errors.append(path + ".parameters: new required parameter")
            for status, response in expected.get("responses", {}).items():
                if status not in actual.get("responses", {}):
                    errors.append(path + ".responses." + status + ": missing selected response")
                else:
                    content(
                        response,
                        actual["responses"][status],
                        path + ".responses." + status,
                        "response",
                    )
    return sorted(set(errors))


def audit(schema: dict, catalog: dict, *, contract: dict | None = None) -> dict:
    mapped: dict[str, list[str]] = {}
    names = {tool["name"] for tool in catalog["tools"]}
    for tools in ALTERNATIVES.values():
        if not set(tools) <= names:
            raise ValueError("An alternative names an unavailable tool")
    for tool in catalog["tools"]:
        for endpoint in tool["endpoints"]:
            mapped.setdefault(normalized(endpoint), []).append(tool["name"])
    operations = []
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if method not in METHODS:
                continue
            endpoint = method.upper() + " " + path
            direct = mapped.get(normalized(endpoint), [])
            recipe_scope = path.startswith(RECIPE_PREFIXES)
            alternative = ALTERNATIVES.get(endpoint, [])
            status = (
                "catalog_dependency"
                if direct
                else "explicit_alternative_contract"
                if alternative
                else "unmapped_recipe_operation"
                if recipe_scope
                else "outside_recipe_extension"
            )
            operations.append(
                {
                    "endpoint": endpoint,
                    "summary": operation.get("summary"),
                    "recipeScope": recipe_scope,
                    "status": status,
                    "tools": direct or alternative,
                }
            )
    api_keys = {normalized(operation["endpoint"]) for operation in operations}
    related = [operation for operation in operations if operation["recipeScope"]]
    return {
        "providerVersion": schema["info"]["version"],
        "mcpTools": len(names),
        "apiOperations": len(operations),
        "catalogDependencyOperations": sum(
            operation["status"] == "catalog_dependency" for operation in operations
        ),
        "recipeOperations": len(related),
        "recipeCatalogDependencies": sum(
            operation["status"] == "catalog_dependency" for operation in related
        ),
        "recipeAlternativeContracts": sum(
            operation["status"] == "explicit_alternative_contract" for operation in related
        ),
        "unmappedRecipeOperations": [
            operation["endpoint"]
            for operation in related
            if operation["status"] == "unmapped_recipe_operation"
        ],
        "unmatchedCatalogDependencies": sorted(set(mapped) - api_keys),
        "contractErrors": contract_errors(schema, contract) if contract is not None else [],
        "contractChecked": contract is not None,
        "limitations": [
            "Catalog dependencies include internal reads; "
            "they do not prove full parameter support.",
            "Alternative batch tools have distinct snapshot, ordering, error and partial-result "
            "contracts; arbitrary full-model writes are not exposed.",
            "Public exploration of other groups, account/provider configuration and "
            "administration are outside this household recipe extension.",
            "AI provider success requires separate evidence; see the real-provider E2E report.",
        ],
        "operations": operations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
        help=(
            "Reviewed focused contract (default: Mealie 3.30); "
            "other versions need an explicit contract"
        ),
    )
    args = parser.parse_args()
    raw = args.schema.read_bytes()
    try:
        schema = json.loads(raw)
        contract = json.loads(args.contract.read_bytes())
        report = audit(schema, json.loads(CATALOG.read_bytes()), contract=contract)
        if schema["info"]["version"] != args.expected_version:
            report["contractErrors"].append("providerVersion: differs from --expected-version")
    except ValueError, KeyError, TypeError, OSError, RecursionError:
        report = {
            "contractErrors": ["Invalid provider schema or focused contract"],
            "operations": [],
        }
    report["openapiSha256"] = hashlib.sha256(raw).hexdigest()
    report["catalogSha256"] = hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    if args.contract.is_file():
        report["contractSha256"] = hashlib.sha256(args.contract.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "operations"}))
    return int(
        bool(
            report.get("unmappedRecipeOperations")
            or report.get("unmatchedCatalogDependencies")
            or report["contractErrors"]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
