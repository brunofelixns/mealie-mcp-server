"""Explicit native 3.30 recipe capabilities, independent of legacy contracts."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from mealie_mcp_server.models.inputs.base import ToolInput
from mealie_mcp_server.models.inputs.recipe_notes import NoteReferenceId

type Identifier = Annotated[str, Field(min_length=1, max_length=200)]
type FoodId = Annotated[
    str,
    Field(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
    ),
]
type ShortText = Annotated[str, Field(max_length=10000)]


class OrderingInput(ToolInput):
    order_by: Identifier | None = Field(default=None, alias="orderBy")
    order_by_null_position: Literal["first", "last"] | None = Field(
        default=None, alias="orderByNullPosition"
    )
    order_direction: Literal["asc", "desc"] = Field(default="desc", alias="orderDirection")
    query_filter: ShortText | None = Field(default=None, alias="queryFilter")
    pagination_seed: Identifier | None = Field(default=None, alias="paginationSeed")


class SearchRecipesInput(OrderingInput):
    search: ShortText | None = None
    categories: list[Identifier] | None = Field(default=None, max_length=100)
    tags: list[Identifier] | None = Field(default=None, max_length=100)
    tools: list[Identifier] | None = Field(default=None, max_length=100)
    foods: list[Identifier] | None = Field(default=None, max_length=100)
    households: list[Identifier] | None = Field(default=None, max_length=100)
    cookbook: Identifier | None = None
    page: int = Field(default=1, ge=1, le=2147483647)
    per_page: int = Field(default=50, alias="perPage", ge=1, le=1000)
    require_all_categories: bool = Field(default=False, alias="requireAllCategories")
    require_all_tags: bool = Field(default=False, alias="requireAllTags")
    require_all_tools: bool = Field(default=False, alias="requireAllTools")
    require_all_foods: bool = Field(default=False, alias="requireAllFoods")


class GetRecipeSuggestionsInput(OrderingInput):
    foods: list[FoodId] | None = Field(default=None, max_length=100)
    tools: list[FoodId] | None = Field(default=None, max_length=100)
    limit: int = Field(default=10, ge=1, le=1000)
    max_missing_foods: int = Field(default=5, alias="maxMissingFoods", ge=0, le=1000)
    max_missing_tools: int = Field(default=5, alias="maxMissingTools", ge=0, le=1000)
    include_foods_on_hand: bool = Field(default=True, alias="includeFoodsOnHand")
    include_tools_on_hand: bool = Field(default=True, alias="includeToolsOnHand")
    include_substitutions: bool = Field(default=True, alias="includeSubstitutions")


class ParseRecipeIngredientInput(ToolInput):
    parser: Literal["nlp", "brute", "openai"] = "nlp"
    ingredient: str = Field(min_length=1, max_length=10000)


class ParseRecipeIngredientsInput(ToolInput):
    parser: Literal["nlp", "brute", "openai"] = "nlp"
    ingredients: list[Annotated[str, Field(min_length=1, max_length=10000)]] = Field(
        min_length=1, max_length=100
    )


class FoodSubstitutionInput(ToolInput):
    model_config = ConfigDict(
        json_schema_extra={
            "anyOf": [
                {
                    "required": ["substituteFoodId"],
                    "properties": {"substituteFoodId": {"type": "string"}},
                },
                {
                    "required": ["note"],
                    "properties": {"note": {"type": "string", "pattern": r"\S"}},
                },
            ]
        }
    )
    substitute_food_id: FoodId | None = Field(default=None, alias="substituteFoodId")
    note: ShortText | None = None

    @model_validator(mode="after")
    def require_food_or_text(self) -> FoodSubstitutionInput:
        if self.substitute_food_id is None and (self.note is None or not self.note.strip()):
            raise ValueError("Supply a canonical substituteFoodId or a nonblank note.")
        return self


class IngredientSubstitutionUpdate(ToolInput):
    reference_id: NoteReferenceId = Field(alias="referenceId")
    substitutions: list[FoodSubstitutionInput] = Field(max_length=100)


class SnapshotInput(ToolInput):
    slug: Identifier
    expected_updated_at: str = Field(alias="expectedUpdatedAt", min_length=1, max_length=200)


class UpdateRecipeIngredientSubstitutionsInput(SnapshotInput):
    updates: list[IngredientSubstitutionUpdate] = Field(min_length=1, max_length=100)


class UpdateFoodSubstitutionsInput(ToolInput):
    food_id: FoodId = Field(alias="foodId")
    substitutions: list[FoodSubstitutionInput] = Field(max_length=100)


class InstructionDurationUpdate(ToolInput):
    index: int = Field(ge=0, le=2147483647)
    duration_seconds: Annotated[int, Field(ge=1, le=2147483647)] | None = Field(
        alias="durationSeconds"
    )


class UpdateRecipeInstructionDurationsInput(SnapshotInput):
    updates: list[InstructionDurationUpdate] = Field(min_length=1, max_length=100)
