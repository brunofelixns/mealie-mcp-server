"""Strict inputs for native recipe import/export and asset operations."""

from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator, Field

from mealie_mcp_server.mealie.client import encode_path_segment
from mealie_mcp_server.models.inputs.base import ToolInput

UPLOAD_MAX_BYTES = 10 * 1024 * 1024
ARCHIVE_MAX_BYTES = 20 * 1024 * 1024
EXPORT_MAX_BYTES = 20 * 1024 * 1024
IMPORT_MAX_BYTES = 2 * 1024 * 1024


def valid_segment(value: str) -> str:
    encode_path_segment(value)
    return value


def valid_url(value: str) -> str:
    try:
        url = urlsplit(value)
        valid = (
            url.scheme in {"https", "http"}
            and bool(url.hostname)
            and url.username is None
            and url.password is None
            and not url.fragment
        )
        _ = url.port
    except ValueError:
        valid = False
    if not valid or any(ord(char) <= 32 for char in value):
        raise ValueError("Expected an HTTP(S) URL without credentials or fragment.")
    return value


type Segment = Annotated[str, Field(min_length=1, max_length=255), AfterValidator(valid_segment)]
type RemoteUrl = Annotated[str, Field(max_length=8192), AfterValidator(valid_url)]


class UploadRecipeAssetInput(ToolInput):
    slug: Segment
    name: str = Field(min_length=1, max_length=255)
    icon: str = Field(min_length=1, max_length=100)
    extension: str = Field(pattern=r"^[A-Za-z0-9]+$", max_length=10)
    file_base64: str = Field(
        alias="fileBase64", min_length=1, max_length=4 * ((UPLOAD_MAX_BYTES + 2) // 3)
    )


class CreateRecipeAssetFromUrlInput(ToolInput):
    slug: Segment
    url: RemoteUrl


class ImportOptions(ToolInput):
    include_tags: bool = Field(default=False, alias="includeTags")
    include_categories: bool = Field(default=False, alias="includeCategories")


class ImportRecipeFromUrlInput(ImportOptions):
    url: RemoteUrl


class ImportRecipeFromHtmlOrJsonInput(ImportOptions):
    data: str = Field(min_length=1, max_length=IMPORT_MAX_BYTES)
    url: RemoteUrl | None = None


class ImportRecipeFromZipInput(ToolInput):
    archive_base64: str = Field(
        alias="archiveBase64", min_length=1, max_length=4 * ((ARCHIVE_MAX_BYTES + 2) // 3)
    )


class GetRecipeExportFormatsInput(ToolInput):
    pass


class ExportRecipeInput(ToolInput):
    slug: Segment
    template_name: str = Field(alias="templateName", min_length=1, max_length=255)
