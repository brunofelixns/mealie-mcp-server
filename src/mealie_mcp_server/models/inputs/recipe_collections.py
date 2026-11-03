"""Strict native cookbook, personal collection and recipe-action requests."""

from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import AfterValidator, BeforeValidator, Field, model_validator

from mealie_mcp_server.models.inputs.base import (
    JsonInteger,
    PositiveJsonInteger,
    ToolInput,
    normalize_json_integer,
)
from mealie_mcp_server.models.inputs.recipe_collaboration import RecipeSlug, UUID4String

type CollectionPageSize = Annotated[
    int, Field(ge=1, le=1000), BeforeValidator(normalize_json_integer)
]


class EmptyInput(ToolInput):
    pass


class GetRecipeHouseholdInput(ToolInput):
    slug: RecipeSlug = Field(min_length=1, max_length=255)


class ListCollectionsInput(ToolInput):
    page: PositiveJsonInteger = 1
    per_page: CollectionPageSize = Field(default=50, alias="perPage")
    order_by: str | None = Field(default=None, alias="orderBy", max_length=500)
    order_by_null_position: Literal["first", "last"] | None = Field(
        default=None, alias="orderByNullPosition"
    )
    order_direction: Literal["asc", "desc"] = Field(default="desc", alias="orderDirection")
    query_filter: str | None = Field(default=None, alias="queryFilter", max_length=10000)
    pagination_seed: str | None = Field(default=None, alias="paginationSeed", max_length=500)


class CookbookIdInput(ToolInput):
    cookbook_id: RecipeSlug = Field(alias="cookbookId")


class CookbookFields(ToolInput):
    name: str = Field(min_length=1, max_length=1000)
    description: str = Field(default="", max_length=10000)
    position: JsonInteger = 1
    public: bool = False
    query_filter_string: str = Field(default="", alias="queryFilterString", max_length=10000)


class CreateCookbookInput(CookbookFields):
    pass


class CookbookChanges(ToolInput):
    name: str | None = Field(default=None, min_length=1, max_length=1000)
    description: str | None = Field(default=None, max_length=10000)
    position: JsonInteger | None = None
    public: bool | None = None
    query_filter_string: str | None = Field(
        default=None, alias="queryFilterString", max_length=10000
    )

    @model_validator(mode="after")
    def supplied(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one change.")
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Cookbook changes cannot be null.")
        return self


class UpdateCookbookInput(CookbookIdInput):
    changes: CookbookChanges


class CommentIdInput(ToolInput):
    comment_id: UUID4String = Field(alias="commentId")


class TimelineEventIdInput(ToolInput):
    event_id: UUID4String = Field(alias="eventId")


class ShareLinkIdInput(ToolInput):
    token_id: UUID4String = Field(alias="tokenId")


class RecipeActionIdInput(ToolInput):
    action_id: UUID4String = Field(alias="actionId")


def _action_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Expected an HTTP(S) action URL without credentials.")
    return value


type ActionUrl = Annotated[str, Field(min_length=1, max_length=4000), AfterValidator(_action_url)]


class CreateRecipeActionInput(ToolInput):
    action_type: Literal["link", "post"] = Field(alias="actionType")
    title: str = Field(min_length=1, max_length=1000)
    url: ActionUrl


class RecipeActionChanges(ToolInput):
    action_type: Literal["link", "post"] | None = Field(default=None, alias="actionType")
    title: str | None = Field(default=None, min_length=1, max_length=1000)
    url: ActionUrl | None = None

    @model_validator(mode="after")
    def supplied(self) -> Self:
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Provide at least one non-null change.")
        return self


class UpdateRecipeActionInput(RecipeActionIdInput):
    changes: RecipeActionChanges


class TriggerRecipeActionInput(RecipeActionIdInput):
    slug: RecipeSlug
    recipe_scale: float = Field(default=1, alias="recipe_scale", gt=0)
