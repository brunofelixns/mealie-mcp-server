"""Deterministic collection resolution shared by recipe taxonomy and equipment."""

from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue

from mealie_mcp_server.mealie.api import categories, equipment, tags
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.organizer_resolution import (
    OrganizerItem,
    compute_delta,
    compute_final,
    resolve_values,
    to_organizer_item,
    to_organizer_items,
)
from mealie_mcp_server.support.strings import trim

type OrganizerKind = Literal["category", "tag", "tool"]


def string_values(changes: JsonObject, key: str) -> list[str] | None:
    if key not in changes:
        return None
    value = changes[key]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be an array of strings.")
    return [item for item in value if isinstance(item, str)]


def mode_value(changes: JsonObject) -> Literal["merge", "replace"]:
    value = changes.get("mode", "merge")
    if value not in ("merge", "replace"):
        raise ValueError("Invalid organizer mode.")
    return "replace" if value == "replace" else "merge"


def payload_item(item: OrganizerItem) -> JsonObject:
    return {"id": item["id"], "name": item["name"], "slug": item["slug"]}


@dataclass
class CollectionOutcome:
    final: list[OrganizerItem]
    added: list[OrganizerItem]
    removed: list[OrganizerItem]
    created: list[OrganizerItem]

    @property
    def changed(self) -> bool:
        return bool(self.added or self.removed)

    def payload(self) -> list[JsonObject]:
        return [payload_item(item) for item in self.final]

    def as_json(self) -> JsonObject:
        return {
            "final": [payload_item(item) for item in self.final],
            "added": [payload_item(item) for item in self.added],
            "removed": [payload_item(item) for item in self.removed],
            "created": [payload_item(item) for item in self.created],
        }


def _object(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError("Invalid Mealie organizer response.")
    return value


async def _catalog(client: MealieClient, kind: OrganizerKind) -> list[OrganizerItem]:
    if kind == "category":
        response = await categories.get_categories(client, per_page=-1)
    elif kind == "tag":
        response = await tags.get_tags(client, per_page=-1)
    else:
        response = await equipment.get_tools(client, per_page=-1)
    return to_organizer_items(_object(response).get("items"))


async def _create(client: MealieClient, kind: OrganizerKind, name: str) -> JsonObject:
    if kind == "category":
        response = await categories.create_category(client, name)
    elif kind == "tag":
        response = await tags.create_tag(client, name)
    else:
        response = await equipment.create_tool(client, name)
    return _object(response)


def _missing(kind: OrganizerKind, values: list[str]) -> ValueError:
    label = {"category": "categories", "tag": "tags", "tool": "tools"}[kind]
    correction = "tool" if kind == "tool" else label
    pronoun = "it" if len(values) == 1 else "them"
    suffix = " No changes were made to the recipe." if kind == "tool" else ""
    return ValueError(
        f"The following {label} do not exist: {', '.join(values)}. "
        f"Pass createMissing: true to create {pronoun} automatically, "
        f"or correct the {correction} name(s)/slug(s)/ID(s).{suffix}"
    )


async def resolve_collection(
    client: MealieClient,
    kind: OrganizerKind,
    current: list[OrganizerItem],
    full: list[str] | None,
    add: list[str],
    remove: list[str],
    mode: Literal["merge", "replace"],
    create_missing: bool,
    *,
    dry_run: bool = False,
) -> CollectionOutcome:
    all_items = await _catalog(client, kind)

    async def create(name: str) -> JsonObject:
        if dry_run:
            return {"id": f"pending-{name}", "name": name, "slug": name}
        return await _create(client, kind, name)

    if full is not None:
        resolved = await resolve_values(full, all_items, create_missing, create)
        if resolved["missing"]:
            raise _missing(kind, resolved["missing"])
        final = compute_final(mode, current, resolved["resolved"])
        return CollectionOutcome(
            final["final"], final["added"], final["removed"], resolved["created"]
        )

    removals = await resolve_values(remove, all_items, False, create)
    if removals["missing"]:
        label = {"category": "categories", "tag": "tags", "tool": "tools"}[kind]
        correction = "tool" if kind == "tool" else label
        raise ValueError(
            f"Cannot remove {label} that do not exist: {', '.join(removals['missing'])}. "
            "Values passed to remove are never created; "
            f"correct the {correction} name(s)/slug(s)/ID(s). No changes were made to the recipe."
        )
    preview = await resolve_values(add, all_items, False, create)
    removal_ids = {item["id"] for item in removals["resolved"]}
    conflicts = [item for item in preview["resolved"] if item["id"] in removal_ids]
    if conflicts:
        raise ValueError(
            f"The same {kind} appears in both add and remove: "
            + ", ".join(item["name"] for item in conflicts)
            + "."
        )
    if preview["missing"] and not create_missing:
        raise _missing(kind, preview["missing"])
    additions = (
        await resolve_values(add, all_items, True, create) if preview["missing"] else preview
    )
    final = compute_delta(current, additions["resolved"], removals["resolved"])
    return CollectionOutcome(final["final"], final["added"], final["removed"], additions["created"])


def recipe_identity(recipe: JsonObject, slug: str) -> JsonObject:
    stored_slug = recipe.get("slug")
    return {
        "id": to_organizer_item(recipe)["id"],
        "slug": stored_slug if isinstance(stored_slug, str) else slug,
    }


def batch_slugs(updates: list[JsonObject], *, limit: int | None = None) -> None:
    if limit is not None:
        if not updates:
            raise ValueError("At least one recipe update is required.")
        if len(updates) > limit:
            raise ValueError(
                f"At most {limit} recipes are allowed per batch call (got {len(updates)})."
            )
    seen: set[str] = set()
    duplicates: dict[str, None] = {}
    for update in updates:
        raw = update.get("slug")
        slug = trim(raw) if isinstance(raw, str) else ""
        if not isinstance(raw, str) or (limit is not None and not slug):
            raise ValueError("Each update must include a non-empty recipe slug.")
        if slug in seen:
            duplicates[slug] = None
        seen.add(slug)
    if duplicates:
        raise ValueError(
            f"Duplicate recipe slug(s) in the same batch call: {', '.join(duplicates)}. "
            "Each recipe may appear at most once per batch — "
            "submit a second call for a repeat update."
        )
