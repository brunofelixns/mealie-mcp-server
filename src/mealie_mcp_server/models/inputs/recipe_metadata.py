"""Strict additional recipe metadata inputs; omitted nested fields stay omitted."""

from pydantic import Field

from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.models.inputs.base import ToolInput


class RecipeNutritionPatch(ToolInput):
    calories: str | None = None
    carbohydrate_content: str | None = Field(default=None, alias="carbohydrateContent")
    cholesterol_content: str | None = Field(default=None, alias="cholesterolContent")
    fat_content: str | None = Field(default=None, alias="fatContent")
    fiber_content: str | None = Field(default=None, alias="fiberContent")
    protein_content: str | None = Field(default=None, alias="proteinContent")
    saturated_fat_content: str | None = Field(default=None, alias="saturatedFatContent")
    sodium_content: str | None = Field(default=None, alias="sodiumContent")
    sugar_content: str | None = Field(default=None, alias="sugarContent")
    trans_fat_content: str | None = Field(default=None, alias="transFatContent")
    unsaturated_fat_content: str | None = Field(default=None, alias="unsaturatedFatContent")


class RecipeSettingsPatch(ToolInput):
    public: bool = False
    show_nutrition: bool = Field(default=False, alias="showNutrition")
    show_assets: bool = Field(default=False, alias="showAssets")
    landscape_view: bool = Field(default=False, alias="landscapeView")
    disable_comments: bool = Field(default=True, alias="disableComments")
    locked: bool = False


class UpdateRecipeMetadataInput(ToolInput):
    slug: str = Field(min_length=1)
    expected_updated_at: str = Field(min_length=1, alias="expectedUpdatedAt")
    name: str | None = None
    description: str | None = None
    recipe_servings: float = Field(default=0, alias="recipeServings", ge=0)
    recipe_yield_quantity: float = Field(default=0, alias="recipeYieldQuantity", ge=0)
    recipe_yield: str | None = Field(default=None, alias="recipeYield")
    total_time: str | None = Field(default=None, alias="totalTime")
    prep_time: str | None = Field(default=None, alias="prepTime")
    cook_time: str | None = Field(default=None, alias="cookTime")
    perform_time: str | None = Field(default=None, alias="performTime")
    org_url: str | None = Field(default=None, alias="orgURL")
    nutrition: RecipeNutritionPatch | None = None
    settings: RecipeSettingsPatch = Field(default_factory=RecipeSettingsPatch)
    extras: JsonObject = Field(default_factory=dict)
    remove_extra_keys: list[str] = Field(default_factory=list, alias="removeExtraKeys")
