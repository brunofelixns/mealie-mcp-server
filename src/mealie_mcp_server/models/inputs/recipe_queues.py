from typing import Literal

from pydantic import Field

from mealie_mcp_server.models.inputs.base import JsonInteger, ToolInput

type TaxonomyState = Literal[
    "missing_either", "missing_both", "missing_categories", "missing_tags", "any"
]
type ParsingState = Literal["unparsed_only", "partially_parsed", "any"]


class RecipeQueueInput(ToolInput):
    cursor: str | None = None
    limit: JsonInteger = Field(default=25, ge=1, le=50)


class GetRecipesForClassificationInput(RecipeQueueInput):
    taxonomy_state: TaxonomyState = Field(default="missing_either", alias="taxonomyState")


class GetRecipesForIngredientParsingInput(RecipeQueueInput):
    state: ParsingState = "unparsed_only"


class EnrichmentFilters(ToolInput):
    ingredient_parsing: Literal["unparsed", "partial", "unparsed_or_partial"] | None = Field(
        default=None, alias="ingredientParsing"
    )
    ingredient_sections: bool | None = Field(default=None, alias="ingredientSections")
    instruction_ingredient_links: Literal["missing", "dangling", "missing_or_dangling"] | None = (
        Field(default=None, alias="instructionIngredientLinks")
    )
    tools: bool | None = None
    categories: bool | None = None
    tags: bool | None = None
    image: bool | None = None


class GetRecipesForDataEnrichmentInput(RecipeQueueInput):
    match: Literal["any", "all"] = "any"
    filters: EnrichmentFilters | None = None


class FindRecipesForIngredientsInput(ToolInput):
    ingredients: list[str] = Field(min_length=1)
    categories: list[str] | None = None
    tags: list[str] | None = None
    require_all_ingredients: bool | None = Field(default=None, alias="requireAllIngredients")
    require_all_categories: bool | None = Field(default=None, alias="requireAllCategories")
    require_all_tags: bool | None = Field(default=None, alias="requireAllTags")
    limit: float = 10
