"""Public input semantics; HTTP configuration intentionally uses different parsing."""

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from mealie_mcp_server.support.strings import trim


def _json_integer(value: object) -> object:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


type JsonInteger = Annotated[int, BeforeValidator(_json_integer)]


class ToolInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        allow_inf_nan=False,
        validate_by_alias=True,
        validate_by_name=False,
    )


class CandidateLookupInput(ToolInput):
    queries: list[str]
    max_matches_per_query: JsonInteger | None = Field(default=None, alias="maxMatchesPerQuery")

    @field_validator("queries")
    @classmethod
    def trim_queries(cls, queries: list[str]) -> list[str]:
        return [trim(query) for query in queries]
