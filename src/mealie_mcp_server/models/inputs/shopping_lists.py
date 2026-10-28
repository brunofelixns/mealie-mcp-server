"""Strict public inputs; only the original entity maps remain open."""

from pydantic import Field

from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.models.inputs.base import JsonInteger, ToolInput


class GetShoppingListsInput(ToolInput):
    page: float | None = None
    per_page: float | None = Field(default=None, alias="perPage")


class CreateShoppingListInput(ToolInput):
    name: str


class GetShoppingListInput(ToolInput):
    list_id: str = Field(alias="listId")


class UpdateShoppingListInput(ToolInput):
    list_id: str = Field(alias="listId")
    name: str | None = None


class DeleteShoppingListInput(ToolInput):
    list_id: str = Field(alias="listId")


class AddRecipeToShoppingListInput(ToolInput):
    list_id: str = Field(alias="listId")
    recipe_id: str = Field(alias="recipeId")
    recipe_increment_quantity: float | None = Field(default=None, alias="recipeIncrementQuantity")


class RemoveRecipeFromShoppingListInput(ToolInput):
    list_id: str = Field(alias="listId")
    recipe_id: str = Field(alias="recipeId")


class GetShoppingListItemsInput(GetShoppingListsInput):
    search: str | None = None


class CreateShoppingListItemInput(ToolInput):
    shopping_list_id: str = Field(alias="shoppingListId")
    note: str
    quantity: float | None = None
    unit_id: str | None = Field(default=None, alias="unitId")
    food_id: str | None = Field(default=None, alias="foodId")
    label_id: str | None = Field(default=None, alias="labelId")


class ShoppingListRecipeReference(ToolInput):
    recipe_id: str = Field(alias="recipeId")
    recipe_quantity: float | None = Field(default=None, alias="recipeQuantity")
    recipe_scale: float | None = Field(default=None, alias="recipeScale")
    recipe_note: str | None = Field(default=None, alias="recipeNote")


class ShoppingListItemCreate(ToolInput):
    shopping_list_id: str = Field(alias="shoppingListId")
    id: str | None = None
    note: str | None = None
    display: str | None = None
    quantity: float | None = None
    checked: bool | None = None
    position: JsonInteger | None = None
    unit_id: str | None = Field(default=None, alias="unitId")
    food_id: str | None = Field(default=None, alias="foodId")
    label_id: str | None = Field(default=None, alias="labelId")
    unit: JsonObject | None = None
    food: JsonObject | None = None
    referenced_recipe: JsonObject | None = Field(default=None, alias="referencedRecipe")
    extras: JsonObject | None = None
    recipe_references: list[ShoppingListRecipeReference] | None = Field(
        default=None, alias="recipeReferences"
    )


class CreateShoppingListItemsBulkInput(ToolInput):
    items: list[ShoppingListItemCreate]


class UpdateShoppingListItemInput(ToolInput):
    item_id: str = Field(alias="itemId")
    note: str | None = None
    quantity: float | None = None
    checked: bool | None = None


class DeleteShoppingListItemInput(ToolInput):
    item_id: str = Field(alias="itemId")


class DeleteShoppingListItemsBulkInput(ToolInput):
    item_ids: list[str] = Field(alias="itemIds")
