from pydantic import Field

from mealie_mcp_server.models.inputs.base import ToolInput


class SetRecipeImageInput(ToolInput):
    slug: str
    image_base64: str | None = Field(alias="imageBase64")
    extension: str | None = None


class RecipeImageFileRef(ToolInput):
    download_url: str
    file_id: str
    mime_type: str | None = None
    file_name: str | None = None


class SetRecipeImageFromFileInput(ToolInput):
    slug: str
    file: RecipeImageFileRef


class SetRecipeImageFromUrlInput(ToolInput):
    slug: str
    image_url: str = Field(alias="imageUrl")
