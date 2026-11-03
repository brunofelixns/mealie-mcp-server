"""Published bounds and MCP argument rejection agree for Mealie 3.30 additions."""

from copy import deepcopy

import httpx2 as httpx
import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.server import create_server
from mealie_mcp_server.tools.registry import definitions

PAGINATED = [
    "get_cookbooks",
    "list_recipe_comments",
    "get_recipe_actions",
    "list_mealplan_entries",
    "get_mealplan_rules",
]
NUMERIC_CASES = [
    *[pytest.param(name, {}, ("page",), 1, None, id=f"{name}-page") for name in PAGINATED],
    *[pytest.param(name, {}, ("perPage",), 1, 1000, id=f"{name}-perPage") for name in PAGINATED],
    pytest.param("get_mealplan_entry", {}, ("entryId",), 1, None, id="get-entry-id"),
    pytest.param("delete_mealplan_entry", {}, ("entryId",), 1, None, id="delete-entry-id"),
    pytest.param(
        "update_mealplan_entry",
        {"changes": {"text": ""}},
        ("entryId",),
        1,
        None,
        id="update-entry-id",
    ),
    pytest.param(
        "get_mealplan_ical_feed",
        {"token": "fixture"},
        ("duration",),
        1,
        1440,
        id="calendar-duration",
    ),
    *[
        pytest.param(
            "import_recipes_from_urls",
            {
                "imports": [
                    {"url": "https://recipes.test/soup", key: [{"name": "Soup", "slug": "soup"}]}
                ]
            },
            ("imports", 0, key, 0, "recipeCount"),
            0,
            None,
            id=f"bulk-{key}-count",
        )
        for key in ("categories", "tags")
    ],
    pytest.param(
        "update_recipe_metadata_batch",
        {"items": [{"slug": "soup", "expectedUpdatedAt": "2026-11-03T00:00:00Z", "name": "Soup"}]},
        ("concurrency",),
        1,
        5,
        id="metadata-concurrency",
    ),
]


def with_number(arguments, path, value):
    arguments = deepcopy(arguments)
    target = arguments
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return arguments


def assert_standard_bounds(schema):
    if isinstance(schema, dict):
        assert not {"ge", "le"}.intersection(schema), "Use minimum/maximum in JSON Schema"
        for child in schema.values():
            assert_standard_bounds(child)
    elif isinstance(schema, list):
        for child in schema:
            assert_standard_bounds(child)


@pytest.mark.parametrize("name,arguments,path,minimum,maximum", NUMERIC_CASES)
def test_published_numeric_bounds_are_enforced_by_standard_json_schema(
    name, arguments, path, minimum, maximum
):
    schema = definitions()[name].input_schema
    validator = Draft202012Validator(schema)
    for value in [minimum, maximum if maximum is not None else minimum + 17]:
        assert validator.is_valid(with_number(arguments, path, value))
        assert validator.is_valid(with_number(arguments, path, float(value)))
    invalid_values = [minimum - 1, True, False, None, 1.25, "1"]
    if maximum is not None:
        invalid_values.append(maximum + 1)
    for value in invalid_values:
        assert not validator.is_valid(with_number(arguments, path, value)), (name, path, value)
    assert_standard_bounds(schema)


@pytest.mark.parametrize("name,arguments,path,minimum,maximum", NUMERIC_CASES)
async def test_invalid_numeric_arguments_are_rejected_by_mcp_before_http(
    name, arguments, path, minimum, maximum
):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(500, json={"detail": "Unexpected provider request"})

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
    )
    invalid_values = [minimum - 1, True, False, None, 1.25, "1"]
    if maximum is not None:
        invalid_values.append(maximum + 1)
    async with Client(server) as client:
        for value in invalid_values:
            result = await client.call_tool(
                name, with_number(arguments, path, value), raise_on_error=False
            )
            assert result.is_error, (name, path, value)
            assert "Invalid arguments" in result.content[0].text
    assert calls == []


async def test_mcp_lists_the_corrected_numeric_schemas_without_provider_access():
    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    async with Client(create_server(settings)) as client:
        listed = {tool.name: tool.input_schema for tool in await client.list_tools()}
    names = {
        *PAGINATED,
        "get_mealplan_entry",
        "delete_mealplan_entry",
        "update_mealplan_entry",
        "get_mealplan_ical_feed",
        "import_recipes_from_urls",
        "update_recipe_metadata_batch",
    }
    assert len(names) == 11
    for name in names:
        assert_standard_bounds(listed[name])
