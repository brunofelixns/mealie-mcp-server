"""Public input semantics; HTTP configuration intentionally uses different parsing."""

from pydantic import BaseModel, ConfigDict


class ToolInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        allow_inf_nan=False,
        validate_by_alias=True,
        validate_by_name=False,
    )
