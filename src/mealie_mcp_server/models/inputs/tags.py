from pydantic import Field

from mealie_mcp_server.models.inputs.base import ToolInput


class GetTagsInput(ToolInput):
    page: float | None = None
    per_page: float | None = Field(default=None, alias="perPage")


class GetEmptyTagsInput(ToolInput):
    pass


class CreateTagInput(ToolInput):
    name: str


class GetTagInput(ToolInput):
    tag_id: str = Field(alias="tagId")


class GetTagBySlugInput(ToolInput):
    tag_slug: str = Field(alias="tagSlug")


class UpdateTagInput(ToolInput):
    tag_id: str = Field(alias="tagId")
    name: str | None = None


class DeleteTagInput(ToolInput):
    tag_id: str = Field(alias="tagId")
