"""Recipe organizer inputs preserve legacy and delta forms independently."""

from typing import Literal

from pydantic import Field, field_validator

from mealie_mcp_server.models.inputs.base import ToolInput
from mealie_mcp_server.support.strings import trim


class TaxonomyMutation(ToolInput):
    categories: list[str] | None = None
    tags: list[str] | None = None
    add_categories: list[str] | None = Field(default=None, alias="addCategories")
    remove_categories: list[str] | None = Field(default=None, alias="removeCategories")
    add_tags: list[str] | None = Field(default=None, alias="addTags")
    remove_tags: list[str] | None = Field(default=None, alias="removeTags")
    mode: Literal["merge", "replace"] | None = None
    create_missing: bool | None = Field(default=None, alias="createMissing")

    @field_validator("add_categories", "remove_categories", "add_tags", "remove_tags")
    @classmethod
    def trim_delta(cls, values: list[str] | None) -> list[str] | None:
        return [trim(value) for value in values] if values is not None else None


class UpdateRecipeTaxonomyInput(TaxonomyMutation):
    slug: str


class UpdateRecipeTaxonomyBatchInput(ToolInput):
    updates: list[UpdateRecipeTaxonomyInput]


class EquipmentMutation(ToolInput):
    tools: list[str] | None = None
    add: list[str] | None = None
    remove: list[str] | None = None
    mode: Literal["merge", "replace"] | None = None
    create_missing: bool | None = Field(default=None, alias="createMissing")

    @field_validator("tools", "add", "remove")
    @classmethod
    def trim_values(cls, values: list[str] | None) -> list[str] | None:
        return [trim(value) for value in values] if values is not None else None


class UpdateRecipeToolsInput(EquipmentMutation):
    slug: str


class UpdateRecipeToolsBatchInput(ToolInput):
    updates: list[UpdateRecipeToolsInput]


class PatchRecipeInput(ToolInput):
    slug: str
    name: str | None = None
    description: str | None = None
    recipe_yield: str | None = Field(default=None, alias="recipeYield")
    total_time: str | None = Field(default=None, alias="totalTime")
    recipe_servings: float | None = Field(default=None, alias="recipeServings")
    recipe_yield_quantity: float | None = Field(default=None, alias="recipeYieldQuantity")
    org_url: str | None = Field(default=None, alias="orgURL")
    categories: list[str] | None = None
    tags: list[str] | None = None
    taxonomy_mode: Literal["merge", "replace"] | None = Field(default=None, alias="taxonomyMode")
    create_missing: bool | None = Field(default=None, alias="createMissing")
    instructions: list[str] | None = None
