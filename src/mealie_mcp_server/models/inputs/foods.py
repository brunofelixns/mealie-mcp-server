from pydantic import Field

from mealie_mcp_server.models.inputs.base import CandidateLookupInput, ToolInput


class GetFoodsInput(ToolInput):
    search: str | None = None
    page: float | None = None
    per_page: float | None = Field(default=None, alias="perPage")


class GetFoodInput(ToolInput):
    food_id: str = Field(alias="foodId")


class GetFoodMatchesInput(CandidateLookupInput):
    pass


class CreateFoodInput(ToolInput):
    name: str
    plural_name: str | None = Field(default=None, alias="pluralName")
    description: str | None = None
    aliases: list[str] | None = None
    label_id: str | None = Field(default=None, alias="labelId")


class UpdateFoodInput(ToolInput):
    food_id: str = Field(alias="foodId")
    name: str | None = None
    plural_name: str | None = Field(default=None, alias="pluralName")
    description: str | None = None
    aliases: list[str] | None = None
    label_id: str | None = Field(default=None, alias="labelId")
    households_with_ingredient_food: list[str] | None = Field(
        default=None, alias="householdsWithIngredientFood"
    )


class DeleteFoodInput(ToolInput):
    food_id: str = Field(alias="foodId")


class MergeFoodsInput(ToolInput):
    from_food_id: str = Field(alias="fromFoodId")
    to_food_id: str = Field(alias="toFoodId")
