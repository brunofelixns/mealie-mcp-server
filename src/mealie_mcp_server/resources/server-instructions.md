# Mealie MCP Guidance

This server exposes tools for a Mealie recipe database: recipes, meal plans, shopping lists, categories, tags, foods, units, and tools (equipment). Most tools are deterministic data-management primitives rather than semantic decision-makers — a handful perform their own deterministic name/taxonomy resolution (e.g. `find_recipes_for_ingredients`), but none perform open-ended natural-language interpretation. The architectural principle throughout: **the model interprets; the MCP resolves, persists, and batches.** The sections below cover behavior that spans several tools or requires a semantic judgment call from the calling model; everything else is documented on the individual tools.

## General Tool-Use Principles

- **Semantic interpretation is yours.** Treat these tools as deterministic data-management primitives unless a tool's own description says it performs interpretation itself. A queue, search, or match result is a data lookup, not semantic truth — deciding what it means is still your job.
- **Prefer purpose-built batch tools** (`get_food_matches`/`get_unit_matches`/`get_tool_matches`, `get_recipes_batch`/`get_recipes_detailed_batch`, `update_recipe_taxonomy_batch`, `update_recipe_tools_batch`, `create_shopping_list_items_bulk`, etc.) over repeating an equivalent single-item call, when one fits. Don't force it — a genuinely one-off operation is fine as a single call.
- **Reuse canonical entities.** Search/resolve existing foods, units, categories, tags, and tools before creating new ones (`get_tool_matches` for tools). For entity types that support aliases — foods and units — check those aliases before deciding the concept is missing; don't create a duplicate merely because the source wording differs from the stored name. You decide that a recipe needs a piece of equipment (e.g. a whisk); tool matching and `update_recipe_tools` only find the canonical Tool organizer and persist the assignment.
- **Replacement writes need the full payload.** A tool that replaces a complete collection (e.g. `update_recipe_ingredients`) is not a patch — build the complete intended collection, including unchanged members, or they're silently dropped. Detailed semantics per tool are in that tool's description.
- **Queue/audit classifications are signals, not verdicts.** Read-only queue tools generally report stored/schema state (e.g. ingredient `partial` is a deliberately coarse schema signal) — treat a flagged item as something to look at, not something that automatically needs to change.
- **Respect the requested scope.** Don't perform unrelated cleanup, renaming, normalization, taxonomy changes, or vocabulary edits as a side effect of another task unless they're necessary to complete it correctly.
- **The user's explicit request wins.** Everything here is a default workflow preference, not a constraint on the user. When a request deliberately calls for different behavior or scope and the available tools support it safely, follow the request.

## Recipe Creation and Import

When the user asks to add, create, import, or save a recipe in Mealie — from a URL, pasted text, an image/screenshot, a document, or their own description — aim to create a complete, useful recipe representation from the information the source actually provides, not merely the minimum object the API accepts.

Native import tools delegate URL scraping, HTML/schema.org JSON parsing and ZIP import to Mealie: use import_recipe_from_url, import_recipe_from_html_or_json or import_recipe_from_zip when requested. They create recipes and may import taxonomy according to their flags. After an ambiguous write, inspect before repeating. This server adds no OCR or document/image parser. For manual creation from text, images or documents, extract content using your own capabilities and follow the workflow below.

### What a complete recipe includes

When the source provides them, populate: name, description, source yield/servings, total time, structured ingredients, complete instructions, categories/tags, and an image. **Never invent a value the source doesn't provide just to fill a field** — if the source gives no timing information and none can be reliably derived, leave it out rather than fabricate one. Faithfulness to the source beats completeness by guessing.

### Workflow

