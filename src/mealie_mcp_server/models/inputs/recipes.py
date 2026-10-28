from pydantic import Field

from mealie_mcp_server.models.inputs.base import ToolInput


class GetRecipesInput(ToolInput):
    search: str | None = None
    page: float | None = None
    per_page: float | None = Field(default=None, alias="perPage")
    categories: list[str] | None = None
    tags: list[str] | None = None
    require_all_tags: bool | None = Field(default=None, alias="requireAllTags")
    require_all_categories: bool | None = Field(default=None, alias="requireAllCategories")


class GetRecipeDetailedInput(ToolInput):
    slug: str


class GetRecipeConciseInput(ToolInput):
    slug: str


class GetRecipesBatchInput(ToolInput):
    slugs: list[str]


class GetRecipesDetailedBatchInput(ToolInput):
    slugs: list[str]


class CreateRecipeInput(ToolInput):
    name: str
    ingredients: list[str] | None = None
    instructions: list[str] | None = None


class DuplicateRecipeInput(ToolInput):
    slug: str
    name: str | None = None


class DeleteRecipeInput(ToolInput):
    slug: str
