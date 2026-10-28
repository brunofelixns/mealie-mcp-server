"""Representative CRUD across all domains on the explicitly disposable Mealie stack."""

import asyncio
import base64
import binascii
import json
import os
import struct
import uuid
import zlib
from datetime import UTC, datetime
from pathlib import Path

import httpx2 as httpx
import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server

pytestmark = pytest.mark.live


def png():
    def chunk(kind, data):
        return (
            struct.pack("!I", len(data))
            + kind
            + data
            + struct.pack("!I", binascii.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0"))
        + chunk(b"IEND", b"")
    )


async def test_real_mealie_crud_recipe_integrity_and_binary_upload():
    url = os.environ.get("MEALIE_LIVE_URL")
    if not url or os.environ.get("MEALIE_LIVE_ALLOW_WRITES") != "disposable-only":
        pytest.skip("Run only through the documented disposable integration stack")
    async with httpx.AsyncClient(base_url=url, timeout=30) as http:
        about = (await http.get("/api/app/about")).json()
        assert about["version"] == "v3.29.0"
        login = await http.post(
            "/api/auth/token", data={"username": "changeme@example.com", "password": "MyPassword"}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
    settings = load_settings({"MEALIE_BASE_URL": url, "MEALIE_API_KEY": token})
    prefix = "MCP migration " + uuid.uuid4().hex[:10]
    steps = []
    async with Client(create_server(settings)) as client:
        assert len(await client.list_tools()) == 78

        async def call(name, arguments):
            result = await client.call_tool(name, arguments, raise_on_error=False)
            assert not result.is_error, (name, result.content)
            steps.append(name)
            return json.loads(result.content[0].text)

        category = await call("create_category", {"name": prefix + " category"})
        tag = await call("create_tag", {"name": prefix + " tag"})
        food = await call("create_food", {"name": prefix + " salt"})
        unit = await call("create_unit", {"name": prefix + " spoon", "abbreviation": "sp"})
        tool = await call("create_tool", {"name": prefix + " pan"})
        food = await call("update_food", {"foodId": food["id"], "description": "integration-only"})
        assert food["description"] == "integration-only"
        slug = await call("create_recipe", {"name": prefix + " soup"})
        assert isinstance(slug, str)
        recipe = await call(
            "patch_recipe",
            {
                "slug": slug,
                "description": "integration-only",
                "categories": [category["id"]],
                "tags": [tag["id"]],
            },
        )
        assert recipe["description"] == "integration-only"
        await call("update_recipe_tools", {"slug": slug, "tools": [tool["id"]]})
        reference = str(uuid.uuid4())
        await call(
            "update_recipe_ingredients",
            {
                "slug": slug,
                "ingredients": [
                    {
                        "referenceId": reference,
                        "foodId": food["id"],
                        "foodName": food["name"],
                        "unitId": unit["id"],
                        "unitName": unit["name"],
                        "quantity": 2,
                        "note": "Keep this original note",
                    }
                ],
            },
        )
        recipe = await call("get_recipe_detailed", {"slug": slug})
        assert recipe["recipeIngredient"][0]["food"]["id"] == food["id"]
        assert recipe["recipeIngredient"][0]["quantity"] == 2
        stamp = recipe["updatedAt"]
        await call(
            "update_recipe_instructions",
            {
                "slug": slug,
                "expectedUpdatedAt": stamp,
                "instructions": [{"text": "Boil the soup.", "ingredientReferenceIds": [reference]}],
            },
        )
        stale = await client.call_tool(
            "update_recipe_instructions",
            {
                "slug": slug,
                "expectedUpdatedAt": stamp,
                "instructions": [{"text": "Must never be written"}],
            },
            raise_on_error=False,
        )
        assert stale.is_error
        recipe = await call("get_recipe_detailed", {"slug": slug})
        assert recipe["recipeInstructions"][0]["text"] == "Boil the soup."
        assert (
            recipe["recipeInstructions"][0]["ingredientReferences"][0]["referenceId"] == reference
        )
        rating = await call("set_recipe_rating", {"slug": slug, "rating": 4.5, "isFavorite": True})
        assert rating["userRating"]["rating"] == 4.5
        assert rating["userRating"]["isFavorite"] is True
        await call("mark_recipe_last_made", {"slug": slug})
        await call(
            "set_recipe_image", {"slug": slug, "imageBase64": base64.b64encode(png()).decode()}
        )
        recipe = await call("get_recipe_detailed", {"slug": slug})
        assert recipe["image"]
        # Mealie 3.29 stores this per household; RecipeRead has no lastMade field.
        async with httpx.AsyncClient(
            base_url=url, headers={"Authorization": "Bearer " + token}
        ) as observer:
            made = (await observer.get("/api/households/self/recipes/" + slug)).json()
        assert made["lastMade"]
        today = datetime.now(UTC).date().isoformat()
        plan = await call(
            "create_mealplan", {"date": today, "recipeId": recipe["id"], "entryType": "dinner"}
        )
        plans = await call("get_all_mealplans", {"startDate": today, "endDate": today})
        assert any(item["id"] == plan["id"] for item in plans["items"])
        shopping = await call("create_shopping_list", {"name": prefix + " shopping"})
        await call(
            "create_shopping_list_item",
            {
                "shoppingListId": shopping["id"],
                "note": prefix,
                "foodId": food["id"],
                "unitId": unit["id"],
                "quantity": 2,
            },
        )
        full_list = await call("get_shopping_list", {"listId": shopping["id"]})
        assert any(row["note"] == prefix and row["quantity"] == 2 for row in full_list["listItems"])
        await call("delete_shopping_list", {"listId": shopping["id"]})
        await call("patch_mealplan", {"actions": [{"action": "delete", "id": str(plan["id"])}]})
        plans = await call("get_all_mealplans", {"startDate": today, "endDate": today})
        assert not any(row["id"] == plan["id"] for row in plans["items"])
        await call("delete_recipe", {"slug": slug})
        for name, arguments in (
            ("delete_food", {"foodId": food["id"]}),
            ("delete_unit", {"unitId": unit["id"]}),
            ("delete_tool", {"toolId": tool["id"]}),
            ("delete_category", {"categoryId": category["id"]}),
            ("delete_tag", {"tagId": tag["id"]}),
        ):
            await call(name, arguments)
    summary = {
        "mealieVersion": about["version"],
        "calls": len(steps),
        "tools": sorted(set(steps)),
        "staleWriteRejected": True,
        "transport": "native MCP; real Mealie HTTP",
        "credentialsRecorded": False,
    }
    await asyncio.to_thread(save_summary, summary)


def save_summary(summary):
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/P24-live-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
