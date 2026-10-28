"""Curated definitions and explicit registration of implemented families only."""

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from fastmcp import FastMCP

from mealie_mcp_server.tools.contracts import ToolDefinition


@lru_cache(maxsize=1)
def definitions() -> dict[str, ToolDefinition]:
    asset = files("mealie_mcp_server").joinpath("resources/tool-catalog.json")
    raw: dict[str, Any] = json.loads(asset.read_text(encoding="utf-8"))
    return {
        tool["name"]: ToolDefinition(
            name=tool["name"],
            description=tool["description"],
            input_schema=tool["inputSchema"],
            output_schema=tool.get("outputSchema"),
            annotations=tool.get("annotations"),
            meta=tool.get("_meta"),
            endpoints=tuple(tool["endpoints"]),
        )
        for tool in raw["tools"]
    }


def register_all_tools(server: FastMCP) -> None:
    # Families are added explicitly as their implementation tasks are verified.
    # Definitions are metadata, never placeholders advertised as working tools.
    from mealie_mcp_server.tools.categories import register_categories
    from mealie_mcp_server.tools.equipment import register_equipment
    from mealie_mcp_server.tools.foods import register_foods
    from mealie_mcp_server.tools.mealplans import register_mealplans
    from mealie_mcp_server.tools.recipe_queues import register_recipe_queues
    from mealie_mcp_server.tools.recipes import (
        register_recipe_core,
        register_recipe_ingredients,
        register_recipe_organizers,
    )
    from mealie_mcp_server.tools.shopping_lists import register_shopping_lists
    from mealie_mcp_server.tools.tags import register_tags
    from mealie_mcp_server.tools.units import register_units

    register_categories(server)
    register_tags(server)
    register_foods(server)
    register_units(server)
    register_equipment(server)
    register_shopping_lists(server)
    register_recipe_core(server)
    register_recipe_organizers(server)
    register_mealplans(server)
    register_recipe_queues(server)
    register_recipe_ingredients(server)
