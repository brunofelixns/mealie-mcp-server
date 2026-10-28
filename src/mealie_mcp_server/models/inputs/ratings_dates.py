from pydantic import Field

from mealie_mcp_server.models.inputs.base import ToolInput


class SetRecipeRatingInput(ToolInput):
    slug: str
    rating: float | None = Field(default=None, ge=0.5, le=5, multiple_of=0.5)
    is_favorite: bool | None = Field(default=None, alias="isFavorite")


class MarkRecipeLastMadeInput(ToolInput):
    slug: str
    timestamp: str | None = None
