"""Upstream v1 continuation tokens and deterministic, page-local recipe ordering."""

import base64
import json
import math
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import NoReturn, TypeGuard, cast

from pydantic import JsonValue

from mealie_mcp_server.mealie.api import recipes
from mealie_mcp_server.mealie.client import MealieClient, scalar_string
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.support.strings import trim


class InvalidCursorError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid cursor: {reason}")


@dataclass(frozen=True)
class ScanCursor:
    last_created_at: str
    last_id: str
    page: int

    def as_json(self) -> JsonObject:
        return {
            "v": 1,
            "lastCreatedAt": self.last_created_at,
            "lastId": self.last_id,
            "page": self.page,
        }


@dataclass(frozen=True)
class ScannedRecipe:
    summary: JsonObject
    created_at: str
    id: str
    page: int


def encode_cursor(cursor: ScanCursor) -> str:
    raw = json.dumps(cursor.as_json(), ensure_ascii=False, separators=(",", ":"))
    # JSON.stringify escapes lone UTF-16 surrogates but preserves other Unicode characters.
    raw = re.sub(r"[\ud800-\udfff]", lambda match: f"\\u{ord(match[0]):04x}", raw)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(raw: str) -> ScanCursor:
    try:
        # Buffer.from(..., 'base64url') accepts both alphabets and ignores nonalphabet bytes.
        cleaned = re.sub(r"[^A-Za-z0-9+/_-]", "", raw.split("=", 1)[0])
        cleaned = cleaned[: len(cleaned) - 1] if len(cleaned) % 4 == 1 else cleaned
        decoded = base64.urlsafe_b64decode(cleaned + "=" * (-len(cleaned) % 4))
        value: JsonValue = json.loads(
            decoded.decode("utf-8", errors="replace"), parse_constant=_invalid_constant
        )
    except ValueError, UnicodeError:
        raise InvalidCursorError("not valid base64url-encoded JSON.") from None
    if not isinstance(value, (dict, list)):
        raise InvalidCursorError("decoded payload is not an object.")
    data = value if isinstance(value, dict) else {}
    version = data.get("v")
    if not is_number(version) or version != 1:
        raise InvalidCursorError("unsupported or missing cursor version.")
    created = data.get("lastCreatedAt")
    identifier = data.get("lastId")
    page = data.get("page")
    if not isinstance(created, str) or not created:
        raise InvalidCursorError("missing or malformed lastCreatedAt.")
    if not isinstance(identifier, str) or not identifier:
        raise InvalidCursorError("missing or malformed lastId.")
    if not is_number(page) or not math.isfinite(page) or int(page) != page or page < 1:
        raise InvalidCursorError("missing or malformed page.")
    return ScanCursor(created, identifier, int(page))


def is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _invalid_constant(value: str) -> NoReturn:
    raise ValueError("Not a JSON numeric constant.")


def string(value: JsonValue | None) -> str:
    return trim(value) if isinstance(value, str) else ""


def id_string(value: JsonValue | None) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return scalar_string(value)
    return ""


def to_array(value: JsonValue | None) -> list[JsonObject]:
    # Mealie collection rows have object shape; keep upstream's shallow array guard.
    return cast(list[JsonObject], value) if isinstance(value, list) else []


def taxonomy_item(raw: JsonObject) -> JsonObject:
    return {
        "id": id_string(raw.get("id")),
        "name": string(raw.get("name")),
        "slug": string(raw.get("slug")),
    }


def _position(created_at: str, identifier: str) -> tuple[bytes, bytes]:
    # ECMAScript relational comparison is UTF-16 code-unit order, not locale collation.
    return (
        created_at.encode("utf-16-be", errors="surrogatepass"),
        identifier.encode("utf-16-be", errors="surrogatepass"),
    )


async def scan_recipes_stable(
    client: MealieClient, cursor: ScanCursor | None = None
) -> AsyncGenerator[ScannedRecipe]:
    page = cursor.page if cursor else 1
    skip_until = _position(cursor.last_created_at, cursor.last_id) if cursor else None
    while True:
        result = await recipes.get_recipes(
            client, {"page": page, "perPage": 50, "orderBy": "createdAt", "orderDirection": "asc"}
        )
        rows = to_array(result.get("items"))
        if not rows:
            return
        entries = [
            ScannedRecipe(row, string(row.get("createdAt")), id_string(row.get("id")), page)
            for row in rows
        ]
        entries.sort(key=lambda entry: _position(entry.created_at, entry.id))
        for entry in entries:
            if skip_until is None or _position(entry.created_at, entry.id) > skip_until:
                yield entry
        skip_until = None
        total = result.get("total")
        if len(rows) < 50 or (is_number(total) and page * 50 >= total):
            return
        page += 1
