"""Strict media identities; callers never provide download URLs or host paths."""

from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from mealie_mcp_server.mealie.client import encode_path_segment
from mealie_mcp_server.models.inputs.base import ToolInput
from mealie_mcp_server.models.inputs.recipe_collaboration import UUID4String


def _segment(value: str) -> str:
    encode_path_segment(value)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("Media identifiers cannot contain control characters.")
    return value


type MediaSegment = Annotated[str, Field(min_length=1, max_length=255), AfterValidator(_segment)]
type ImageVariant = Literal["original.webp", "min-original.webp", "tiny-original.webp"]


class GetRecipeAssetsInput(ToolInput):
    slug: MediaSegment


class DownloadRecipeAssetInput(GetRecipeAssetsInput):
    file_name: MediaSegment = Field(alias="fileName")


class DownloadRecipeImageInput(GetRecipeAssetsInput):
    file_name: ImageVariant = Field(default="original.webp", alias="fileName")


class DownloadRecipeTimelineImageInput(DownloadRecipeImageInput):
    event_id: UUID4String = Field(alias="eventId")


class GetSharedRecipeInput(ToolInput):
    token_id: UUID4String = Field(alias="tokenId")


class DownloadSharedRecipeInput(GetSharedRecipeInput):
    pass
