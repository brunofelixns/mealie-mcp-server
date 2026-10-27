"""Shared food/unit REST mechanics; each MCP tool still has an explicit typed handler."""

from dataclasses import dataclass
from typing import Literal, NoReturn

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient, encode_path_segment, format_params
from mealie_mcp_server.mealie.errors import MealieApiError
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.support.strings import trim


@dataclass(frozen=True)
class Vocabulary:
    kind: Literal["food", "unit"]
    writable: tuple[str, ...]

    @property
    def path(self) -> str:
        return "/api/" + self.kind + "s"

    def identifier(self, value: str) -> str:
        identifier = trim(value)
        if not identifier:
            raise ValueError(f"{self.kind}Id is required.")
        return identifier

    def _raise(self, context: str, error: Exception, identifier: str | None = None) -> NoReturn:
        if identifier is not None and isinstance(error, MealieApiError) and error.status == 404:
            context = f"{self.kind.title()} not found: {identifier}"
        raise RuntimeError(f"{context}: {error}") from error

    def _changes(self, data: JsonObject) -> JsonObject:
        payload = {
            key: value
            for key, value in data.items()
            if key in self.writable and key not in {"id", "extras"}
        }
        if "aliases" in payload:
            aliases = payload["aliases"]
            if not isinstance(aliases, list) or any(not isinstance(name, str) for name in aliases):
                raise ValueError("Aliases must be strings.")
            payload["aliases"] = [{"name": name} for name in aliases]
        return payload

    async def list(
        self, client: MealieClient, search: str | None, page: float | None, per_page: float | None
    ) -> JsonValue:
        try:
            return await client.request(
                "GET",
                self.path,
                params=list(
                    format_params({"search": search, "page": page, "perPage": per_page}).items()
                ),
            )
        except Exception as error:
            self._raise(f"Unable to retrieve {self.kind}s", error)

    async def get(self, client: MealieClient, value: str) -> JsonValue:
        identifier = self.identifier(value)
        try:
            return await client.request(
                "GET", self.path + "/" + encode_path_segment(identifier, "id")
            )
        except Exception as error:
            self._raise(f"Unable to retrieve {self.kind} {identifier}", error, identifier)

    async def create(self, client: MealieClient, data: JsonObject) -> JsonValue:
        raw = data.get("name")
        name = trim(raw) if isinstance(raw, str) else ""
        if not name:
            raise ValueError(f"{self.kind.title()} name cannot be empty.")
        payload = self._changes(data)
        payload["name"] = name
        try:
            return await client.request("POST", self.path, json=payload)
        except Exception as error:
            self._raise(f"Unable to create {self.kind}", error)

    async def update(self, client: MealieClient, value: str, data: JsonObject) -> JsonValue:
        identifier = self.identifier(value)
        if not any(key in data for key in self.writable if key not in {"id", "extras"}):
            raise ValueError("At least one field must be supplied for an update.")
        try:
            path = self.path + "/" + encode_path_segment(identifier, "id")
            existing = await client.request("GET", path)
            if not isinstance(existing, dict):
                raise ValueError(f"Invalid Mealie {self.kind} response.")
            payload = {key: existing[key] for key in self.writable if key in existing}
            payload.update(self._changes(data))
            return await client.request("PUT", path, json=payload)
        except Exception as error:
            self._raise(f"Unable to update {self.kind} {identifier}", error, identifier)

    async def delete(self, client: MealieClient, value: str) -> JsonValue:
        identifier = self.identifier(value)
        try:
            return await client.request(
                "DELETE", self.path + "/" + encode_path_segment(identifier, "id")
            )
        except Exception as error:
            references = (
                "existing recipes or shopping list items"
                if self.kind == "food"
                else "existing recipe ingredients"
            )
            self._raise(
                f"Unable to delete {self.kind} {identifier}. "
                f"If this {self.kind} is still referenced by {references}, "
                "Mealie will refuse to delete it",
                error,
                identifier,
            )
