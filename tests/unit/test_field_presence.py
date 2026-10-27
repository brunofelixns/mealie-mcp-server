"""A patch must preserve the caller's explicit null, zero, false and empty list."""

from pydantic import BaseModel, Field

from mealie_mcp_server.models.common import provided_fields


class PatchInput(BaseModel):
    value: int | None = None
    enabled: bool = False
    items: list[str] = Field(default_factory=list)


def test_only_explicit_fields_are_serialized() -> None:
    assert provided_fields(PatchInput()) == {}
    assert provided_fields(PatchInput(value=None, enabled=False, items=[])) == {
        "value": None,
        "enabled": False,
        "items": [],
    }
    assert provided_fields(PatchInput(value=0)) == {"value": 0}
