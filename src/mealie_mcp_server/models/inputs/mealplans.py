import re
from typing import Annotated, Literal

from pydantic import Field, field_validator

from mealie_mcp_server.models.inputs.base import ToolInput


class DateRangeInput(ToolInput):
    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")

    @field_validator("start_date", "end_date")
    @classmethod
    def date_format(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
            raise ValueError("Expected YYYY-MM-DD")
        return value


class GetAllMealplansInput(DateRangeInput):
    page: float | None = None
    per_page: float | None = Field(default=None, alias="perPage")


class GetMealplanWithRecipesInput(DateRangeInput):
    start_date: str = Field(alias="startDate")
    end_date: str = Field(alias="endDate")


class MealplanEntry(ToolInput):
    date: str
    recipe_id: str | None = Field(default=None, alias="recipeId")
    title: str | None = None
    entry_type: str = Field(default="breakfast", alias="entryType")


class CreateMealplanInput(MealplanEntry):
    pass


class CreateMealplanBulkInput(ToolInput):
    entries: list[MealplanEntry]


class GetTodaysMealplanInput(ToolInput):
    pass


class DeleteAction(ToolInput):
    action: Literal["delete"]
    id: str


class ReplaceAction(ToolInput):
    action: Literal["replace"]
    id: str
    date: str | None = None
    recipe_id: str | None = Field(default=None, alias="recipeId")
    title: str | None = None
    entry_type: str | None = Field(default=None, alias="entryType")


class AppendAction(MealplanEntry):
    action: Literal["append"]


type MealplanAction = Annotated[
    DeleteAction | ReplaceAction | AppendAction, Field(discriminator="action")
]


class PatchMealplanInput(ToolInput):
    actions: list[MealplanAction]
