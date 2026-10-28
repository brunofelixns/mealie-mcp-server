"""Bind explicit Python handlers to the unchanged curated MCP input contracts."""

from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_context
from fastmcp.tools import Tool, ToolResult
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as SchemaValidationError
from mcp.types import CallToolResult, ToolAnnotations
from mcp.types import Tool as MCPTool
from pydantic import BaseModel, PrivateAttr, ValidationError

from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.tools.helpers import error_result, get_state

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState

type Handler = Callable[[BaseModel, "AppState"], Awaitable[CallToolResult]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    endpoints: tuple[str, ...] = ()


def _input_error(error: SchemaValidationError | ValidationError) -> ValueError:
    if isinstance(error, SchemaValidationError):
        path = ".".join(map(str, error.absolute_path)) or "arguments"
        detail = str(error.validator)
        if error.validator == "additionalProperties" and isinstance(error.instance, dict):
            properties = (
                error.schema.get("properties", {}) if isinstance(error.schema, Mapping) else {}
            )
            unknown = sorted(set(error.instance) - set(properties))
            detail += ": " + ", ".join(unknown)
        elif error.validator == "required" and isinstance(error.instance, dict):
            required = error.validator_value if isinstance(error.validator_value, list) else []
            missing = [name for name in required if name not in error.instance]
            detail += ": " + ", ".join(missing)
        return ValueError(f"Invalid arguments at {path} ({detail}).")
    paths = sorted({".".join(map(str, item["loc"])) for item in error.errors(include_input=False)})
    return ValueError("Invalid arguments at " + ", ".join(paths) + ".")


class ContractTool(Tool):
    _input_model: type[BaseModel] = PrivateAttr()
    _handler: Handler = PrivateAttr()
    _validator: Draft202012Validator = PrivateAttr()

    def __init__(
        self, definition: ToolDefinition, input_model: type[BaseModel], handler: Handler
    ) -> None:
        schema = deepcopy(definition.input_schema)
        Draft202012Validator.check_schema(schema)
        super().__init__(
            name=definition.name,
            description=definition.description,
            parameters=schema,
            output_schema=deepcopy(definition.output_schema),
            annotations=(
                ToolAnnotations.model_validate(definition.annotations)
                if definition.annotations is not None
                else None
            ),
            meta=deepcopy(definition.meta),
        )
        self._input_model = input_model
        self._handler = handler
        self._validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def to_mcp_tool(self, **overrides: Any) -> MCPTool:
        # Use the public serialization hook to retain the original curated wire metadata.
        overrides.setdefault("_meta", deepcopy(self.meta))
        return super().to_mcp_tool(**overrides)

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            request = self._input_model.model_validate(arguments, strict=True)
            self._validator.validate(provided_fields(request))
        except (SchemaValidationError, ValidationError) as error:
            return ToolResult.from_mcp_result(error_result(_input_error(error)))
        try:
            result = await self._handler(request, get_state(get_context()))
        except Exception as error:
            result = error_result(error)
        return ToolResult.from_mcp_result(result)


def register_contract_tool[T: BaseModel](
    server: FastMCP,
    definition: ToolDefinition,
    input_model: type[T],
    handler: Callable[[T, AppState], Awaitable[CallToolResult]],
) -> None:
    async def invoke(request: BaseModel, state: AppState) -> CallToolResult:
        return await handler(cast(T, request), state)

    server.add_tool(ContractTool(definition, input_model, invoke))
