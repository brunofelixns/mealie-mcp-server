from typing import Self

from pydantic import Field, model_validator

from mealie_mcp_server.models.inputs.base import ToolInput


class RecipeIngredientInput(ToolInput):
    quantity: float | None = None
    unit_id: str | None = Field(default=None, alias="unitId")
    unit_name: str | None = Field(default=None, alias="unitName")
    food_id: str | None = Field(default=None, alias="foodId")
    food_name: str | None = Field(default=None, alias="foodName")
    note: str | None = None
    display: str | None = None
    original_text: str | None = Field(default=None, alias="originalText")
    title: str | None = None
    reference_id: str | None = Field(default=None, alias="referenceId")
    referenced_recipe_id: str | None = Field(default=None, alias="referencedRecipeId")

    @model_validator(mode="after")
    def subrecipe_excludes_food_and_unit(self) -> Self:
        if self.referenced_recipe_id and (self.food_id or self.unit_id):
            raise ValueError("referencedRecipeId cannot be combined with foodId/unitId.")
        return self


class IngredientAddition(RecipeIngredientInput):
    insert_after_reference_id: str | None = Field(default=None, alias="insertAfterReferenceId")
    insert_before_reference_id: str | None = Field(default=None, alias="insertBeforeReferenceId")


class IngredientUpdate(RecipeIngredientInput):
    reference_id: str = Field(alias="referenceId")


class UpdateRecipeIngredientsInput(ToolInput):
    slug: str
    ingredients: list[RecipeIngredientInput] | None = None
    add_ingredients: list[IngredientAddition] | None = Field(default=None, alias="addIngredients")
    update_ingredients: list[IngredientUpdate] | None = Field(
        default=None, alias="updateIngredients"
    )
    remove_ingredient_reference_ids: list[str] | None = Field(
        default=None, alias="removeIngredientReferenceIds"
    )


class UpdateRecipeIngredientsBatchInput(ToolInput):
    updates: list[UpdateRecipeIngredientsInput] = Field(min_length=1, max_length=25)
