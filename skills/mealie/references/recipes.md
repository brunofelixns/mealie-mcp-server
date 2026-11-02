# Recipe maintenance

## Discover and inspect

Use `get_recipes` for search, `get_recipe_concise` for a compact view, and
`get_recipes_batch` when several slugs are already known. For edits, read the
current recipe with `get_recipe_detailed` or the appropriate detailed batch tool.
Keep IDs and timestamps from that current response.

The classification, enrichment, and ingredient-parsing queues report stored
state. A `partial` ingredient is a candidate for inspection, not proof that it is
wrong. For example, «4 huevos» can correctly have quantity 4 and no unit.

## Import or create

Extract the recipe from the source using the client's own reading capabilities;
this MCP does not scrape websites or perform OCR. Preserve the source's ingredient
lines, quantities, instructions, order, and meaningful sections. Do not invent
servings, times, nutrition, or unit conversions.

Use `create_recipe` for the name and ordered instruction text, then the focused
tools for metadata, ingredients, taxonomy, equipment, or images as needed. Do not
create a duplicate after an ambiguous response: search and inspect first.

## Structure ingredients and edit instructions

Resolve existing foods and units with `get_food_matches` and `get_unit_matches`,
including aliases, before proposing new vocabulary. Interpret the ingredient
yourself: matching is a lookup, not a parser. Preserve preparation and alternatives
in notes. «Sal al gusto» has no invented measurable quantity; «cheddar o mozzarella»
is a choice, not two required ingredients. Follow the server's ingredient policy
for the representation of these cases.

For `update_recipe_ingredients`, distinguish full replacement from delta fields.
A replacement must include every ingredient that should remain. Preserve stored
`referenceId` values for continuing rows and refresh the recipe after writing.

`update_recipe_instructions` requires the current `expectedUpdatedAt`. Indexes
refer to the fresh snapshot; instruction IDs can be regenerated. Ingredient links
must use durably stored ingredient reference IDs. If the tool reports legacy
unpinned ingredients, follow its pinning guidance, then re-read the recipe before
editing instructions. Never infer links just to fill the field.

For a stale snapshot, re-read and reassess the intended edit rather than replaying
it with an invented or previously cached timestamp. If a write fails verification,
report whether rollback succeeded and inspect the current state before recovery.

## Organize

Use `update_recipe_taxonomy` and `update_recipe_tools` (or their batch forms) for
categories/tags and equipment. Resolve existing vocabulary first. Choose merge,
replacement, removal, or creation only according to the user's request and the
tool schema; do not normalize unrelated recipes or create missing terms silently.
