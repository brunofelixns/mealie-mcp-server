"""Provider-contract regression tests; historical migration captures stay untouched."""

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/audit_mealie_api.py"
SPEC = importlib.util.spec_from_file_location("audit_mealie_api", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def catalog():
    names = {name for names in module.ALTERNATIVES.values() for name in names}
    return {
        "tools": [
            {"name": name, "endpoints": ["PUT /api/recipes/{slug}"]} for name in sorted(names)
        ]
    }


def provider():
    return {
        "openapi": "3.1.0",
        "info": {"version": "v3.30.0"},
        "paths": {
            "/api/recipes/{slug}": {
                "put": {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RecipeStep"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/RecipeStep"}
                                }
                            }
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "RecipeStep": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {
                        "text": {"type": "string"},
                        "durationSeconds": {
                            "anyOf": [
                                {"type": "integer", "minimum": 1, "maximum": 2147483647},
                                {"type": "null"},
                            ]
                        },
                        "kind": {"type": "string", "enum": ["system", "info"]},
                    },
                }
            }
        },
    }


def contract(schema):
    return {"contractVersion": 1, "openapi": copy.deepcopy(schema)}


def compare(schema, baseline):
    return module.audit(schema, catalog(), contract=baseline)


def test_route_audit_reports_new_recipe_operation_and_missing_dependency():
    schema = provider()
    schema["paths"] = {"/api/recipes/new-operation": {"post": {}}}
    report = module.audit(schema, catalog())
    assert report["unmappedRecipeOperations"] == ["POST /api/recipes/new-operation"]
    assert report["unmatchedCatalogDependencies"] == ["PUT /api/recipes/{}"]


@pytest.mark.parametrize("change", ["type", "required", "enum", "minimum", "maximum", "missing"])
def test_rejects_breaking_request_field_drift(change):
    schema = provider()
    baseline = contract(schema)
    # Only exercise the request direction: outputs have the inverse variance.
    baseline["openapi"]["paths"]["/api/recipes/{slug}"]["put"].pop("responses")
    step = schema["components"]["schemas"]["RecipeStep"]
    if change == "type":
        step["properties"]["durationSeconds"]["anyOf"][0]["type"] = "string"
    elif change == "required":
        step["required"].append("durationSeconds")
    elif change == "enum":
        step["properties"]["kind"]["enum"] = ["info"]
    elif change == "minimum":
        step["properties"]["durationSeconds"]["anyOf"][0]["minimum"] = 2
    elif change == "maximum":
        step["properties"]["durationSeconds"]["anyOf"][0]["maximum"] = 60
    else:
        del step["properties"]["durationSeconds"]
    report = compare(schema, baseline)
    assert report["contractErrors"], change
    assert "requestBody" in " ".join(report["contractErrors"])


def test_rejects_new_required_request_field_outside_the_selected_properties():
    schema = provider()
    baseline = contract(schema)
    schema["components"]["schemas"]["RecipeStep"]["required"].append("providerSetting")
    schema["components"]["schemas"]["RecipeStep"]["properties"]["providerSetting"] = {
        "type": "string"
    }
    assert compare(schema, baseline)["contractErrors"]


