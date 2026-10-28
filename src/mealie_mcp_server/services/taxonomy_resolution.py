"""Read-only taxonomy filters use ID, then name, then slug priority."""

from typing import Literal, TypedDict

from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.organizer_resolution import OrganizerItem, to_organizer_items
from mealie_mcp_server.support.strings import trim

type TaxonomyKind = Literal["category", "tag"]


class TaxonomyResolution(TypedDict):
    resolved: list[OrganizerItem]
    unresolved: list[str]


class UnresolvedTaxonomyFilterError(ValueError):
    def __init__(self, kind: TaxonomyKind, values: list[str]) -> None:
        self.kind, self.values = kind, values
        label = "categories" if kind == "category" else "tags"
        pronoun = "it" if len(values) == 1 else "them"
        super().__init__(
            f"The following {label} do not exist: {', '.join(values)}. "
            f"Correct the {label} name(s)/slug(s)/ID(s), or remove {pronoun} from the filter."
        )


async def resolve_taxonomy_values(
    client: MealieClient, kind: TaxonomyKind, values: list[str]
) -> TaxonomyResolution:
    path = "/api/organizers/" + ("categories" if kind == "category" else "tags")
    response = await client.request("GET", path, params=[("perPage", "-1")])
    if not isinstance(response, dict):
        raise ValueError("Invalid Mealie organizer response.")
    existing = to_organizer_items(response.get("items"))
    by_id = {item["id"].lower(): item for item in existing}
    by_name = {item["name"].lower(): item for item in existing}
    by_slug = {item["slug"].lower(): item for item in existing}
    resolved: dict[str, OrganizerItem] = {}
    unresolved: list[str] = []
    for raw in values:
        value = trim(raw)
        if not value:
            continue
        key = value.lower()
        match = by_id.get(key) or by_name.get(key) or by_slug.get(key)
        if match is None:
            unresolved.append(raw)
        else:
            resolved[match["id"]] = match
    return {"resolved": list(resolved.values()), "unresolved": unresolved}


async def resolve_taxonomy_filter(
    client: MealieClient, kind: TaxonomyKind, values: list[str] | None
) -> list[str] | None:
    if not values:
        return values
    result = await resolve_taxonomy_values(client, kind, values)
    if result["unresolved"]:
        raise UnresolvedTaxonomyFilterError(kind, result["unresolved"])
    return [item["id"] for item in result["resolved"]]
