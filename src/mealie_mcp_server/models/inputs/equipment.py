from pydantic import Field

from mealie_mcp_server.models.inputs.base import CandidateLookupInput, ToolInput


class GetToolsInput(ToolInput):
    search: str | None = None
    page: float | None = None
    per_page: float | None = Field(default=None, alias="perPage")


class GetToolInput(ToolInput):
    tool_id: str = Field(alias="toolId")


class GetToolMatchesInput(CandidateLookupInput):
    pass


class CreateToolInput(ToolInput):
    name: str


class UpdateToolInput(ToolInput):
    tool_id: str = Field(alias="toolId")
    name: str | None = None


class DeleteToolInput(ToolInput):
    tool_id: str = Field(alias="toolId")
