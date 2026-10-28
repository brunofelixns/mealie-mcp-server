from mealie_mcp_server.mealie.api import recipes, users
from mealie_mcp_server.mealie.client import MealieClient, scalar_string
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.organizer_resolution import to_organizer_item
from mealie_mcp_server.support.recipe_scan import is_number


async def set_recipe_rating(client: MealieClient, slug: str, changes: JsonObject) -> JsonObject:
    if "rating" not in changes and "isFavorite" not in changes:
        raise ValueError("Provide at least one of rating or isFavorite.")
    rating = changes.get("rating")
    if is_number(rating) and (not 0.5 <= rating <= 5 or rating / 0.5 != int(rating / 0.5)):
        raise ValueError("rating must be between 0.5 and 5 in steps of 0.5, or null to clear.")
    update: JsonObject = {}
    if "rating" in changes:
        update["rating"] = 0 if rating is None else rating
    if "isFavorite" in changes:
        update["isFavorite"] = changes["isFavorite"]
    user_id = await users.get_self_user_id(client)
    await users.update_user_rating(client, user_id, slug, update)
    recipe = await recipes.get_recipe(client, slug)
    identifier = recipe.get("id")
    recipe_id = (
        scalar_string(identifier) if is_number(identifier) else to_organizer_item(recipe)["id"]
    )
    summary = await users.get_self_rating(client, recipe_id)
    stored = summary.get("rating")
    return {
        "userRating": {**summary, "rating": stored if is_number(stored) and stored > 0 else None},
        "recipeRating": recipe.get("rating"),
    }