1. **Create the recipe with its instructions.** `create_recipe` takes `name` and, optionally, `instructions` (an ordered array of step strings — plain ordered text, no title/summary/ingredient links). Extract the full instruction text and pass it here; later edits, section titles, and ingredient links go through `update_recipe_instructions` (see "Editing Recipe Instructions" below). Preserve step ordering, and preserve meaningful section/group boundaries within the instruction text itself where practical (e.g. a step that reads "For the sauce:"), along with temperatures, durations, and rest/marinade/chill times; don't summarize away a material step or rewrite the recipe's voice unless the user asked for that.
2. **Fill in metadata.** Legacy patch_recipe retains its original arguments. Use update_recipe_metadata with the latest expectedUpdatedAt to edit description, orgURL, servings/yield, totalTime, prepTime, cookTime, performTime, nutrition, settings and extras. Nested objects merge with current state, preserving omitted fields; nutrition:null clears the block. Copy times and nutrition from the source, never invent them or blindly sum overlapping component times. Change privacy or locking only when explicitly requested.
3. **Structure the ingredients per the Ingredient Parsing and Structuring section below** — that policy is the single source of truth for ingredient semantics and is not repeated here. `create_recipe`'s own `ingredients` parameter only stores free-form notes (no food/unit), so a recipe is not complete after that step alone: interpret the source ingredients semantically, resolve food/unit concepts with `get_food_matches`/`get_unit_matches` against existing canonical vocabulary (creating new vocabulary only when nothing suitable exists), and persist the result with `update_recipe_ingredients`.
4. **Apply categories/tags if relevant to the request**, via `patch_recipe` or `update_recipe_taxonomy`: preserve any taxonomy the source already supplies, reuse existing categories/tags, and derive at most a small number of natural classifications — don't turn an import into open-ended taxonomy expansion, and don't treat classification as mandatory when the user didn't ask for it.
5. **Set the image only when you have a real source.** Prefer `set_recipe_image_from_file` when the host provides a file reference for the image (host-dependent), then `set_recipe_image_from_url` when the source gives you a fetchable URL, then `set_recipe_image` with base64 data as the portable fallback (e.g. a user-provided image file). Never substitute an unrelated image, and leave the image unset when you have neither a fetchable URL nor real image data.
6. **Preserve the source URL in orgURL**, using patch_recipe or update_recipe_metadata. Do not put it into description as a workaround when the dedicated field is available.

### Verify after creating or importing

For a normal single-recipe import, once all writes are complete, re-read the recipe with `get_recipe_detailed` when practical and check for obvious omissions: missing ingredient lines or instructions, lost yield/serving data, wrong food/unit associations, dropped preparation notes, a missing image when the source had a usable URL, or accidentally duplicated vocabulary. Don't use this pass as an excuse for unrelated cleanup.

## Recipe Data Enrichment

Choose the work queue by scope. Never silently broaden a specific request into comprehensive cleanup.

1. **Clearly scoped single task: use the focused queue.** Ingredient parsing -> `get_recipes_for_ingredient_parsing`; category/tag classification -> `get_recipes_for_classification`.
2. **Several enrichment dimensions in one pass: use `get_recipes_for_data_enrichment`**, narrowing with `filters` (an explicit `filters` object is the complete active set and is not merged with the defaults; combine with `match: "any" | "all"`).
3. **Broad requests such as "clean up my recipes" or "enrich my recipes": use `get_recipes_for_data_enrichment` with its default filters**, paging with `nextCursor` until `hasMore` is false unless the user narrows scope. Recipes arrive oldest-created first.

Every match is a review signal, not a verdict. Use `matchedDimensions`, the recipe context, and `audit` to decide what actually warrants a change: whether `4 eggs` legitimately has no unit, whether ingredients need sections, which ingredients belong to which steps, whether a recipe needs a given Tool, and whether existing Categories/Tags are right are all your decisions. Preserve correct existing data, and do not perform unrelated enrichment once the user has narrowed scope. Apply changes with the focused write tools (`update_recipe_ingredients`, `update_recipe_instructions`, `update_recipe_tools`, `update_recipe_taxonomy`, their batch forms, and the recipe image tools) — there is no single cleanup mutation. Pass the queue item's `updatedAt` as `expectedUpdatedAt` to guarded writers. Image generation or upload is optional and comparatively expensive; do not treat a missing image as a mandate.

## Ingredient Parsing and Structuring

When structuring, parsing, normalizing, or repairing recipe ingredients — including as part of Recipe Creation and Import above — follow the workflow and policy below. This section does not apply to unrelated tasks — finding a recipe, meal planning, reading a recipe, shopping-list work, or category/tag classification — and should not otherwise influence how you use this server.

### Workflow

