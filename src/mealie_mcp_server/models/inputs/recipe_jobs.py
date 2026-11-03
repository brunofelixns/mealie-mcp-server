"""Bounded explicit inputs for native recipe jobs and guarded metadata batches."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, BeforeValidator, Field, field_validator, model_validator

from mealie_mcp_server.mealie.client import encode_path_segment
from mealie_mcp_server.models.inputs.base import (
    NonNegativeJsonInteger,
    ToolInput,
    normalize_json_integer,
)
from mealie_mcp_server.models.inputs.recipe_io import IMPORT_MAX_BYTES, RemoteUrl, Segment
from mealie_mcp_server.models.inputs.recipe_metadata import UpdateRecipeMetadataInput

AI_IMAGE_MAX_BYTES = 5 * 1024 * 1024
AI_TOTAL_IMAGE_MAX_BYTES = 20 * 1024 * 1024

type MetadataConcurrency = Annotated[
    int, Field(ge=1, le=5), BeforeValidator(normalize_json_integer)
]


def uuid4_string(value: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError:
        raise ValueError("Expected a UUID4 identifier.") from None
    if parsed.version != 4:
        raise ValueError("Expected a UUID4 identifier.")
    return value


type UUID4String = Annotated[
    str, Field(pattern=r"^[0-9a-fA-F-]{36}$"), AfterValidator(uuid4_string)
]


class PreviewRecipeFromUrlInput(ToolInput):
    url: RemoteUrl
    use_open_ai: bool = Field(default=False, alias="useOpenAI")


class AiRecipeImage(ToolInput):
    filename: Segment
    media_type: Literal["image/png", "image/jpeg", "image/webp", "image/gif"] = Field(
        alias="mediaType"
    )
    data_base64: str = Field(
        alias="dataBase64", min_length=1, max_length=4 * ((AI_IMAGE_MAX_BYTES + 2) // 3)
    )

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value: str) -> str:
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Image filename contains invalid characters.")
        return value


class ImportRecipeWithAiInput(ToolInput):
    content: str | None = Field(default=None, max_length=IMPORT_MAX_BYTES)
    url: RemoteUrl | None = None
    translate_language: str | None = Field(
        default=None, alias="translateLanguage", min_length=1, max_length=100
    )
    create_new_organizers: bool = Field(default=False, alias="createNewOrganizers")
    images: list[AiRecipeImage] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def require_source(self) -> Self:
        if not (self.content and self.content.strip()) and not self.url and not self.images:
            raise ValueError("Provide content, a URL or images for native AI import.")
        return self


class BulkImportOrganizer(ToolInput):
    id: UUID4String | None = None
    group_id: UUID4String | None = Field(default=None, alias="groupId")
    name: str = Field(min_length=1, max_length=255)
    slug: Segment
    recipe_count: NonNegativeJsonInteger = Field(default=0, alias="recipeCount")


class BulkRecipeUrl(ToolInput):
    url: RemoteUrl
    categories: list[BulkImportOrganizer] | None = Field(default=None, max_length=100)
    tags: list[BulkImportOrganizer] | None = Field(default=None, max_length=100)


class ImportRecipesFromUrlsInput(ToolInput):
    imports: list[BulkRecipeUrl] = Field(min_length=1, max_length=100)


class GetRecipeImportReportsInput(ToolInput):
    pass


class GetRecipeImportReportInput(ToolInput):
    report_id: UUID4String = Field(alias="reportId")


class DeleteRecipesBulkInput(ToolInput):
    recipes: list[Segment] = Field(min_length=1, max_length=100)


class ExportRecipesBulkInput(DeleteRecipesBulkInput):
    export_type: Literal["json"] = Field(default="json", alias="exportType")


class GetRecipeBulkExportsInput(ToolInput):
    pass


class DownloadRecipeBulkExportInput(ToolInput):
    export_id: UUID4String = Field(alias="exportId")


class PurgeRecipeBulkExportsInput(ToolInput):
    pass


class BatchMetadataItem(UpdateRecipeMetadataInput):
    slug: Segment


class UpdateRecipeMetadataBatchInput(ToolInput):
    items: list[BatchMetadataItem] = Field(min_length=1, max_length=50)
    concurrency: MetadataConcurrency = 3

    @model_validator(mode="after")
    def unique_slugs(self) -> Self:
        if len({encode_path_segment(item.slug) for item in self.items}) != len(self.items):
            raise ValueError("Metadata batch cannot edit the same recipe twice.")
        return self
