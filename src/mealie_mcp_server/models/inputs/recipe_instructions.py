from pydantic import Field

from mealie_mcp_server.models.inputs.base import JsonInteger, ToolInput


class InstructionContent(ToolInput):
    text: str = Field(min_length=1)
    title: str | None = None
    summary: str | None = None
    ingredient_reference_ids: list[str] | None = Field(default=None, alias="ingredientReferenceIds")


class RecipeInstructionInput(InstructionContent):
    note_reference_ids: list[str] | None = Field(default=None, alias="noteReferenceIds")


class InstructionAddition(InstructionContent):
    insert_before_index: JsonInteger | None = Field(default=None, ge=0, alias="insertBeforeIndex")
    insert_after_index: JsonInteger | None = Field(default=None, ge=0, alias="insertAfterIndex")


class InstructionUpdate(ToolInput):
    index: JsonInteger = Field(ge=0)
    text: str | None = Field(default=None, min_length=1)
    title: str | None = None
    summary: str | None = None
    ingredient_reference_ids: list[str] | None = Field(default=None, alias="ingredientReferenceIds")


class UpdateRecipeInstructionsInput(ToolInput):
    slug: str
    expected_updated_at: str = Field(min_length=1, alias="expectedUpdatedAt")
    instructions: list[RecipeInstructionInput] | None = None
    add_instructions: list[InstructionAddition] | None = Field(
        default=None, alias="addInstructions"
    )
    update_instructions: list[InstructionUpdate] | None = Field(
        default=None, alias="updateInstructions"
    )
    remove_instruction_indexes: list[JsonInteger] | None = Field(
        default=None, alias="removeInstructionIndexes"
    )


class UpdateRecipeInstructionsBatchInput(ToolInput):
    updates: list[UpdateRecipeInstructionsInput] = Field(min_length=1, max_length=25)
