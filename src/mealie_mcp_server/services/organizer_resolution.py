from collections.abc import Awaitable, Callable
from typing import Literal, TypedDict

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.support.strings import trim


class OrganizerItem(TypedDict):
    id: str
    name: str
    slug: str


class ResolveResult(TypedDict):
    resolved: list[OrganizerItem]
    created: list[OrganizerItem]
    missing: list[str]


class CollectionResult(TypedDict):
    final: list[OrganizerItem]
    added: list[OrganizerItem]
    removed: list[OrganizerItem]


async def resolve_organizer_values(
    client: MealieClient,
    kind: Literal["category", "tag", "tool"],
    values: list[str],
    *,
    create_missing: bool = False,
) -> ResolveResult:
    path = {
        "category": "/api/organizers/categories",
        "tag": "/api/organizers/tags",
        "tool": "/api/organizers/tools",
    }[kind]
    response = await client.request("GET", path, params=[("perPage", "-1")])
    if not isinstance(response, dict):
        raise ValueError("Invalid Mealie organizer response.")
    existing = to_organizer_items(response.get("items"))

    async def create(name: str) -> JsonObject:
        created = await client.request("POST", path, json={"name": name})
        if not isinstance(created, dict):
            raise ValueError("Invalid Mealie organizer response.")
        return created

    return await resolve_values(values, existing, create_missing, create)


def to_organizer_items(raw: JsonValue) -> list[OrganizerItem]:
    if not isinstance(raw, list):
        return []
    return [to_organizer_item(item) for item in raw if isinstance(item, dict)]


def to_organizer_item(raw: JsonObject) -> OrganizerItem:
    def string(key: str) -> str:
        if key not in raw:
            return "undefined"
        value = raw[key]
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    return {"id": string("id"), "name": string("name"), "slug": string("slug")}


async def resolve_values(
    values: list[str],
    existing: list[OrganizerItem],
    create_missing: bool,
    create: Callable[[str], Awaitable[JsonObject]],
) -> ResolveResult:
    by_id = {item["id"].lower(): item for item in existing}
    by_slug = {item["slug"].lower(): item for item in existing}
    by_name = {item["name"].lower(): item for item in existing}
    resolved: dict[str, OrganizerItem] = {}
    created: list[OrganizerItem] = []
    missing: list[str] = []
    created_this_call: dict[str, OrganizerItem] = {}
    for raw in values:
        value = trim(raw)
        if not value:
            continue
        key = value.lower()
        match = by_id.get(key) or by_slug.get(key) or by_name.get(key) or created_this_call.get(key)
        if match is not None:
            resolved[match["id"]] = match
            continue
        if not create_missing:
            missing.append(raw)
            continue
        item = to_organizer_item(await create(value))
        for created_key in [key, item["id"].lower(), item["slug"].lower(), item["name"].lower()]:
            created_this_call[created_key] = item
        resolved[item["id"]] = item
        created.append(item)
    return {"resolved": list(resolved.values()), "created": created, "missing": missing}


def compute_final(
    mode: Literal["merge", "replace"], current: list[OrganizerItem], requested: list[OrganizerItem]
) -> CollectionResult:
    if mode == "replace":
        final = {item["id"]: item for item in requested}
        current_ids = {item["id"] for item in current}
        return {
            "final": list(final.values()),
            "added": [item for item in final.values() if item["id"] not in current_ids],
            "removed": [item for item in current if item["id"] not in final],
        }
    return compute_delta(current, requested, [])


def compute_delta(
    current: list[OrganizerItem], additions: list[OrganizerItem], removals: list[OrganizerItem]
) -> CollectionResult:
    removal_ids = {item["id"] for item in removals}
    removed = [item for item in current if item["id"] in removal_ids]
    final = {item["id"]: item for item in current if item["id"] not in removal_ids}
    added: list[OrganizerItem] = []
    for item in additions:
        if item["id"] not in final:
            final[item["id"]] = item
            added.append(item)
    return {"final": list(final.values()), "added": added, "removed": removed}