1. **Retrieve candidates.** For bulk parsing, start with `get_recipes_for_ingredient_parsing({ state: "unparsed_only" })` and page with the returned cursor until `hasMore` is false. `unparsed_only` (no associated food) is the primary work queue. `partially_parsed` (a food with no unit despite a positive quantity) is an audit queue only — its `partial` state includes plenty of correctly-unitless countables like `4 eggs`, `2 lemons`, `3 tomatoes`, `10 pitas`. Do not assume every `partial` row needs a unit invented for it.
2. **Read the whole recipe context** before restructuring an ambiguous line: all ingredient lines and sections, the instructions, and any existing food/unit/note/referenceId already set. Don't interpret a line in isolation when the instructions resolve the ambiguity — this matters most for compound quantities and ingredients used at multiple stages.
3. **Interpret concepts before resolving IDs.** For each line, decide the intended quantity, unit concept (if any), food concept, preparation/modifier note, alternatives, and whether one source line is actually multiple required ingredients. This is semantic parsing and it is your job — never hand raw ingredient sentences to the match tools.
4. **Resolve vocabulary in batches.** Once concepts are identified, resolve them with `get_food_matches`/`get_unit_matches` (many concepts per call, subject to their 25-query cap) rather than one `get_foods`/`get_units` call per ingredient. These tools return ranked candidates, never a decision — prefer an existing canonical food/unit (including via alias matches) over creating a duplicate; create a new food/unit with the existing CRUD tools only when the concept is clear and nothing suitable already exists, using a clean canonical name and no duplicate synonyms.
5. **Persist the complete collection with `update_recipe_ingredients`.** This replaces the recipe's entire ingredient array — include every row that should remain, not just the ones you changed. Preserve ordering; when one source line is split into several rows, keep them adjacent at that position. Don't touch unrelated recipe metadata.

### Prefer structured representation

Default to aggressive structural parsing. A line with no numeric quantity, a "to taste" note, a garnish, preparation text, alternatives, or more than one food is still worth structuring — free-form rows should be the exception, not the fallback, since Mealie's serving-size scaling depends on parsed quantity/unit/food.

Preserve a meaningful numeric quantity whenever the source supplies one, even if the rest of the line is complicated:

```
"2 green onions, sliced (for garnish)"
  -> quantity: 2, food: green onion, unit: none, note: "sliced; for garnish"
```

Use `quantity: 0` for a real ingredient with no measurable amount rather than inventing a number — `salt to taste`, `pepper to taste`, `cilantro for garnish`, `oil as needed` all take `quantity: 0`.

### Unitless countables

A positive quantity does not imply a unit is required. `4 eggs`, `3 tomatoes`, `2 lemons`, and `10 tortillas` are correctly structured with `unit: none`. Never invent an artificial unit like "piece" just to make `parsingState` read as `structured` — `partial` is a schema-level audit signal on the queue, not an instruction to add a unit.

### Splitting one line into multiple foods

When a line names more than one food that is genuinely required, split it into separate rows and resolve each through `get_food_matches`:

```
"Salt and pepper to taste"
  -> salt      { quantity: 0, note: "to taste" }
  -> pepper    { quantity: 0, note: "to taste" }   // may resolve via alias to canonical "black pepper"
```

`garlic and ginger, minced` splits the same way when both are actually used. Do not split adjectives, preparation phrases, or alternatives as though they were extra required foods.

### Alternatives: preserve semantic ordering

Don't collapse every multi-option ingredient to the same generic treatment — which side of the alternative is primary depends on how the source phrases it.

```
"1 cup shredded cheese (cheddar or mozzarella)"
  -> food: cheese          // the source names the generic concept first
     note: "shredded; cheddar or mozzarella"

"1 cup shredded cheddar cheese (or mozzarella)"
  -> food: cheddar cheese  // the source names cheddar as the primary ingredient
     note: "shredded; or mozzarella"          // do NOT downgrade this to generic cheese
```

General rule: preserve the primary ingredient the source actually names; keep the alternative in `note` unless the source itself is generic. Alternatives are choices, not simultaneous required ingredients — never split `cheddar or mozzarella` into two required rows. Use recipe context when the wording alone is ambiguous.

### Preparation and descriptive text

Keep preparation state, modifiers, and usage detail in `note` rather than folding them into the food name:

```
"3 cloves garlic, minced"        -> food: garlic,   quantity: 3, unit: clove, note: "minced"
"1 small zucchini, sliced"       -> food: zucchini,  quantity: 1, unit: none,  note: "small; sliced"
"fresh basil leaves for garnish" -> food: basil,     quantity: 0, unit: none,  note: "fresh leaves; for garnish"
```

### Compound quantities

A compound quantity like `1/4 cup + 2 tbsp cornstarch` needs the instructions to disambiguate which case applies:

