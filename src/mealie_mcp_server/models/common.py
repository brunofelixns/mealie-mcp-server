"""JSON and field-presence contracts shared by every Mealie mutation."""

from pydantic import BaseModel, JsonValue

type JsonObject = dict[str, JsonValue]


class UnsetType:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET = UnsetType()


def provided_fields(model: BaseModel) -> JsonObject:
    """Omit absent fields while preserving explicit null, zero, false and empty collections."""
    return model.model_dump(mode="json", by_alias=True, exclude_unset=True)
