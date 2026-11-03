"""Mealie 3.30 weekly entries, native rules and calendar inputs."""

import re
from datetime import date, time, timedelta
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BeforeValidator, Field, model_validator

from mealie_mcp_server.models.inputs.base import (
    PositiveJsonInteger,
    ToolInput,
    normalize_json_integer,
)
from mealie_mcp_server.models.inputs.recipe_collaboration import RecipeSlug, UUID4String
from mealie_mcp_server.models.inputs.recipe_collections import ListCollectionsInput

type EntryType = Literal["breakfast", "lunch", "dinner", "side", "snack", "drink", "dessert"]
type RuleDay = Literal[
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "unset"
]
type CalendarDuration = Annotated[
    int, Field(ge=1, le=1440), BeforeValidator(normalize_json_integer)
]


def _date(value: str) -> str:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Expected YYYY-MM-DD.")
    date.fromisoformat(value)
    return value


type DateString = Annotated[str, AfterValidator(_date)]
type UUIDString = Annotated[
    str, Field(pattern=r"^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
]


def validate_week(start: str, end: str | None) -> None:
    if end is not None and date.fromisoformat(end) != date.fromisoformat(start) + timedelta(days=6):
        raise ValueError("endDate must be exactly six days after date.")


class MealplanEntryFields(ToolInput):
    date: DateString
    end_date: DateString | None = Field(default=None, alias="endDate")
    entry_type: EntryType = Field(default="breakfast", alias="entryType")
    title: str = Field(default="", max_length=10000)
    text: str = Field(default="", max_length=100000)
    recipe_id: UUIDString | None = Field(default=None, alias="recipeId")
    recipe_scale: float = Field(default=1, alias="recipeScale", gt=0)

    @model_validator(mode="after")
    def weekly(self) -> Self:
        validate_week(self.date, self.end_date)
        return self


class CreateMealplanEntryInput(MealplanEntryFields):
    pass


class MealplanEntryIdInput(ToolInput):
    entry_id: PositiveJsonInteger = Field(alias="entryId")


class MealplanEntryChanges(ToolInput):
    date: DateString | None = None
    end_date: DateString | None = Field(default=None, alias="endDate")
    entry_type: EntryType | None = Field(default=None, alias="entryType")
    title: str | None = Field(default=None, max_length=10000)
    text: str | None = Field(default=None, max_length=100000)
    recipe_id: UUIDString | None = Field(default=None, alias="recipeId")
    recipe_scale: float | None = Field(default=None, alias="recipeScale", gt=0)

    @model_validator(mode="after")
    def supplied(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one change.")
        if any(
            getattr(self, key) is None for key in self.model_fields_set - {"end_date", "recipe_id"}
        ):
            raise ValueError("Only endDate and recipeId may be null.")
        if self.date is not None and "end_date" in self.model_fields_set:
            validate_week(self.date, self.end_date)
        return self


class UpdateMealplanEntryInput(MealplanEntryIdInput):
    changes: MealplanEntryChanges


class ListMealplanEntriesInput(ListCollectionsInput):
    start_date: DateString | None = None
    end_date: DateString | None = None
    include_week_entries: bool = False


class CreateRandomMealplanEntryInput(ToolInput):
    date: DateString
    end_date: DateString | None = Field(default=None, alias="endDate")
    entry_type: EntryType = Field(default="dinner", alias="entryType")

    @model_validator(mode="after")
    def weekly(self) -> Self:
        validate_week(self.date, self.end_date)
        return self


class MealplanRuleIdInput(ToolInput):
    rule_id: UUID4String = Field(alias="ruleId")


class CreateMealplanRuleInput(ToolInput):
    day: RuleDay = "unset"
    entry_type: EntryType | Literal["unset"] = Field(default="unset", alias="entryType")
    query_filter_string: str = Field(default="", alias="queryFilterString", max_length=10000)


class MealplanRuleChanges(ToolInput):
    day: RuleDay | None = None
    entry_type: EntryType | Literal["unset"] | None = Field(default=None, alias="entryType")
    query_filter_string: str | None = Field(
        default=None, alias="queryFilterString", max_length=10000
    )

    @model_validator(mode="after")
    def supplied(self) -> Self:
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Provide at least one non-null change.")
        return self


class UpdateMealplanRuleInput(MealplanRuleIdInput):
    changes: MealplanRuleChanges


def _timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError, ValueError:
        raise ValueError("Expected an IANA timezone.") from None
    return value


def _time(value: str) -> str:
    time.fromisoformat(value)
    return value


type TimeString = Annotated[str, AfterValidator(_time)]
type TimezoneString = Annotated[str, AfterValidator(_timezone)]


class GetMealplanIcalFeedInput(ToolInput):
    token: RecipeSlug
    types: list[EntryType] | None = Field(default=None, max_length=7)
    include_notes: bool = Field(default=True, alias="includeNotes")
    tz: TimezoneString | None = None
    lang: str | None = Field(default=None, max_length=20)
    duration: CalendarDuration = 60
    summary: str = Field(default="${type}: ${title}", max_length=500)
    description: str = Field(default="${note}\n\n${url}", max_length=500)
    breakfast: TimeString | None = None
    lunch: TimeString | None = None
    dinner: TimeString | None = None
    side: TimeString | None = None
    snack: TimeString | None = None
    drink: TimeString | None = None
    dessert: TimeString | None = None
