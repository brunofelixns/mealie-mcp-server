"""Strict inputs for Mealie v3.29 comments, sharing and recipe timeline."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, field_validator, model_validator

from mealie_mcp_server.mealie.client import encode_path_segment
from mealie_mcp_server.models.inputs.base import JsonInteger, ToolInput

MAX_IMAGE_BASE64_LENGTH = 4 * ((10 * 1024 * 1024 + 2) // 3)
type UUID4String = Annotated[
    str,
    Field(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
    ),
]


def _slug(value: str) -> str:
    encode_path_segment(value, "slug")
    return value


def _timestamp(value: str) -> str:
    datetime.fromisoformat(value)
    return value


type RecipeSlug = Annotated[str, AfterValidator(_slug)]
type Timestamp = Annotated[str, AfterValidator(_timestamp)]
type EventImage = Literal["has image", "does not have image"]


class GetRecipeCommentsInput(ToolInput):
    slug: RecipeSlug


class CreateRecipeCommentInput(ToolInput):
    slug: RecipeSlug
    text: str

    @field_validator("text")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Comment text must not be empty.")
        return value


class UpdateRecipeCommentInput(ToolInput):
    comment_id: UUID4String = Field(alias="commentId")
    text: str

    @field_validator("text")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Comment text must not be empty.")
        return value


class DeleteRecipeCommentInput(ToolInput):
    comment_id: UUID4String = Field(alias="commentId")


class GetRecipeShareLinksInput(ToolInput):
    slug: RecipeSlug


class CreateRecipeShareLinkInput(ToolInput):
    slug: RecipeSlug
    expires_at: Timestamp | None = Field(default=None, alias="expiresAt")

    @model_validator(mode="after")
    def nonnull_expiry(self) -> Self:
        if "expires_at" in self.model_fields_set and self.expires_at is None:
            raise ValueError("expiresAt must be omitted or a timestamp.")
        return self


class DeleteRecipeShareLinkInput(ToolInput):
    token_id: UUID4String = Field(alias="tokenId")


class GetRecipeTimelineInput(ToolInput):
    slug: RecipeSlug
    page: JsonInteger = Field(default=1, ge=1)
    per_page: JsonInteger = Field(default=50, alias="perPage", ge=1, le=1000)


class CreateRecipeTimelineEventInput(ToolInput):
    slug: RecipeSlug
    subject: str
    event_type: Literal["system", "info", "comment"] = Field(alias="eventType")
    event_message: str | None = Field(default=None, alias="eventMessage")
    timestamp: Timestamp | None = None
    user_id: UUID4String | None = Field(default=None, alias="userId")
    image: EventImage | None = None

    @model_validator(mode="after")
    def nonnull_timestamp(self) -> Self:
        if "timestamp" in self.model_fields_set and self.timestamp is None:
            raise ValueError("timestamp must be omitted or a timestamp.")
        return self


class UpdateRecipeTimelineEventInput(ToolInput):
    event_id: UUID4String = Field(alias="eventId")
    subject: str
    event_message: str | None = Field(default=None, alias="eventMessage")
    image: EventImage | None = None


class DeleteRecipeTimelineEventInput(ToolInput):
    event_id: UUID4String = Field(alias="eventId")


class SetRecipeTimelineEventImageInput(ToolInput):
    event_id: UUID4String = Field(alias="eventId")
    image_base64: str = Field(alias="imageBase64", min_length=1, max_length=MAX_IMAGE_BASE64_LENGTH)
    extension: Literal["png", "jpg", "jpeg", "gif", "webp"] | None = None