- **One combined amount** — if the instructions show both parts are used together for the same purpose, normalize to a single practical quantity/unit (prefer the smallest unit already present in the source) only when the conversion is exact, well-known, and the result stays readable — e.g. `1/4 cup + 2 tbsp cornstarch` -> `6 tablespoons cornstarch`. Don't perform speculative or approximate conversions just to force one quantity. Preserve the original wording in `originalText`.
- **Separate uses** — if the instructions show the parts serve distinct purposes (e.g. `3 cups + 2 tbsp bread flour` where 3 cups go into the dough and 2 tbsp is for dusting later), keep them as two rows, each with a `note` describing its purpose.

### Quantity expressed through a source item

Don't invent a measured volume when the source expresses quantity through a countable item instead: `"Juice of 1 lemon"` is generally `quantity: 1, food: lemon, unit: none, note: "juiced"`, not a fabricated volume of lemon juice.

### Packages and secondary sizes

Distinguish the primary quantity/unit the recipe actually asks for from secondary package-size information: `"1 can (15 oz) black beans, drained and rinsed"` is generally `quantity: 1, unit: can, food: black beans, note: "15 oz; drained and rinsed"` — don't represent both `1 can` and `15 oz` as simultaneous quantities unless the instructions show only part of the container is actually used.

### Named prepared components

A named prepared component (e.g. "jeow king", "pesto", "curry paste", "chili crisp") normally stays one ingredient concept — resolve it as a food if a suitable canonical one exists, and don't explode it into its own constituent ingredients unless the source line itself defines them. If it can't be faithfully represented with the current model, preserve meaning conservatively rather than inventing ingredients.

### Provenance: `originalText`, `display`, and `referenceId`

- **`originalText`** — for a one-to-one restructure, keep an existing non-null `originalText` unchanged; if it's null but the original free-form line is clearly present in `note` or `display`, carry that source text into `originalText` when rewriting. Never replace `originalText` with Mealie's recomputed display string. For a one-to-many split, retain provenance to the original line on the resulting rows where appropriate.
- **`display`** — Mealie recomputes this from `quantity`/`unit`/`food`/`note` on read, so it never round-trips literally. Get the structured fields right; don't distort them chasing a particular display string.
- **`referenceId`** — existing IDs matter because recipe instructions may reference them via `ingredientReferences`. One-to-one: preserve the row's existing `referenceId`. One-to-many split: keep the original `referenceId` on the primary/first resulting row; give additional rows unique new IDs, preferably by omitting `referenceId` and letting Mealie assign one rather than fabricating or reusing the old ID. Before splitting a referenced row, check the recipe's existing `ingredientReferences` — this ingredient-only workflow cannot redistribute those references across newly split rows, so for an already-linked compound ingredient, prefer preserving the existing structure conservatively over silently breaking that link. Instruction-to-ingredient reference rewriting is done with `update_recipe_instructions`, not by this ingredient workflow.

`recipeInstructions[].id` is not stable identity — Mealie regenerates it on every recipe update, including via `update_recipe_ingredients`. Use instruction `title`/`text`/`ingredientReferences` for context, never the instruction `id`.

### Leave already-correct rows alone

When a recipe mixes structured and unparsed ingredients, preserve the already-correct rows — quantity, unit, food, note, referenceId — unchanged, and only touch them when context reveals an actual error or the user's request requires it. With a full-replacement `ingredients` write, unchanged rows must still be included in the payload; with the referenceId-based delta fields (do not combine them with `ingredients`), leave unchanged rows out entirely.

### Candidate selection and missing vocabulary

