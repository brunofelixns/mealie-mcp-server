from pydantic import Field

from mealie_mcp_server.models.inputs.base import CandidateLookupInput, ToolInput


class GetUnitsInput(ToolInput):
    search: str | None = None
    page: float | None = None
    per_page: float | None = Field(default=None, alias="perPage")


class GetUnitInput(ToolInput):
    unit_id: str = Field(alias="unitId")


class GetUnitMatchesInput(CandidateLookupInput):
    pass


class CreateUnitInput(ToolInput):
    name: str
    plural_name: str | None = Field(default=None, alias="pluralName")
    description: str | None = None
    aliases: list[str] | None = None
    abbreviation: str | None = None
    plural_abbreviation: str | None = Field(default=None, alias="pluralAbbreviation")
    use_abbreviation: bool | None = Field(default=None, alias="useAbbreviation")
    fraction: bool | None = None
    standard_quantity: float | None = Field(default=None, alias="standardQuantity")
    standard_unit: str | None = Field(default=None, alias="standardUnit")


class UpdateUnitInput(ToolInput):
    unit_id: str = Field(alias="unitId")
    name: str | None = None
    plural_name: str | None = Field(default=None, alias="pluralName")
    description: str | None = None
    aliases: list[str] | None = None
    abbreviation: str | None = None
    plural_abbreviation: str | None = Field(default=None, alias="pluralAbbreviation")
    use_abbreviation: bool | None = Field(default=None, alias="useAbbreviation")
    fraction: bool | None = None
    standard_quantity: float | None = Field(default=None, alias="standardQuantity")
    standard_unit: str | None = Field(default=None, alias="standardUnit")


class DeleteUnitInput(ToolInput):
    unit_id: str = Field(alias="unitId")