@pytest.mark.parametrize("change", ["required", "enum", "bound", "binding", "missing_response"])
def test_rejects_breaking_response_guarantees_and_changed_operation_binding(change):
    schema = provider()
    baseline = contract(schema)
    baseline["openapi"]["paths"]["/api/recipes/{slug}"]["put"].pop("requestBody")
    schema["paths"]["/api/recipes/{slug}"]["put"].pop("requestBody")
    step = schema["components"]["schemas"]["RecipeStep"]
    if change == "required":
        step["required"] = []
    elif change == "enum":
        step["properties"]["kind"]["enum"].append("unknown")
    elif change == "bound":
        step["properties"]["durationSeconds"]["anyOf"][0]["minimum"] = 0
    elif change == "binding":
        schema["paths"]["/api/recipes/{slug}"]["put"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"] = {"type": "string"}
    else:
        schema["paths"]["/api/recipes/{slug}"]["put"]["responses"] = {}
    assert compare(schema, baseline)["contractErrors"]


def test_rejects_wrong_provider_version_even_if_routes_and_fields_match():
    schema = provider()
    baseline = contract(schema)
    schema["info"]["version"] = "v3.31.0"
    assert compare(schema, baseline)["contractErrors"] == ["providerVersion: expected v3.30.0"]


def test_accepts_documentation_reordering_and_additive_optional_fields():
    schema = provider()
    baseline = contract(schema)
    step = schema["components"]["schemas"]["RecipeStep"]
    step["title"] = "Different generated title"
    step["description"] = "New prose"
    step["properties"]["providerExtension"] = {"type": "boolean"}
    step["properties"]["durationSeconds"]["anyOf"].reverse()
    step["properties"]["kind"]["enum"].reverse()
    schema["paths"]["/api/admin/extra"] = {"get": {}}
    assert compare(schema, baseline)["contractErrors"] == []


def test_accepts_compatible_request_enum_and_bound_widening():
    schema = provider()
    baseline = contract(schema)
    baseline["openapi"]["paths"]["/api/recipes/{slug}"]["put"].pop("responses")
    step = schema["components"]["schemas"]["RecipeStep"]
    step["properties"]["kind"]["enum"].append("comment")
    step["properties"]["durationSeconds"]["anyOf"][0]["minimum"] = 0
    assert compare(schema, baseline)["contractErrors"] == []


@pytest.mark.parametrize("direction", ["request", "response"])
def test_nullability_uses_request_acceptance_and_response_guarantees(direction):
    schema = provider()
    baseline = contract(schema)
    operation = baseline["openapi"]["paths"]["/api/recipes/{slug}"]["put"]
    operation.pop("responses" if direction == "request" else "requestBody")
    schema["paths"]["/api/recipes/{slug}"]["put"].pop(
        "responses" if direction == "request" else "requestBody"
    )
    duration = schema["components"]["schemas"]["RecipeStep"]["properties"]["durationSeconds"]
    duration["anyOf"] = duration["anyOf"][:1]
    assert bool(compare(schema, baseline)["contractErrors"]) is (direction == "request")


def test_new_required_request_body_is_breaking_when_baseline_had_none():
    schema = provider()
    baseline = contract(schema)
    baseline["openapi"]["paths"]["/api/recipes/{slug}"]["put"].pop("requestBody")
    assert compare(schema, baseline)["contractErrors"]


def test_required_query_parameter_added_to_existing_operation_is_breaking():
    schema = provider()
    baseline = contract(schema)
    schema["paths"]["/api/recipes/{slug}"]["put"]["parameters"] = [
        {"name": "extra", "in": "query", "required": True, "schema": {"type": "string"}}
    ]
    assert compare(schema, baseline)["contractErrors"]


@pytest.mark.parametrize("facet", ["enum", "const"])
def test_json_boolean_does_not_replace_a_numeric_enum_or_const(facet):
    schema = provider()
    baseline = contract(schema)
    old_value, new_value = ([0], [False]) if facet == "enum" else (0, False)
    baseline["openapi"]["components"]["schemas"]["RecipeStep"]["properties"]["kind"] = {
        "type": "integer",
        facet: old_value,
    }
    schema["components"]["schemas"]["RecipeStep"]["properties"]["kind"] = {
        "type": "integer",
        facet: new_value,
    }
    assert compare(schema, baseline)["contractErrors"]


@pytest.mark.parametrize("composition", ["allOf", "oneOf"])
def test_unsupported_schema_composition_fails_closed(composition):
    schema = provider()
    schema["components"]["schemas"]["RecipeStep"]["properties"]["kind"] = {
        composition: [{"type": "string"}]
    }
    assert compare(schema, contract(schema))["contractErrors"]


def test_reviewed_cookbook_request_rejects_unhandled_dependent_required():
    fixture = json.loads(module.DEFAULT_CONTRACT.read_bytes())
    schema = copy.deepcopy(fixture["openapi"])
    cookbook = schema["components"]["schemas"]["CreateCookBook"]
    minimum_request = {"name": "Recipes"}
    assert Draft202012Validator(cookbook).is_valid(minimum_request)
    cookbook["dependentRequired"] = {"name": ["description"]}
    assert not Draft202012Validator(cookbook).is_valid(minimum_request)
    errors = module.contract_errors(schema, fixture)
    assert errors
    assert any("requestBody" in error for error in errors)


@pytest.mark.parametrize("direction", ["request", "response"])
@pytest.mark.parametrize(
    "keyword,value",
    [
        ("dependentRequired", {"text": ["PRIVATE-SCHEMA-FRAGMENT"]}),
        ("contains", {"const": "PRIVATE-SCHEMA-FRAGMENT"}),
        ("propertyNames", {"pattern": "PRIVATE-SCHEMA-FRAGMENT"}),
        ("patternProperties", {"PRIVATE-SCHEMA-FRAGMENT": {"type": "string"}}),
        ("unevaluatedProperties", False),
        ("futureAssertion", "PRIVATE-SCHEMA-FRAGMENT"),
    ],
)
def test_unknown_validation_keywords_fail_closed_without_printing_fragments(
    direction, keyword, value
):
    schema = provider()
    operation = schema["paths"]["/api/recipes/{slug}"]["put"]
    operation.pop("responses" if direction == "request" else "requestBody")
    baseline = contract(schema)
    schema["components"]["schemas"]["RecipeStep"][keyword] = value
    errors = compare(schema, baseline)["contractErrors"]
    assert errors
    location = "requestBody" if direction == "request" else "responses"
    assert all(location in error for error in errors)
    assert "PRIVATE-SCHEMA-FRAGMENT" not in " ".join(errors)


def test_known_annotations_are_compatible_on_schemas_unions_and_references():
    schema = provider()
    baseline = contract(schema)
    annotations = {
        "title": "Generated title",
        "description": "Documentation only",
        "default": None,
        "examples": ["sample"],
        "example": "sample",
        "$comment": "Reviewed annotation",
        "deprecated": True,
        "readOnly": False,
        "writeOnly": False,
        "contentMediaType": "application/json",
        "contentEncoding": "utf-8",
    }
    step = schema["components"]["schemas"]["RecipeStep"]
    step.update(annotations)
    step["properties"]["durationSeconds"].update(annotations)
    schema["paths"]["/api/recipes/{slug}"]["put"]["requestBody"]["content"]["application/json"][
        "schema"
    ].update(annotations)
    assert compare(schema, baseline)["contractErrors"] == []


def test_reviewed_fixture_records_source_provenance_and_preserves_property_named_title():
    fixture = json.loads(module.DEFAULT_CONTRACT.read_bytes())
    assert fixture["provenance"]["sourceBytes"] == 856123
    assert fixture["provenance"]["sourceSha256"] == (
        "60a06ffa9a39e9769e37ea333859d698df3fcb472043b67e6e0f367406bb6087"
    )
    assert fixture["openapi"]["info"]["version"] == "v3.30.0"
    assert fixture["provenance"]["providerImage"].endswith(
        "@sha256:90f83da6f3ab0a421efc827118a556168573930105f13fa3321768f42163d784"
    )
    schemas = fixture["openapi"]["components"]["schemas"]
    assert "title" in schemas["RecipeStep"]["properties"]
    assert schemas["RecipeStep"]["properties"]["durationSeconds"]["anyOf"] == [
        {"type": "integer", "maximum": 2147483647.0, "minimum": 1.0},
        {"type": "null"},
    ]


@pytest.mark.parametrize(
    "name,field",
    [
        ("RecipeStep", "durationSeconds"),
        ("RecipeIngredient-Input", "substitutions"),
        ("RecipeIngredient-Output", "substitutions"),
        ("CreateIngredientFood", "substitutions"),
        ("CreateIngredientFoodSubstitution", "substituteFoodId"),
        ("IngredientFoodSubstitution", "note"),
        ("CreatePlanEntry", "endDate"),
        ("ReadPlanEntry", "recipeScale"),
        ("CreateRandomEntry", "endDate"),
        ("CreateCookBook", "name"),
        ("RecipeTimelineEventIn", "eventType"),
        ("RecipeTimelineEventOut", "id"),
        ("ScrapeRecipeData", "data"),
        ("RecipeSuggestionResponseItem", "substitutedFoods"),
        ("RecipeAsset", "fileName"),
    ],
)
def test_reviewed_native_fixture_detects_focused_field_type_drift(name, field):
    fixture = json.loads(module.DEFAULT_CONTRACT.read_bytes())
    schema = copy.deepcopy(fixture["openapi"])
    assert module.contract_errors(schema, fixture) == []
    schema["components"]["schemas"][name]["properties"][field] = {"type": "boolean"}
    assert module.contract_errors(schema, fixture), (name, field)


@pytest.mark.parametrize(
    "reference",
    [
        "https://invalid.example/schema.json",
        "#/components/schemas/absent",
        "#/components/schemas/Loop",
    ],
)
def test_bad_references_fail_closed_without_fetching_or_leaking_the_reference(reference):
    schema = provider()
    baseline = contract(schema)
    schema["components"]["schemas"]["Loop"] = {"$ref": "#/components/schemas/Loop"}
    schema["paths"]["/api/recipes/{slug}"]["put"]["requestBody"]["content"]["application/json"][
        "schema"
    ] = {"$ref": reference}
    errors = compare(schema, baseline)["contractErrors"]
    assert errors
    assert "invalid.example" not in " ".join(errors)


def test_resolves_escaped_local_pointer_names_and_valid_recursive_objects():
    schema = provider()
    step = schema["components"]["schemas"].pop("RecipeStep")
    schema["components"]["schemas"]["Step~/Node"] = step
    ref = {"$ref": "#/components/schemas/Step~0~1Node"}
    step["properties"]["next"] = copy.deepcopy(ref)
    operation = schema["paths"]["/api/recipes/{slug}"]["put"]
    operation["requestBody"]["content"]["application/json"]["schema"] = copy.deepcopy(ref)
    operation["responses"]["200"]["content"]["application/json"]["schema"] = copy.deepcopy(ref)
    assert compare(schema, contract(schema))["contractErrors"] == []


def test_cli_writes_a_failure_report_for_version_drift_without_printing_schema_bodies(tmp_path):
    schema = provider()
    baseline = contract(schema)
    schema["info"]["version"] = "v99"
    schema["description"] = "SECRET-RECIPE-CONTENT"
    schema_path, contract_path, output = (
        tmp_path / name for name in ("api.json", "contract.json", "audit.json")
    )
    schema_path.write_text(json.dumps(schema))
    contract_path.write_text(json.dumps(baseline))
    result = subprocess.run(
        [
            sys.executable,
            str(module.ROOT / "scripts/audit_mealie_api.py"),
            "--schema",
            str(schema_path),
            "--expected-version",
            "v3.30.0",
            "--contract",
            str(contract_path),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert output.exists(), result.stderr
    report = json.loads(output.read_text())
    assert result.returncode == 1
    assert report["contractErrors"]
    assert report["openapiSha256"] == hashlib.sha256(schema_path.read_bytes()).hexdigest()
    assert "SECRET-RECIPE-CONTENT" not in result.stdout + result.stderr + output.read_text()