Ranked candidates from `get_food_matches`/`get_unit_matches` are a shortlist, not an answer: prefer an exact canonical match, accept an alias match that clearly represents the intended concept (e.g. `"som moo"` matching canonical `fermented pork` through the stored alias `cured pork (som moo)` — don't create a duplicate food in that case), and inspect substring candidates rather than reflexively taking the first result. Avoid substituting a merely-related food. When nothing suitable exists, create conservatively: a clean, reusable canonical name, no recipe-specific phrasing, no entity for a preparation note, and no alias edits as an unrelated side effect unless clearly justified.

### Validate after writing

After restructuring a recipe, re-read it with `get_recipe_detailed` when practical and check that: every intended ingredient is present and correctly ordered; quantities, units, and foods are correct; notes retain modifiers/alternatives; referenceIds for continuing rows survived and split rows got unique new ones; `originalText` provenance was preserved; and no unrelated recipe metadata changed. Don't assume the `display` you sent will come back literally. On a large bulk-parsing job, use judgment about how often to re-read — a `get_recipe_detailed` call after every single recipe can dominate the job's cost; spot-check instead of verifying every recipe individually when the volume is high.

### Efficiency at scale

Parsing may span hundreds of recipes. Per recipe or small group: interpret concepts first, collect the food and unit concepts across the group, resolve them with one batched `get_food_matches` call and one batched `get_unit_matches` call (mind the 25-query cap), then write with `update_recipe_ingredients`. Avoid one lookup call per ingredient when a batch call can answer several at once.

## Editing Recipe Instructions

When the user asks to edit, add, remove, reorder, section, or link instructions to ingredients on an existing recipe, use `update_recipe_instructions` (or `update_recipe_instructions_batch` for several recipes). Instruction `id`s are ephemeral (regenerated on every recipe write) and are never valid edit identities — do not save or send them.

1. Call `get_recipe_detailed` first and pass that read's exact `updatedAt` as `expectedUpdatedAt`, unchanged. Instruction indexes are zero-based positions in that same snapshot. `expectedUpdatedAt` is a stale-snapshot guard: if the recipe has already changed when the tool reads it for mutation, the call fails before writing — re-read and retry. Mealie has no conditional recipe writes, so a concurrent edit between that validation read and the PATCH cannot be detected.
2. Use the delta form (`addInstructions`/`updateInstructions`/`removeInstructionIndexes`) for focused edits; use complete replacement (`instructions`) for a substantial rebuild or reordering. The two cannot be mixed.
3. Link instructions to ingredients with `ingredientReferenceIds` taken from the recipe's `recipeIngredient[].referenceId`. Which ingredients belong to which step, and the wording and sectioning, are your decisions — the MCP never infers them. Unknown ids are rejected before any write.
4. Changes that leave instructions identical skip the write. Writes are verified by content and rolled back on mismatch; the result reports whether rollback succeeded.

## Additional Recipe Operations

get_recipe_notes reads notes and a fresh updatedAt. add_recipe_note appends; update_recipe_note edits title/text by stable referenceId; delete_recipe_note deletes that identity. All writes require expectedUpdatedAt. Recipe notes differ from ingredient note fields and user comments. Deleting a linked note requires explicit removeReferences:true. On stale snapshots, re-read and reassess without automatic replay.

Use get_recipe_comments/create_recipe_comment/update_recipe_comment/delete_recipe_comment for user comments; Mealie enforces ownership. get_recipe_share_links/create_recipe_share_link/delete_recipe_share_link manage shared access: create or reveal tokens only for an explicit sharing request, never as a cleanup side effect. Timeline tools list/create/update/delete events and upload event images; the provider controls editability.

upload_recipe_asset and create_recipe_asset_from_url add attachments, available in get_recipe_detailed. get_recipe_export_formats discovers formats; export_recipe returns bounded dataBase64, filename and mediaType without writing host files. Native imports are additional options alongside manual creation. Never log recipe/file contents, credentials or signed URLs.

## Mealie 3.30 Recipe Capabilities

Use search_recipes for native advanced filters/order/queryFilter and get_recipe_suggestions for missing-food/tool, stock and substitution options. Legacy get_recipes/find_recipes_for_ingredients retain their original contracts.

Substitution edits use update_recipe_ingredient_substitutions or update_food_substitutions with explicit canonical food IDs or meaningful text-only alternatives; never invent or create a food to fill an ID. update_recipe_instruction_durations sets or clears durationSeconds by fresh snapshot index; do not use ephemeral instruction IDs. Preserve unrelated content and refresh after stale or ambiguous writes.

Native parse_recipe_ingredient/parse_recipe_ingredients and AI imports are explicit optional interpretation paths delegated to Mealie; they do not authorize silently applying their output to existing recipes. Existing client interpretation remains available. Native AI imports use Mealie's provider configuration, not a local API key.

Recipe media downloads return bounded base64 data without writing host files or accepting arbitrary URLs. Share and iCal tokens are sensitive. Bulk imports/exports/actions may be asynchronous: accepted is not completed. Report per-item failures, propagate unknown write outcomes and never automatically replay an import, trigger or other write. External recipe actions and token rotations only run on an explicit request.

Cookbook CRUD, current-household last-made data via get_recipe_household, personal favorites/ratings reads, single comment/event/share reads and advanced meal plans are available as separate tools. Advanced meal plans support text, positive recipeScale and weekly endDate exactly six days after date. Keep the scope of the user's request; do not turn recipe editing into provider or account administration.
