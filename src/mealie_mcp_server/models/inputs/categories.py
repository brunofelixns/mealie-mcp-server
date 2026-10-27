from pydantic import Field

from mealie_mcp_server.models.inputs.base import ToolInput


class GetCategoriesInput(ToolInput):
    page: float | None = None
    per_page: float | None = Field(default=None, alias="perPage")


class GetEmptyCategoriesInput(ToolInput):
    pass


class CreateCategoryInput(ToolInput):
    name: str


class GetCategoryInput(ToolInput):
    category_id: str = Field(alias="categoryId")


class GetCategoryBySlugInput(ToolInput):
    category_slug: str = Field(alias="categorySlug")


class UpdateCategoryInput(ToolInput):
    category_id: str = Field(alias="categoryId")
    name: str | None = None


class DeleteCategoryInput(ToolInput):
    category_id: str = Field(alias="categoryId")
