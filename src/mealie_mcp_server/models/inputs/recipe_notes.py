"""Strict note identities and optimistic recipe snapshot tokens."""

from typing import Annotated

from pydantic import Field, model_validator

from mealie_mcp_server.models.inputs.base import ToolInput

type NoteReferenceId = Annotated[
    str,
    Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
]


class GetRecipeNotesInput(ToolInput):
    slug: str = Field(min_length=1)


class NoteWriteInput(GetRecipeNotesInput):
    expected_updated_at: str = Field(alias="expectedUpdatedAt", min_length=1)


class AddRecipeNoteInput(NoteWriteInput):
    title: str
    text: str
    reference_id: NoteReferenceId | None = Field(default=None, alias="referenceId")

    @model_validator(mode="after")
    def disallow_null_reference(self) -> AddRecipeNoteInput:
        if "reference_id" in self.model_fields_set and self.reference_id is None:
            raise ValueError("referenceId must be a UUID string when supplied.")
        return self


class UpdateRecipeNoteInput(NoteWriteInput):
    reference_id: NoteReferenceId = Field(alias="referenceId")
    title: str | None = None
    text: str | None = None

    @model_validator(mode="after")
    def require_changes(self) -> UpdateRecipeNoteInput:
        supplied = self.model_fields_set.intersection({"title", "text"})
        if not supplied or any(getattr(self, key) is None for key in supplied):
            raise ValueError("Supply title and/or text as strings (empty strings are allowed).")
        return self


class DeleteRecipeNoteInput(NoteWriteInput):
    reference_id: NoteReferenceId = Field(alias="referenceId")
    remove_references: bool = Field(default=False, alias="removeReferences")
