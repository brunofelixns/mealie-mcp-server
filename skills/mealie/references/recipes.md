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

Use native `import_recipe_from_url`, `import_recipe_from_html_or_json` or
`import_recipe_from_zip` when requested; these delegate parsing to Mealie and
create recipes. After an ambiguous response, inspect before importing again.
For manual creation, extract using the client's reading capabilities; the MCP
adds no OCR. Preserve the source's ingredient
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

## Notes, metadata and files

Recipe notes differ from ingredient notes and user comments. Read
`get_recipe_notes`, then use `add_recipe_note`, `update_recipe_note` or
`delete_recipe_note` with fresh `expectedUpdatedAt`. Edit/delete by stable
`referenceId`; deleting linked notes requires explicit `removeReferences:true`.
Preserve unselected notes; re-read after a stale or ambiguous write.

Use `update_recipe_metadata` for prep/cook/perform time, `orgURL`, nutrition,
settings and extras. Nested objects merge and omitted fields stay intact.
`nutrition:null` clears the block. Do not invent nutritional values or change
privacy/locking without a request. The snapshot check is not atomic.

Comments, shared links and timeline events have dedicated tools. Shared tokens
grant access: create/reveal them only when requested. Add attachments with
`upload_recipe_asset` or `create_recipe_asset_from_url`. Discover formats with
`get_recipe_export_formats`; `export_recipe` returns bounded base64 data without
writing host files. Do not log file contents, credentials or signed URLs.

## Mealie 3.30

Prefer `search_recipes` for advanced native filters/order/queryFilter and
`get_recipe_suggestions` for stock, missing foods/tools and substitution options.
Use explicit canonical IDs or meaningful text-only alternatives with
`update_recipe_ingredient_substitutions` and `update_food_substitutions`.
`update_recipe_instruction_durations` edits timers
by fresh snapshot index, accepts positive whole seconds or null to clear, and
preserves other instruction content.

Native ingredient parsing is optional and read-only for Mealie data; an OpenAI
parser can call the provider configured in Mealie. Review parsed data before
applying it. AI imports also use Mealie's configuration, never a local key.
Progress/bulk imports must not be replayed after an ambiguous failure. Inspect
their returned job/report instead; accepted does not mean every item succeeded.

Media downloads, cookbook CRUD, favorites/ratings reads, shared recipe/token
reads and advanced meal plans are available through dedicated tools. Weekly
entries use endDate six days after date; recipeScale is positive. Rotate share
or iCal tokens and trigger external recipe actions only when explicitly requested.
Use `get_recipe_household` to read the current household's lastMade; preserve null
and do not infer this date from the recipe's general metadata.
