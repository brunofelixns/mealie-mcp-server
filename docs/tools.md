# Referencia MCP

Generada desde resources/tool-catalog.json, el contrato público usado por el servidor. Se conservan nombres camelCase, obligatoriedad, annotations y metadata declaradas. No se añaden outputSchema ni structuredContent. El prompt weekly-meal-plan acepta preferences opcional.

## get_recipes

Searches and lists recipes with pagination. Categories and tags are resolved by name/slug/ID against Mealie's organizer endpoints before the request, since Mealie's query params only match by exact slug/ID.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "search": {
      "type": "string"
    },
    "page": {
      "type": "number"
    },
    "perPage": {
      "type": "number"
    },
    "categories": {
      "description": "Each given as a name, slug, or ID (matched case-insensitively by name/slug).",
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "tags": {
      "description": "Each given as a name, slug, or ID (matched case-insensitively by name/slug).",
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "requireAllTags": {
      "type": "boolean"
    },
    "requireAllCategories": {
      "type": "boolean"
    }
  },
  "additionalProperties": false
}
```

## find_recipes_for_ingredients

Finds recipes that contain one or more requested ingredients. Ingredient names are resolved against Mealie's food taxonomy internally — never pass Mealie food UUIDs, just human-readable names like "branzino" or "chicken thighs". Use this for exact or approximate ingredient-based recipe discovery, e.g. deciding what to cook with an ingredient on hand. If an ingredient has no useful matches (see resolvedIngredients/unresolvedIngredients/matchSource in the response), the MCP will not guess a substitute on your behalf — retry this same tool with broader or substitutable ingredient terms you choose (e.g. "branzino" with no matches -> retry with "sea bass", "whole fish", or "snapper"), then use get_recipe_detailed or get_recipes_batch to inspect the most promising candidates.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "ingredients": {
      "minItems": 1,
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "One or more human-readable ingredient names (e.g. \"branzino\", \"chicken thighs\"). Never Mealie food UUIDs — this tool resolves names against Mealie's food taxonomy internally."
    },
    "categories": {
      "description": "Optional category filter, same name/slug/ID matching convention as get_recipes.",
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "tags": {
      "description": "Optional tag filter, same name/slug/ID matching convention as get_recipes.",
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "requireAllIngredients": {
      "description": "When true, only return recipes containing every resolved ingredient (AND). Default false returns recipes containing any one of them, ranked by how many they contain and how few other ingredients they are missing (Mealie's Recipe Finder behavior).",
      "type": "boolean"
    },
    "requireAllCategories": {
      "description": "Require every given category, not just one.",
      "type": "boolean"
    },
    "requireAllTags": {
      "description": "Require every given tag, not just one.",
      "type": "boolean"
    },
    "limit": {
      "description": "Max recipes to return, default 10, capped at 50.",
      "type": "number"
    }
  },
  "required": [
    "ingredients"
  ],
  "additionalProperties": false
}
```

## get_recipe_detailed

Retrieves a recipe by slug with full details including nutrition, settings, and assets.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string"
    }
  },
  "required": [
    "slug"
  ],
  "additionalProperties": false
}
```

## get_recipe_concise

Retrieves a recipe by slug, filtered to summary fields (name, slug, servings, yield, total time, rating, ingredients, last made).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string"
    }
  },
  "required": [
    "slug"
  ],
  "additionalProperties": false
}
```

## get_recipes_batch

Fetches multiple recipes by slug with bounded concurrency (4 in-flight requests at a time).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slugs": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "slugs"
  ],
  "additionalProperties": false
}
```

## get_recipes_detailed_batch

Fetches multiple recipes by slug with full details (including nutrition) and bounded concurrency.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slugs": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Recipe slugs to fetch in parallel"
    }
  },
  "required": [
    "slugs"
  ],
  "additionalProperties": false
}
```

## get_recipes_for_classification

Compact, paginated, READ-ONLY feed of recipes for assigning Categories and Tags. Returns only the fields useful for classification (name, description, times, servings, source URL, ingredients, instructions) plus each recipe's EXISTING categories and tags — include and preserve those when classifying; do not drop or overwrite them. By default only recipes missing at least one taxonomy collection are returned (taxonomyState "missing_either"); use "missing_both", "missing_categories", "missing_tags", or "any" to change that. Pass the response's nextCursor back unchanged as the next call's cursor to continue; stop once hasMore is false. Pagination is stable against concurrent taxonomy edits — a recipe that gains categories/tags between calls will not cause other recipes to be skipped. A failure reading one recipe is reported in failures and does not fail the rest of the page. This tool never creates or modifies anything — it does not assign taxonomy, create categories/tags, or change any recipe. To apply classifications, call update_recipe_taxonomy_batch separately (preferably in batches of about five recipes), normally with mode "merge" and createMissing: false unless the user explicitly asks to replace collections or auto-create new categories/tags.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "cursor": {
      "description": "Opaque continuation token from a previous call's nextCursor. Pass it back unchanged to resume exactly where that call left off; omit it to start from the beginning of the collection. Do not construct or edit this value — malformed or foreign cursors are rejected with a clear error.",
      "type": "string"
    },
    "limit": {
      "description": "Maximum recipes to return (1-50, default 25).",
      "type": "integer",
      "minimum": 1,
      "maximum": 50
    },
    "taxonomyState": {
      "description": "Which recipes to include, based on their existing Categories/Tags (default \"missing_either\"): \"missing_either\" — category list empty, tag list empty, or both; \"missing_both\" — both empty; \"missing_categories\" — category list empty regardless of tags; \"missing_tags\" — tag list empty regardless of categories; \"any\" — no taxonomy filtering.",
      "type": "string",
      "enum": [
        "missing_either",
        "missing_both",
        "missing_categories",
        "missing_tags",
        "any"
      ]
    }
  },
  "additionalProperties": false
}
```

## get_recipes_for_ingredient_parsing

Compact, paginated, READ-ONLY work queue of recipes whose ingredients may need structured parsing. This tool identifies candidate recipes using only their EXISTING stored schema state — it never parses or interprets ingredient language itself: it does not call Mealie's NLP ingredient parser, does not guess a food/unit association, and never modifies any recipe, food, unit, alias, or ingredient. It returns each ingredient's current stored state (quantity, unit id/name, food id/name, note, display, originalText, title, referenceId) plus recipe instructions (title, text, ingredientReferences) as context — turning that into structured data (e.g. "2 tablespoons chopped fresh parsley leaves" -> quantity 2, unit tablespoon, food parsley, note "chopped fresh") is entirely the calling model's job. Instructions are included because they can disambiguate an otherwise-ambiguous ingredient line or reveal how a compound quantity is actually used (e.g. whether "3 cups + 2 tbsp flour" is one combined amount or two separate uses) — this tool does not decide that, it only supplies the text. Each ingredient includes a deterministic, schema-only "parsingState": "section" (a pure Mealie ingredient-section heading: a non-empty title with no food, unit, positive quantity, note, display, or originalText other than the title itself — never counted as needing parsing; a title on a row that also carries an ingredient payload does NOT make it a section and the row is classified by its own state), "unparsed" (no food is associated — the primary, high-confidence signal), "partial" (a food is associated but no unit, while quantity is a positive number — NOTE: this also matches legitimately unit-less countable foods like "4 eggs" or "2 lemons", since Mealie's schema has no field distinguishing that from an incompletely-structured row; treat "partial" as a coarse audit signal, not a confirmed defect), or "structured" (fully resolved, or has no meaningful quantity to need a unit). Each recipe also includes an ingredientParsingState summary (unparsedCount/partialCount/structuredCount/sectionCount/totalCount); sectionCount independently counts every row with a non-empty title, so a titled real ingredient counts in both its parsing count and sectionCount and the counts need not sum to totalCount. Use "state" to choose the queue: "unparsed_only" (default) — recipes with at least one unparsed ingredient; "partially_parsed" — recipes with at least one partial ingredient; "any" — every scanned recipe, for auditing. Every scanned recipe needs a full detail fetch (Mealie's recipe list endpoint does not expose ingredients), fetched with bounded concurrency in small batches — a failure reading one recipe is reported in failures and does not fail the rest of the page. Because of that per-recipe fetch cost, a sparse queue may need to scan far more recipes than it returns to fill a page; returnedCount can come in below the requested limit even when hasMore is true, if an internal time budget is reached first — this is expected, not an error, and the response is still safe to use as-is. Pass the response's nextCursor back unchanged as the next call's cursor to continue; stop once hasMore is false. Pagination is stable against concurrent recipe edits, the same way get_recipes_for_classification is. When you later write changes: use get_food_matches and get_unit_matches to find existing canonical food/unit candidates for the concepts you interpreted (this tool never looks them up or creates them itself), then call update_recipe_ingredients with the complete, corrected ingredient collection for that recipe. Existing referenceIds are stable identifiers for ingredient rows and may be referenced by recipe instructions — preserve them when an existing ingredient row continues to represent the same ingredient. Recipe instruction ids returned here are NOT stable — Mealie recreates recipeInstructions (and assigns fresh ids) on every recipe update, including update_recipe_ingredients — do not depend on an instruction id read here still being valid after a write.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "cursor": {
      "description": "Opaque continuation token from a previous call's nextCursor. Pass it back unchanged to resume exactly where that call left off; omit it to start from the beginning of the collection. Do not construct or edit this value — malformed or foreign cursors are rejected with a clear error.",
      "type": "string"
    },
    "limit": {
      "description": "Maximum recipes to return (1-50, default 25).",
      "type": "integer",
      "minimum": 1,
      "maximum": 50
    },
    "state": {
      "description": "Which recipes to include (default \"unparsed_only\"): \"unparsed_only\" — at least one non-section ingredient has no associated food (pure section headings are excluded); \"partially_parsed\" — at least one ingredient has a food but no unit despite a positive quantity (coarse signal, see tool description for its known false-positive tradeoff); \"any\" — no filtering, every scanned recipe is returned (useful for auditing).",
      "type": "string",
      "enum": [
        "unparsed_only",
        "partially_parsed",
        "any"
      ]
    }
  },
  "additionalProperties": false
}
```

## get_recipes_for_data_enrichment

Compact, paginated, READ-ONLY holistic work queue of recipes that match deterministic enrichment-review conditions across several dimensions at once: ingredient parsing, ingredient section headings, instruction-to-ingredient links, Tools, Categories, Tags, and image. It reports stored-schema facts and filters on them; it never decides what should change. A match is a review signal, NOT a verdict — e.g. "4 eggs" legitimately has no unit, a recipe may not need sections or equipment, and existing Categories/Tags may already be correct. Use matchedDimensions, the recipe context, and the audit counts to decide what actually warrants a change, preserve correct existing data, and apply changes with the focused write tools (update_recipe_ingredients, update_recipe_instructions, update_recipe_tools, update_recipe_taxonomy and their batch forms, and the recipe image tools). When to use it: for a clearly scoped single task prefer the focused queue (get_recipes_for_ingredient_parsing, get_recipes_for_classification); use this queue for several enrichment dimensions in one pass or for broad "clean up / enrich my recipes" requests with its default filters, paging until hasMore is false unless the user narrows scope. Never broaden a specific request into comprehensive cleanup. Filters: ingredientParsing ("unparsed" = some non-heading ingredient has no food — pure section headings excluded; "partial" = some ingredient has a food and positive quantity but no unit — coarse signal; "unparsed_or_partial"), ingredientSections (true = has section headings; false = has ingredients but no section headings — recipes with zero ingredients never match false), instructionIngredientLinks ("missing" = has instructions but none reference an ingredient; "dangling" = an instruction reference matches no current ingredient referenceId; "missing_or_dangling"), tools / categories / tags / image (true = present, false = absent). If filters is omitted, the defaults are ingredientParsing "unparsed_or_partial", ingredientSections false, instructionIngredientLinks "missing_or_dangling", tools false, categories false, tags false, image false. If filters is provided it is the COMPLETE active set — it is not merged with the defaults — and an empty filters object is rejected. match "any" (default) returns recipes matching at least one active filter; "all" requires every active filter. Recipes are scanned oldest-created first (createdAt, then id). Each item includes createdAt and updatedAt (use updatedAt as expectedUpdatedAt for guarded writers), ingredients with parsingState, instructions with ingredientReferenceIds, tools, categories, tags, the audit facts, and matchedDimensions (the active dimensions this recipe matched). Instruction ids are not exposed and are not stable identity — Mealie regenerates them on every recipe update. Every scanned recipe needs a full detail fetch (bounded concurrency); a failure reading one recipe is reported in failures without failing the page. A sparse queue may return fewer than limit items while hasMore is true if the internal time budget is reached — this is expected. Pass nextCursor back unchanged to continue; stop once hasMore is false.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "cursor": {
      "description": "Opaque continuation token from a previous call's nextCursor. Pass it back unchanged; omit it to start from the oldest recipe. Malformed or foreign cursors are rejected with a clear error.",
      "type": "string"
    },
    "limit": {
      "description": "Maximum recipes to return (1-50, default 25).",
      "type": "integer",
      "minimum": 1,
      "maximum": 50
    },
    "match": {
      "description": "How active filters combine: \"any\" (default) = at least one matches; \"all\" = every active filter matches.",
      "type": "string",
      "enum": [
        "any",
        "all"
      ]
    },
    "filters": {
      "description": "Complete active filter set (replaces the defaults; must contain at least one key). Booleans: true = present, false = absent. Omit to use the default enrichment filters.",
      "type": "object",
      "properties": {
        "ingredientParsing": {
          "type": "string",
          "enum": [
            "unparsed",
            "partial",
            "unparsed_or_partial"
          ]
        },
        "ingredientSections": {
          "type": "boolean"
        },
        "instructionIngredientLinks": {
          "type": "string",
          "enum": [
            "missing",
            "dangling",
            "missing_or_dangling"
          ]
        },
        "tools": {
          "type": "boolean"
        },
        "categories": {
          "type": "boolean"
        },
        "tags": {
          "type": "boolean"
        },
        "image": {
          "type": "boolean"
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

## create_recipe

Creates a new recipe. Optionally sets ingredients and instructions on creation.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "name": {
      "type": "string"
    },
    "ingredients": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "instructions": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

## patch_recipe

Partially updates a recipe. Optional categories/tags/taxonomyMode/createMissing assign taxonomy; unchanged Category/Tag collections are never written and, if taxonomy is the only thing requested and nothing changes, no PATCH is issued and the current recipe is returned with taxonomyChanges. Optional instructions is the complete new list of steps (not a patch): it replaces all steps, [] clears them, omitting it leaves them unchanged.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string"
    },
    "name": {
      "type": "string"
    },
    "description": {
      "type": "string"
    },
    "recipeYield": {
      "type": "string"
    },
    "totalTime": {
      "type": "string"
    },
    "recipeServings": {
      "type": "number"
    },
    "recipeYieldQuantity": {
      "type": "number"
    },
    "orgURL": {
      "type": "string"
    },
    "categories": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Categories to assign, each given as a name, slug, or ID (matched case-insensitively by name/slug). Categories are broad groupings (e.g. \"Dinner\", \"Dessert\") as opposed to Tags, which are more specific attributes (e.g. \"Quick\", \"Dairy-Free\"). Omit this field to leave the recipe's categories unchanged. Passing an empty array with mode \"replace\" clears all categories from the recipe — use with care."
    },
    "tags": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Tags to assign, each given as a name, slug, or ID (matched case-insensitively by name/slug). Tags are specific, free-form attributes (e.g. \"Quick\", \"Dairy-Free\") as opposed to Categories, which are broad groupings (e.g. \"Dinner\", \"Dessert\"). Omit this field to leave the recipe's tags unchanged. Passing an empty array with mode \"replace\" clears all tags from the recipe — use with care."
    },
    "taxonomyMode": {
      "type": "string",
      "enum": [
        "merge",
        "replace"
      ],
      "description": "merge (default) adds the given categories/tags to whatever the recipe already has. replace overwrites the corresponding collection with exactly the given list — an empty array in replace mode clears that collection entirely."
    },
    "createMissing": {
      "type": "boolean",
      "description": "When true, any named category/tag that does not already exist in Mealie is created automatically. When false (default), unknown names cause the call to fail with an error listing the unresolved values."
    },
    "instructions": {
      "description": "Complete new list of steps, in order. Replaces all steps; [] clears them.",
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "slug"
  ],
  "additionalProperties": false
}
```

## update_recipe_ingredients

Replaces the complete structured ingredient collection (recipeIngredient) of an existing recipe, leaving every other recipe field untouched (name, description, categories, tags, settings, nutrition, etc.). Known Mealie limitation, not caused by this tool: every recipe instruction's ID is regenerated on any recipe update (PATCH or PUT), including this one — instruction text/title/summary/ingredient-references are preserved correctly, only the IDs change. Low-level write primitive: it does not parse ingredient text and does not look up or create foods/units — foodId/unitId must already reference existing Mealie entities, resolved first with get_food_matches/get_unit_matches (batch, alias-aware lookup for several already-interpreted concepts at once — the normal path after parsing ingredient text) or get_foods/get_food/get_units/get_unit for a single manual lookup. The ingredients array is the recipe's complete new ingredient list, not a patch: any ingredient not included is removed, and an empty array clears all ingredients. Call get_recipe_detailed first to see the recipe's current ingredients, referenceIds, and other fields before replacing them. Note: each ingredient's "display" field is never actually persisted by Mealie — it is always recomputed from quantity/unit/food/note, regardless of what is supplied here. Integrity check: after writing, the recipe Mealie returns is verified — for every ingredient that supplied a foodId/unitId, the persisted food/unit must still be non-null, match the given id, and match the given name (case-insensitive against name/pluralName, plus abbreviation/pluralAbbreviation for units). If verification fails (e.g. a nonexistent or mismatched foodId/unitId that Mealie silently dropped or resolved to the wrong entity), the recipe is restored to its pre-write state on a best-effort basis and this call reports failure — never a silent partial write. Referenced recipes: a row may carry referencedRecipeId (an existing recipe's id) instead of a food/unit to use that recipe as a sub-recipe; every referenced id is read first (an unknown id fails the call and nothing is written), and after the write the persisted referencedRecipe must be non-null with the same id or the recipe is restored like any other verification failure. Verification adds no extra request on success beyond one GET per distinct referenced recipe; a failed write adds one rollback request. Alternatively, use the delta form (addIngredients/updateIngredients/removeIngredientReferenceIds, instead of ingredients) to edit rows incrementally by stable referenceId: retained rows keep their order, updates edit in place, additions are appended or anchored with insertAfterReferenceId/insertBeforeReferenceId, and ingredient sections are just rows with a "title". The delta is applied to the recipe's current ingredients, the complete final collection is built, and the same verified write and rollback is used. Duplicate, unknown, or conflicting operations are rejected before any write. Note Mealie generates a fresh referenceId on every read for rows that never had one stored, so such a row may not be addressable by an id from an earlier read — use the complete-replacement form for it.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string",
      "description": "Slug of the recipe to update."
    },
    "ingredients": {
      "description": "Replacement form: complete desired ingredient collection, in order — replaces the recipe's entire recipeIngredient list. Pass every ingredient that should remain, not just the ones changing. An empty array clears all ingredients. Cannot be combined with the delta fields.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "quantity": {
            "description": "Numeric amount, e.g. 2. 0 is a valid explicit value; omit to use Mealie's default (0).",
            "type": [
              "number",
              "null"
            ]
          },
          "unitId": {
            "description": "UUID of an existing unit. Must be given together with unitName — never alone.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          },
          "unitName": {
            "description": "Human-readable name of the unit identified by unitId. Required whenever unitId is given.",
            "type": "string"
          },
          "foodId": {
            "description": "UUID of an existing food (see get_food_matches for resolving multiple already-interpreted concepts at once, or get_foods/get_food for a single manual lookup). Must be given together with foodName — never alone. This tool never looks up or creates foods; resolve the food first.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          },
          "foodName": {
            "description": "Human-readable name of the food identified by foodId. Required whenever foodId is given.",
            "type": "string"
          },
          "note": {
            "description": "Free-text note for this ingredient line.",
            "type": [
              "string",
              "null"
            ]
          },
          "display": {
            "description": "Fully composed display string, e.g. \"2 tablespoons olive oil\". Mealie does not persist this field — it always recomputes its own display string from quantity/unit/food/note when the ingredient is read, so do not rely on this value round-tripping literally.",
            "type": "string"
          },
          "originalText": {
            "description": "The original, unparsed ingredient text, if any.",
            "type": [
              "string",
              "null"
            ]
          },
          "title": {
            "description": "Section heading for this ingredient line (e.g. \"For the sauce\"); omit or use null for a normal ingredient.",
            "type": [
              "string",
              "null"
            ]
          },
          "referenceId": {
            "description": "Stable UUID for this ingredient line. Recipe instructions can reference ingredients by this ID — pass back the value from a prior get_recipe_detailed to preserve those links; omit to let Mealie assign a new one.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          },
          "referencedRecipeId": {
            "description": "UUID (the recipe's \"id\", stable across renames — not its slug) of an existing recipe to use as a sub-recipe on this line, e.g. a sauce or spice mix. Read it back as referencedRecipe in get_recipe_detailed. Cannot be combined with foodId/unitId on the same row. An id that matches no recipe fails the call before anything is written.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          }
        },
        "additionalProperties": false
      }
    },
    "addIngredients": {
      "description": "Delta form: ingredient rows to add. Without an insert anchor a row is appended to the end, in the order given; anchors must name an existing row that is not being removed, and rows sharing an anchor keep their given order. A row with a \"title\" starts an ingredient section. An explicit referenceId must not already exist on the recipe. Cannot be combined with ingredients.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "quantity": {
            "description": "Numeric amount, e.g. 2. 0 is a valid explicit value; omit to use Mealie's default (0).",
            "type": [
              "number",
              "null"
            ]
          },
          "unitId": {
            "description": "UUID of an existing unit. Must be given together with unitName — never alone.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          },
          "unitName": {
            "description": "Human-readable name of the unit identified by unitId. Required whenever unitId is given.",
            "type": "string"
          },
          "foodId": {
            "description": "UUID of an existing food (see get_food_matches for resolving multiple already-interpreted concepts at once, or get_foods/get_food for a single manual lookup). Must be given together with foodName — never alone. This tool never looks up or creates foods; resolve the food first.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          },
          "foodName": {
            "description": "Human-readable name of the food identified by foodId. Required whenever foodId is given.",
            "type": "string"
          },
          "note": {
            "description": "Free-text note for this ingredient line.",
            "type": [
              "string",
              "null"
            ]
          },
          "display": {
            "description": "Fully composed display string, e.g. \"2 tablespoons olive oil\". Mealie does not persist this field — it always recomputes its own display string from quantity/unit/food/note when the ingredient is read, so do not rely on this value round-tripping literally.",
            "type": "string"
          },
          "originalText": {
            "description": "The original, unparsed ingredient text, if any.",
            "type": [
              "string",
              "null"
            ]
          },
          "title": {
            "description": "Section heading for this ingredient line (e.g. \"For the sauce\"); omit or use null for a normal ingredient.",
            "type": [
              "string",
              "null"
            ]
          },
          "referenceId": {
            "description": "Stable UUID for this ingredient line. Recipe instructions can reference ingredients by this ID — pass back the value from a prior get_recipe_detailed to preserve those links; omit to let Mealie assign a new one.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          },
          "referencedRecipeId": {
            "description": "UUID (the recipe's \"id\", stable across renames — not its slug) of an existing recipe to use as a sub-recipe on this line, e.g. a sauce or spice mix. Read it back as referencedRecipe in get_recipe_detailed. Cannot be combined with foodId/unitId on the same row. An id that matches no recipe fails the call before anything is written.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          },
          "insertAfterReferenceId": {
            "description": "Insert this row directly after the existing row with this referenceId. Not with insertBeforeReferenceId.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          },
          "insertBeforeReferenceId": {
            "description": "Insert this row directly before the existing row with this referenceId. Not with insertAfterReferenceId.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          }
        },
        "additionalProperties": false
      }
    },
    "updateIngredients": {
      "description": "Delta form: partial updates to existing rows, matched by referenceId. Only the fields supplied change; everything else on the row is kept. foodId/foodName and unitId/unitName must each be given as a pair (food/unit can be replaced but not cleared this way — use the complete-replacement form for that). Set \"title\" to add/change/clear (null) a section heading. Cannot be combined with ingredients.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "quantity": {
            "description": "Numeric amount, e.g. 2. 0 is a valid explicit value; omit to use Mealie's default (0).",
            "type": [
              "number",
              "null"
            ]
          },
          "unitId": {
            "description": "UUID of an existing unit. Must be given together with unitName — never alone.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          },
          "unitName": {
            "description": "Human-readable name of the unit identified by unitId. Required whenever unitId is given.",
            "type": "string"
          },
          "foodId": {
            "description": "UUID of an existing food (see get_food_matches for resolving multiple already-interpreted concepts at once, or get_foods/get_food for a single manual lookup). Must be given together with foodName — never alone. This tool never looks up or creates foods; resolve the food first.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          },
          "foodName": {
            "description": "Human-readable name of the food identified by foodId. Required whenever foodId is given.",
            "type": "string"
          },
          "note": {
            "description": "Free-text note for this ingredient line.",
            "type": [
              "string",
              "null"
            ]
          },
          "display": {
            "description": "Fully composed display string, e.g. \"2 tablespoons olive oil\". Mealie does not persist this field — it always recomputes its own display string from quantity/unit/food/note when the ingredient is read, so do not rely on this value round-tripping literally.",
            "type": "string"
          },
          "originalText": {
            "description": "The original, unparsed ingredient text, if any.",
            "type": [
              "string",
              "null"
            ]
          },
          "title": {
            "description": "Section heading for this ingredient line (e.g. \"For the sauce\"); omit or use null for a normal ingredient.",
            "type": [
              "string",
              "null"
            ]
          },
          "referenceId": {
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
            "description": "referenceId of the existing row to update (from get_recipe_detailed)."
          },
          "referencedRecipeId": {
            "description": "UUID (the recipe's \"id\", stable across renames — not its slug) of an existing recipe to use as a sub-recipe on this line, e.g. a sauce or spice mix. Read it back as referencedRecipe in get_recipe_detailed. Cannot be combined with foodId/unitId on the same row. An id that matches no recipe fails the call before anything is written.",
            "type": "string",
            "format": "uuid",
            "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
          }
        },
        "required": [
          "referenceId"
        ],
        "additionalProperties": false
      }
    },
    "removeIngredientReferenceIds": {
      "description": "Delta form: referenceIds of existing rows to remove. Cannot be combined with ingredients, and cannot overlap updateIngredients. Duplicate or unknown referenceIds reject the whole call before any write.",
      "type": "array",
      "items": {
        "type": "string",
        "format": "uuid",
        "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
      }
    }
  },
  "required": [
    "slug"
  ],
  "additionalProperties": false
}
```

## update_recipe_ingredients_batch

Runs update_recipe_ingredients for multiple recipes with bounded concurrency (5 at a time). Use this once several recipes already have COMPLETE, resolved ingredient collections ready to persist — e.g. after batch-resolving food/unit concepts with get_food_matches/get_unit_matches across many recipes — to avoid one individual write call per recipe. Same low-level write semantics as the singular tool, applied independently per entry: each item's "ingredients" is that recipe's complete new recipeIngredient list (not a patch — any ingredient omitted is removed), foodId/unitId must already reference existing Mealie entities (this tool never looks up, matches, or creates foods/units), and referenceIds are preserved exactly as supplied. Same post-write integrity verification and best-effort rollback as the singular tool applies independently per recipe: a verification failure on one recipe restores only that recipe and is reported in its own result entry (error.rollbackSucceeded, plus error.rollbackError if the restore itself failed) — it never affects siblings. There is no cross-recipe transaction: recipes are processed independently, a failure on one (a 404/422/502 from Mealie, a local validation error like a mismatched foodId/foodName, or a verification failure) does not stop or roll back the others, and the response reports a success/failure result per recipe in the same order submitted. The whole call is rejected before any write starts only for a true request-shape problem — an empty batch, more than 25 recipes, a missing slug, or the same slug repeated in one call. Rows may carry referencedRecipeId (sub-recipe by recipe id, instead of a food/unit) exactly as in the singular tool: each distinct referenced id costs one extra GET per recipe (counted in apiRequestCount) and an unknown id fails only that recipe, with nothing written for it. The same recipeInstructions-id-regeneration caveat as update_recipe_ingredients applies to every recipe touched here (instruction content is preserved, only ids churn). Each entry uses either the complete-replacement form (ingredients) or the referenceId delta form (addIngredients/updateIngredients/removeIngredientReferenceIds) with the singular tool's semantics; an invalid or conflicting entry fails only its own result, before that recipe is written.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "updates": {
      "minItems": 1,
      "maxItems": 25,
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "slug": {
            "type": "string",
            "description": "Slug of the recipe to update."
          },
          "ingredients": {
            "description": "Replacement form: complete desired ingredient collection for this recipe, in order — replaces its entire recipeIngredient list. An empty array clears all ingredients for this recipe. Cannot be combined with the delta fields.",
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "quantity": {
                  "description": "Numeric amount, e.g. 2. 0 is a valid explicit value; omit to use Mealie's default (0).",
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "unitId": {
                  "description": "UUID of an existing unit. Must be given together with unitName — never alone.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                },
                "unitName": {
                  "description": "Human-readable name of the unit identified by unitId. Required whenever unitId is given.",
                  "type": "string"
                },
                "foodId": {
                  "description": "UUID of an existing food (see get_food_matches for resolving multiple already-interpreted concepts at once, or get_foods/get_food for a single manual lookup). Must be given together with foodName — never alone. This tool never looks up or creates foods; resolve the food first.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                },
                "foodName": {
                  "description": "Human-readable name of the food identified by foodId. Required whenever foodId is given.",
                  "type": "string"
                },
                "note": {
                  "description": "Free-text note for this ingredient line.",
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "display": {
                  "description": "Fully composed display string, e.g. \"2 tablespoons olive oil\". Mealie does not persist this field — it always recomputes its own display string from quantity/unit/food/note when the ingredient is read, so do not rely on this value round-tripping literally.",
                  "type": "string"
                },
                "originalText": {
                  "description": "The original, unparsed ingredient text, if any.",
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "title": {
                  "description": "Section heading for this ingredient line (e.g. \"For the sauce\"); omit or use null for a normal ingredient.",
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "referenceId": {
                  "description": "Stable UUID for this ingredient line. Recipe instructions can reference ingredients by this ID — pass back the value from a prior get_recipe_detailed to preserve those links; omit to let Mealie assign a new one.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                },
                "referencedRecipeId": {
                  "description": "UUID (the recipe's \"id\", stable across renames — not its slug) of an existing recipe to use as a sub-recipe on this line, e.g. a sauce or spice mix. Read it back as referencedRecipe in get_recipe_detailed. Cannot be combined with foodId/unitId on the same row. An id that matches no recipe fails the call before anything is written.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                }
              },
              "additionalProperties": false
            }
          },
          "addIngredients": {
            "description": "Delta form: ingredient rows to add. Without an insert anchor a row is appended to the end, in the order given; anchors must name an existing row that is not being removed, and rows sharing an anchor keep their given order. A row with a \"title\" starts an ingredient section. An explicit referenceId must not already exist on the recipe. Cannot be combined with ingredients.",
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "quantity": {
                  "description": "Numeric amount, e.g. 2. 0 is a valid explicit value; omit to use Mealie's default (0).",
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "unitId": {
                  "description": "UUID of an existing unit. Must be given together with unitName — never alone.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                },
                "unitName": {
                  "description": "Human-readable name of the unit identified by unitId. Required whenever unitId is given.",
                  "type": "string"
                },
                "foodId": {
                  "description": "UUID of an existing food (see get_food_matches for resolving multiple already-interpreted concepts at once, or get_foods/get_food for a single manual lookup). Must be given together with foodName — never alone. This tool never looks up or creates foods; resolve the food first.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                },
                "foodName": {
                  "description": "Human-readable name of the food identified by foodId. Required whenever foodId is given.",
                  "type": "string"
                },
                "note": {
                  "description": "Free-text note for this ingredient line.",
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "display": {
                  "description": "Fully composed display string, e.g. \"2 tablespoons olive oil\". Mealie does not persist this field — it always recomputes its own display string from quantity/unit/food/note when the ingredient is read, so do not rely on this value round-tripping literally.",
                  "type": "string"
                },
                "originalText": {
                  "description": "The original, unparsed ingredient text, if any.",
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "title": {
                  "description": "Section heading for this ingredient line (e.g. \"For the sauce\"); omit or use null for a normal ingredient.",
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "referenceId": {
                  "description": "Stable UUID for this ingredient line. Recipe instructions can reference ingredients by this ID — pass back the value from a prior get_recipe_detailed to preserve those links; omit to let Mealie assign a new one.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                },
                "referencedRecipeId": {
                  "description": "UUID (the recipe's \"id\", stable across renames — not its slug) of an existing recipe to use as a sub-recipe on this line, e.g. a sauce or spice mix. Read it back as referencedRecipe in get_recipe_detailed. Cannot be combined with foodId/unitId on the same row. An id that matches no recipe fails the call before anything is written.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                },
                "insertAfterReferenceId": {
                  "description": "Insert this row directly after the existing row with this referenceId. Not with insertBeforeReferenceId.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                },
                "insertBeforeReferenceId": {
                  "description": "Insert this row directly before the existing row with this referenceId. Not with insertAfterReferenceId.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                }
              },
              "additionalProperties": false
            }
          },
          "updateIngredients": {
            "description": "Delta form: partial updates to existing rows, matched by referenceId. Only the fields supplied change; everything else on the row is kept. foodId/foodName and unitId/unitName must each be given as a pair (food/unit can be replaced but not cleared this way — use the complete-replacement form for that). Set \"title\" to add/change/clear (null) a section heading. Cannot be combined with ingredients.",
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "quantity": {
                  "description": "Numeric amount, e.g. 2. 0 is a valid explicit value; omit to use Mealie's default (0).",
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "unitId": {
                  "description": "UUID of an existing unit. Must be given together with unitName — never alone.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                },
                "unitName": {
                  "description": "Human-readable name of the unit identified by unitId. Required whenever unitId is given.",
                  "type": "string"
                },
                "foodId": {
                  "description": "UUID of an existing food (see get_food_matches for resolving multiple already-interpreted concepts at once, or get_foods/get_food for a single manual lookup). Must be given together with foodName — never alone. This tool never looks up or creates foods; resolve the food first.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                },
                "foodName": {
                  "description": "Human-readable name of the food identified by foodId. Required whenever foodId is given.",
                  "type": "string"
                },
                "note": {
                  "description": "Free-text note for this ingredient line.",
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "display": {
                  "description": "Fully composed display string, e.g. \"2 tablespoons olive oil\". Mealie does not persist this field — it always recomputes its own display string from quantity/unit/food/note when the ingredient is read, so do not rely on this value round-tripping literally.",
                  "type": "string"
                },
                "originalText": {
                  "description": "The original, unparsed ingredient text, if any.",
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "title": {
                  "description": "Section heading for this ingredient line (e.g. \"For the sauce\"); omit or use null for a normal ingredient.",
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "referenceId": {
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
                  "description": "referenceId of the existing row to update (from get_recipe_detailed)."
                },
                "referencedRecipeId": {
                  "description": "UUID (the recipe's \"id\", stable across renames — not its slug) of an existing recipe to use as a sub-recipe on this line, e.g. a sauce or spice mix. Read it back as referencedRecipe in get_recipe_detailed. Cannot be combined with foodId/unitId on the same row. An id that matches no recipe fails the call before anything is written.",
                  "type": "string",
                  "format": "uuid",
                  "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                }
              },
              "required": [
                "referenceId"
              ],
              "additionalProperties": false
            }
          },
          "removeIngredientReferenceIds": {
            "description": "Delta form: referenceIds of existing rows to remove. Cannot be combined with ingredients, and cannot overlap updateIngredients. Duplicate or unknown referenceIds reject the whole call before any write.",
            "type": "array",
            "items": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
            }
          }
        },
        "required": [
          "slug"
        ],
        "additionalProperties": false
      },
      "description": "One entry per recipe to update. Each entry uses either the replacement form (a complete ingredient collection in `ingredients`) or the delta fields, never both. Each recipe is processed independently with bounded concurrency (5 at a time) — a failure on one recipe does not abort the others. Max 25 recipes per call; each slug must be unique within the call."
    }
  },
  "required": [
    "updates"
  ],
  "additionalProperties": false
}
```

## update_recipe_instructions

Edits a recipe's instructions (text, title, summary, and links to ingredients via ingredientReferenceIds), PATCHing only recipeInstructions. Mealie instruction IDs are ephemeral — regenerated on every recipe write — so they are never accepted or valid as identity and must not be saved. Instead: call get_recipe_detailed first, pass that snapshot's exact updatedAt as expectedUpdatedAt, and address instructions by zero-based index in that snapshot. expectedUpdatedAt guards against editing from a stale snapshot: if the recipe has already changed when the tool reads it for mutation, the call fails before writing and the caller must re-read and retry. Mealie does not provide conditional recipe writes, so a concurrent edit occurring in the narrow interval between that validation read and the PATCH cannot be detected before the write. Two mutually exclusive forms: delta (addInstructions/updateInstructions/removeInstructionIndexes — focused edits, all indexes and anchors refer to the original snapshot) or instructions (complete ordered replacement — use for substantial rebuilds/reordering; [] clears all). ingredientReferenceIds must be referenceIds of the recipe's current ingredients (unknown, malformed or duplicate ids are rejected before any write; Mealie regenerates the id on every read for a legacy/unpinned ingredient that never had one stored — this affects only such ingredients, not every ingredient. To pin them, use update_recipe_ingredients complete replacement with the full ingredient collection, explicitly supplying a referenceId for every continuing row; then re-read the recipe before retrying, because the ingredient write changes the recipe snapshot and its updatedAt); the MCP never infers links — deciding wording, sectioning and which ingredients belong to a step is your job. Delta updates preserve omitted fields, untouched instructions and existing noteReferences exactly (existing dangling ingredient references are not cleaned up). A change that leaves instructions identical skips the write and returns the current recipe. After a write the returned recipe is verified by content (text/title/summary/ingredient and note references, ignoring ids); on mismatch the original instructions are restored best-effort and the call fails, reporting whether rollback succeeded (ids are regenerated by each write and rollback).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string",
      "description": "Slug of the recipe to update."
    },
    "expectedUpdatedAt": {
      "type": "string",
      "minLength": 1,
      "description": "The exact opaque updatedAt from the get_recipe_detailed read whose instruction indexes you are using. Pass it back unchanged. A mismatch means the recipe changed since that read: the call fails before any write (a stale-snapshot guard, not an atomic conditional write)."
    },
    "instructions": {
      "description": "Replacement form: complete desired ordered instruction list. Cannot be combined with the delta fields.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "text": {
            "type": "string",
            "minLength": 1,
            "description": "Instruction text."
          },
          "title": {
            "description": "Instruction section title; omit or null for none.",
            "type": [
              "string",
              "null"
            ]
          },
          "summary": {
            "description": "Instruction summary; omit or null for none.",
            "type": [
              "string",
              "null"
            ]
          },
          "ingredientReferenceIds": {
            "description": "referenceIds of the recipe ingredients this instruction uses (from get_recipe_detailed recipeIngredient).",
            "type": "array",
            "items": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
            }
          },
          "noteReferenceIds": {
            "description": "Low-level preservation field: noteReferences (referenceId) read from the recipe, passed back unchanged so a complete replacement does not drop them. Omit for none.",
            "type": "array",
            "items": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
            }
          }
        },
        "required": [
          "text"
        ],
        "additionalProperties": false
      }
    },
    "addInstructions": {
      "description": "Delta form: instructions to add. No anchor appends to the end in the given order; anchors refer to the guarded original snapshot, must exist and must not be removed; additions sharing an anchor keep input order; opposite anchors targeting the same gap are rejected as ambiguous. Cannot be combined with instructions.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "text": {
            "type": "string",
            "minLength": 1,
            "description": "Instruction text (required)."
          },
          "title": {
            "type": [
              "string",
              "null"
            ]
          },
          "summary": {
            "type": [
              "string",
              "null"
            ]
          },
          "ingredientReferenceIds": {
            "type": "array",
            "items": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
            }
          },
          "insertBeforeIndex": {
            "description": "Insert before the instruction at this index of the guarded snapshot. Not with insertAfterIndex.",
            "type": "integer",
            "minimum": 0,
            "maximum": 9007199254740991
          },
          "insertAfterIndex": {
            "description": "Insert after the instruction at this index of the guarded snapshot. Not with insertBeforeIndex.",
            "type": "integer",
            "minimum": 0,
            "maximum": 9007199254740991
          }
        },
        "required": [
          "text"
        ],
        "additionalProperties": false
      }
    },
    "updateInstructions": {
      "description": "Delta form: partial updates by snapshot index. Only supplied fields change; omitted fields and noteReferences are preserved. An index may appear once and cannot also be removed.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "index": {
            "type": "integer",
            "minimum": 0,
            "maximum": 9007199254740991,
            "description": "Zero-based index in the guarded snapshot."
          },
          "text": {
            "type": "string",
            "minLength": 1
          },
          "title": {
            "type": [
              "string",
              "null"
            ]
          },
          "summary": {
            "type": [
              "string",
              "null"
            ]
          },
          "ingredientReferenceIds": {
            "description": "Replaces this instruction's complete ingredient links; [] clears them; omit to keep them.",
            "type": "array",
            "items": {
              "type": "string",
              "format": "uuid",
              "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
            }
          }
        },
        "required": [
          "index"
        ],
        "additionalProperties": false
      }
    },
    "removeInstructionIndexes": {
      "description": "Delta form: zero-based snapshot indexes to remove (no duplicates, no overlap with updates).",
      "type": "array",
      "items": {
        "type": "integer",
        "minimum": 0,
        "maximum": 9007199254740991
      }
    }
  },
  "required": [
    "slug",
    "expectedUpdatedAt"
  ],
  "additionalProperties": false
}
```

## update_recipe_instructions_batch

Runs update_recipe_instructions for multiple recipes with bounded concurrency (5 at a time). Each entry has its own slug, its own expectedUpdatedAt (exact updatedAt from that recipe's get_recipe_detailed) and exactly one of the replacement form (instructions) or delta form (addInstructions/updateInstructions/removeInstructionIndexes), with the singular tool's semantics. Mealie instruction IDs are ephemeral and never valid identity. Each recipe is validated, written, verified and rolled back independently: a stale expectedUpdatedAt, invalid entry, API error or verification failure fails only that entry. Results come back in input order with requestedCount/succeededCount/failedCount; there is no cross-recipe transaction. The whole call is rejected before any write for an empty batch, more than 25 entries, a missing slug, or a repeated slug.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "updates": {
      "minItems": 1,
      "maxItems": 25,
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "slug": {
            "type": "string",
            "description": "Slug of the recipe to update."
          },
          "expectedUpdatedAt": {
            "type": "string",
            "minLength": 1,
            "description": "The exact opaque updatedAt from the get_recipe_detailed read whose instruction indexes you are using. Pass it back unchanged. A mismatch means the recipe changed since that read: the call fails before any write (a stale-snapshot guard, not an atomic conditional write)."
          },
          "instructions": {
            "description": "Replacement form: complete desired ordered instruction list. Cannot be combined with the delta fields.",
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "text": {
                  "type": "string",
                  "minLength": 1,
                  "description": "Instruction text."
                },
                "title": {
                  "description": "Instruction section title; omit or null for none.",
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "summary": {
                  "description": "Instruction summary; omit or null for none.",
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "ingredientReferenceIds": {
                  "description": "referenceIds of the recipe ingredients this instruction uses (from get_recipe_detailed recipeIngredient).",
                  "type": "array",
                  "items": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                  }
                },
                "noteReferenceIds": {
                  "description": "Low-level preservation field: noteReferences (referenceId) read from the recipe, passed back unchanged so a complete replacement does not drop them. Omit for none.",
                  "type": "array",
                  "items": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                  }
                }
              },
              "required": [
                "text"
              ],
              "additionalProperties": false
            }
          },
          "addInstructions": {
            "description": "Delta form: instructions to add. No anchor appends to the end in the given order; anchors refer to the guarded original snapshot, must exist and must not be removed; additions sharing an anchor keep input order; opposite anchors targeting the same gap are rejected as ambiguous. Cannot be combined with instructions.",
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "text": {
                  "type": "string",
                  "minLength": 1,
                  "description": "Instruction text (required)."
                },
                "title": {
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "summary": {
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "ingredientReferenceIds": {
                  "type": "array",
                  "items": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                  }
                },
                "insertBeforeIndex": {
                  "description": "Insert before the instruction at this index of the guarded snapshot. Not with insertAfterIndex.",
                  "type": "integer",
                  "minimum": 0,
                  "maximum": 9007199254740991
                },
                "insertAfterIndex": {
                  "description": "Insert after the instruction at this index of the guarded snapshot. Not with insertBeforeIndex.",
                  "type": "integer",
                  "minimum": 0,
                  "maximum": 9007199254740991
                }
              },
              "required": [
                "text"
              ],
              "additionalProperties": false
            }
          },
          "updateInstructions": {
            "description": "Delta form: partial updates by snapshot index. Only supplied fields change; omitted fields and noteReferences are preserved. An index may appear once and cannot also be removed.",
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "index": {
                  "type": "integer",
                  "minimum": 0,
                  "maximum": 9007199254740991,
                  "description": "Zero-based index in the guarded snapshot."
                },
                "text": {
                  "type": "string",
                  "minLength": 1
                },
                "title": {
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "summary": {
                  "type": [
                    "string",
                    "null"
                  ]
                },
                "ingredientReferenceIds": {
                  "description": "Replaces this instruction's complete ingredient links; [] clears them; omit to keep them.",
                  "type": "array",
                  "items": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
                  }
                }
              },
              "required": [
                "index"
              ],
              "additionalProperties": false
            }
          },
          "removeInstructionIndexes": {
            "description": "Delta form: zero-based snapshot indexes to remove (no duplicates, no overlap with updates).",
            "type": "array",
            "items": {
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            }
          }
        },
        "required": [
          "slug",
          "expectedUpdatedAt"
        ],
        "additionalProperties": false
      },
      "description": "One entry per recipe. Max 25 per call; each slug must be unique within the call."
    }
  },
  "required": [
    "updates"
  ],
  "additionalProperties": false
}
```

## update_recipe_taxonomy

Updates a recipe's categories and/or tags. Resolves requested names/slugs/IDs against existing taxonomy, optionally auto-creating missing values. Reads the recipe first to merge with existing taxonomy. Per collection, use either categories/tags (+ mode merge/replace) or the delta fields addCategories/removeCategories/addTags/removeTags (current - remove + add, other assignments untouched); additions and removals can be combined in one call. Removals must exist and are never created; createMissing only applies to additions. Unchanged Category/Tag collections are never written, whether the legacy merge/replace form or explicit delta form is used; if nothing changes, no recipe PATCH is issued. Returns final/added/removed/created per collection.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string",
      "description": "Slug of the recipe to update."
    },
    "categories": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Categories to assign, each given as a name, slug, or ID (matched case-insensitively by name/slug). Categories are broad groupings (e.g. \"Dinner\", \"Dessert\") as opposed to Tags, which are more specific attributes (e.g. \"Quick\", \"Dairy-Free\"). Omit this field to leave the recipe's categories unchanged. Passing an empty array with mode \"replace\" clears all categories from the recipe — use with care."
    },
    "tags": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Tags to assign, each given as a name, slug, or ID (matched case-insensitively by name/slug). Tags are specific, free-form attributes (e.g. \"Quick\", \"Dairy-Free\") as opposed to Categories, which are broad groupings (e.g. \"Dinner\", \"Dessert\"). Omit this field to leave the recipe's tags unchanged. Passing an empty array with mode \"replace\" clears all tags from the recipe — use with care."
    },
    "addCategories": {
      "description": "Delta form: categories to add (name, slug, or ID). Cannot be combined with categories. Unchanged categories are preserved.",
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "removeCategories": {
      "description": "Delta form: categories to remove (name, slug, or ID). Must already exist — never created. Cannot be combined with categories, and cannot overlap addCategories.",
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "addTags": {
      "description": "Delta form: tags to add (name, slug, or ID). Cannot be combined with tags.",
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "removeTags": {
      "description": "Delta form: tags to remove (name, slug, or ID). Must already exist — never created. Cannot be combined with tags, and cannot overlap addTags.",
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "mode": {
      "type": "string",
      "enum": [
        "merge",
        "replace"
      ],
      "description": "merge (default) adds the given categories/tags to whatever the recipe already has. replace overwrites the corresponding collection with exactly the given list — an empty array in replace mode clears that collection entirely."
    },
    "createMissing": {
      "type": "boolean",
      "description": "When true, any named category/tag that does not already exist in Mealie is created automatically. When false (default), unknown names cause the call to fail with an error listing the unresolved values."
    }
  },
  "required": [
    "slug"
  ],
  "additionalProperties": false
}
```

## update_recipe_taxonomy_batch

Runs update_recipe_taxonomy for multiple recipes with bounded concurrency (5 at a time), returning a success/error result per recipe. Each entry accepts the same legacy (categories/tags + mode) or delta (addCategories/removeCategories/addTags/removeTags) fields. Each slug may appear only once; a request that repeats a slug is rejected as a whole before any recipe is processed. Category/tag creation via createMissing is serialized across the batch so a value requested by several recipes is created once, but createMissing applies per entry: an entry without it may fail as missing even if another entry creates that value, so set createMissing on every entry that names a new category or tag.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "updates": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "slug": {
            "type": "string",
            "description": "Slug of the recipe to update."
          },
          "categories": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Categories to assign, each given as a name, slug, or ID (matched case-insensitively by name/slug). Categories are broad groupings (e.g. \"Dinner\", \"Dessert\") as opposed to Tags, which are more specific attributes (e.g. \"Quick\", \"Dairy-Free\"). Omit this field to leave the recipe's categories unchanged. Passing an empty array with mode \"replace\" clears all categories from the recipe — use with care."
          },
          "tags": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Tags to assign, each given as a name, slug, or ID (matched case-insensitively by name/slug). Tags are specific, free-form attributes (e.g. \"Quick\", \"Dairy-Free\") as opposed to Categories, which are broad groupings (e.g. \"Dinner\", \"Dessert\"). Omit this field to leave the recipe's tags unchanged. Passing an empty array with mode \"replace\" clears all tags from the recipe — use with care."
          },
          "addCategories": {
            "description": "Delta form: categories to add (name, slug, or ID). Cannot be combined with categories. Unchanged categories are preserved.",
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          },
          "removeCategories": {
            "description": "Delta form: categories to remove (name, slug, or ID). Must already exist — never created. Cannot be combined with categories, and cannot overlap addCategories.",
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          },
          "addTags": {
            "description": "Delta form: tags to add (name, slug, or ID). Cannot be combined with tags.",
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          },
          "removeTags": {
            "description": "Delta form: tags to remove (name, slug, or ID). Must already exist — never created. Cannot be combined with tags, and cannot overlap addTags.",
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          },
          "mode": {
            "type": "string",
            "enum": [
              "merge",
              "replace"
            ],
            "description": "merge (default) adds the given categories/tags to whatever the recipe already has. replace overwrites the corresponding collection with exactly the given list — an empty array in replace mode clears that collection entirely."
          },
          "createMissing": {
            "type": "boolean",
            "description": "When true, any named category/tag that does not already exist in Mealie is created automatically. When false (default), unknown names cause the call to fail with an error listing the unresolved values."
          }
        },
        "required": [
          "slug"
        ],
        "additionalProperties": false
      },
      "description": "One entry per recipe to update; slugs must be unique (duplicates reject the whole request with no changes). Each recipe is processed independently with bounded concurrency — a failure on one recipe does not abort the others, and the response includes a success/error result for every entry."
    }
  },
  "required": [
    "updates"
  ],
  "additionalProperties": false
}
```

## update_recipe_tools

Assigns Mealie Tool organizers (equipment, e.g. "Whisk", "Sheet Pan") to one existing recipe. You decide which tools the recipe needs; this tool only resolves them deterministically (exact ID, then slug, then name, case-insensitive — no fuzzy matching or substitution) and persists them, PATCHing only the recipe's tools field. Two mutually exclusive forms: (1) tools + mode — "merge" (default) keeps existing assignments, "replace" sets the complete collection and DESTRUCTIVELY clears all assigned tools when tools is an empty array; (2) add and/or remove — a delta computed as current - remove + add, leaving every other assigned tool untouched. Unknown tools fail the call before any recipe write unless createMissing is true, which creates values from tools/add (never from remove); if a later creation or the recipe write then fails, any Tool organizers already created remain (no rollback). The same tool in both add and remove is rejected, and a call that changes nothing skips the recipe write.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string",
      "description": "Slug of the recipe to update."
    },
    "tools": {
      "description": "Legacy form: tools to assign, each a name, slug, or ID of a Mealie Tool organizer. An empty array is a no-op in merge mode, but with mode \"replace\" it DESTRUCTIVELY clears all tools from the recipe. Cannot be combined with add/remove.",
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "mode": {
      "description": "Only for the tools form. merge (default) adds to existing tools; replace sets exactly the given list and removes all others.",
      "type": "string",
      "enum": [
        "merge",
        "replace"
      ]
    },
    "add": {
      "description": "Delta form: tools to add (name, slug, or ID). Cannot be combined with tools/mode.",
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "remove": {
      "description": "Delta form: tools to remove (name, slug, or ID). Must already exist as Tool organizers — never created. Cannot be combined with tools/mode, and cannot overlap add.",
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "createMissing": {
      "description": "When true, tools from tools/add that do not exist are created using the requested value as the name. Default false: unknown values fail the call and are all listed.",
      "type": "boolean"
    }
  },
  "required": [
    "slug"
  ],
  "additionalProperties": false
}
```

## update_recipe_tools_batch

Applies update_recipe_tools to several recipes in one call. Each update accepts the same legacy (tools + mode) or delta (add/remove) contract as the singular tool, with the same deterministic ID/slug/name resolution — you decide which tools each recipe needs. Recipes are processed independently with bounded concurrency (5 at a time), results are returned in input order with per-recipe success/error plus requested/succeeded/failed counts, and a failure on one recipe never stops or rolls back the others (no cross-recipe transaction; Tool organizers created for a recipe that later fails remain). Organizer creation via createMissing is serialized across the batch so a Tool requested by several recipes is created once. createMissing still applies per entry: an entry without it may fail as missing even if another entry in the same call creates that Tool, so set createMissing on every entry that names a new Tool. The whole call is rejected before any write for an empty batch, more than 25 updates, a missing slug, or the same recipe slug repeated.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "updates": {
      "minItems": 1,
      "maxItems": 25,
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "slug": {
            "type": "string",
            "description": "Slug of the recipe to update."
          },
          "tools": {
            "description": "Legacy form: tools to assign, each a name, slug, or ID of a Mealie Tool organizer. An empty array is a no-op in merge mode, but with mode \"replace\" it DESTRUCTIVELY clears all tools from the recipe. Cannot be combined with add/remove.",
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          },
          "mode": {
            "description": "Only for the tools form. merge (default) adds to existing tools; replace sets exactly the given list and removes all others.",
            "type": "string",
            "enum": [
              "merge",
              "replace"
            ]
          },
          "add": {
            "description": "Delta form: tools to add (name, slug, or ID). Cannot be combined with tools/mode.",
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          },
          "remove": {
            "description": "Delta form: tools to remove (name, slug, or ID). Must already exist as Tool organizers — never created. Cannot be combined with tools/mode, and cannot overlap add.",
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          },
          "createMissing": {
            "description": "When true, tools from tools/add that do not exist are created using the requested value as the name. Default false: unknown values fail the call and are all listed.",
            "type": "boolean"
          }
        },
        "required": [
          "slug"
        ],
        "additionalProperties": false
      },
      "description": "One entry per recipe, each with its own tools/mode or add/remove mutation. Max 25 per call; each slug must be unique within the call."
    }
  },
  "required": [
    "updates"
  ],
  "additionalProperties": false
}
```

## duplicate_recipe

Creates a duplicate of an existing recipe with an optional new name.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string"
    },
    "name": {
      "type": "string"
    }
  },
  "required": [
    "slug"
  ],
  "additionalProperties": false
}
```

## mark_recipe_last_made

Records when a recipe was last made. Without `timestamp` it records now. `timestamp` is an ISO 8601 date-time (e.g. 2026-09-29T18:45:00Z; without an offset it is local time) or a plain date (YYYY-MM-DD), which is stored as noon local time on that day so time-zone conversion cannot shift it to the previous day (today is clamped to now). Unparseable values and future times are rejected without calling Mealie. Mealie only moves a recipe's lastMade forward: a timestamp older than the current lastMade is accepted but leaves it unchanged.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string"
    },
    "timestamp": {
      "type": "string"
    }
  },
  "required": [
    "slug"
  ],
  "additionalProperties": false
}
```

## set_recipe_image

Sets, replaces, or deletes a recipe's image. Pass `imageBase64` as base64-encoded PNG, JPEG, WebP, or GIF data (max 10 MB; a data: URI prefix is accepted) to upload or replace the image, or pass `null` to delete the existing image. Input is validated before anything is sent to Mealie, and no other recipe fields are touched. `extension` is optional; the format is detected from the data, and a mismatching extension is rejected. To set an image from a URL instead, use `set_recipe_image_from_url`.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string"
    },
    "imageBase64": {
      "description": "Base64-encoded image data to upload, or null to delete the recipe image.",
      "type": [
        "string",
        "null"
      ]
    },
    "extension": {
      "description": "Optional image extension (png, jpg, jpeg, webp, gif); must match the data.",
      "type": "string"
    }
  },
  "required": [
    "slug",
    "imageBase64"
  ],
  "additionalProperties": false
}
```

## set_recipe_rating

Sets the rating and/or favorite flag of a recipe for the user behind the API key. The rating is per user; the recipe's own `rating` field is the aggregate over all users (with a single rater they are equal). rating is 0.5–5 in steps of 0.5 (Mealie itself does not validate the range); null clears the caller's rating (stored as 0, reported as null); omit it to leave the rating unchanged. isFavorite alone changes only the favorite flag. At least one of the two is required. Returns { userRating: { recipeId, rating, isFavorite }, recipeRating } read back after the update.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string"
    },
    "rating": {
      "anyOf": [
        {
          "type": "number",
          "minimum": 0.5,
          "maximum": 5,
          "multipleOf": 0.5
        },
        {
          "type": "null"
        }
      ]
    },
    "isFavorite": {
      "type": "boolean"
    }
  },
  "required": [
    "slug"
  ],
  "additionalProperties": false
}
```

## set_recipe_image_from_file

Sets or replaces a recipe's image from a host-provided file reference (host-dependent: only hosts that can pass file parameters, such as ChatGPT via `openai/fileParams`, supply `file`). The server downloads `file.download_url` directly, so no base64 passes through the model. Preferred order: this tool when the host provides a file reference; `set_recipe_image_from_url` when the image is at a fetchable URL; `set_recipe_image` with base64 as the portable fallback (and with `null` to delete an image). The download is limited to public http(s) hosts, a timeout, and 10 MB; PNG, JPEG, WebP, and GIF are accepted and the format is detected from the bytes (`mime_type`/`file_name` are only hints). Validation happens before anything is sent to Mealie, and no other recipe fields are touched.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string"
    },
    "file": {
      "type": "object",
      "properties": {
        "download_url": {
          "type": "string",
          "description": "Temporary URL the server downloads the file from."
        },
        "file_id": {
          "type": "string",
          "description": "Host file identifier."
        },
        "mime_type": {
          "description": "Optional MIME type hint; not trusted.",
          "type": "string"
        },
        "file_name": {
          "description": "Optional file name hint; not trusted.",
          "type": "string"
        }
      },
      "required": [
        "download_url",
        "file_id"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "slug",
    "file"
  ],
  "additionalProperties": false
}
```

## set_recipe_image_from_url

Sets a recipe's image from a URL.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string"
    },
    "imageUrl": {
      "type": "string"
    }
  },
  "required": [
    "slug",
    "imageUrl"
  ],
  "additionalProperties": false
}
```

## delete_recipe

Permanently deletes a recipe.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "slug": {
      "type": "string"
    }
  },
  "required": [
    "slug"
  ],
  "additionalProperties": false
}
```

## get_all_mealplans

Lists meal plans with optional date range filtering and pagination.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "startDate": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
    },
    "endDate": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
    },
    "page": {
      "type": "number"
    },
    "perPage": {
      "type": "number"
    }
  },
  "additionalProperties": false
}
```

## get_mealplan_with_recipes

Returns meal plans with embedded recipe details (full recipe data fetched via batch requests with bounded concurrency).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "startDate": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
    },
    "endDate": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
    }
  },
  "required": [
    "startDate",
    "endDate"
  ],
  "additionalProperties": false
}
```

## create_mealplan

Creates a single meal plan entry for a given date.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "date": {
      "type": "string"
    },
    "recipeId": {
      "type": "string"
    },
    "title": {
      "type": "string"
    },
    "entryType": {
      "default": "breakfast",
      "type": "string"
    }
  },
  "required": [
    "date"
  ],
  "additionalProperties": false
}
```

## create_mealplan_bulk

Creates multiple meal plan entries at once via bounded concurrent requests. Entries are independent: a failure of one does not stop or undo the others, so a partial failure leaves the successful entries written. Returns { created, failed, results } with one result per input entry in input order: { index, success: true, entry: { id, date, entryType, recipeId, title } } or { index, success: false, error }. The call is an error result only when every entry failed.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "entries": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "date": {
            "type": "string"
          },
          "recipeId": {
            "type": "string"
          },
          "title": {
            "type": "string"
          },
          "entryType": {
            "default": "breakfast",
            "type": "string"
          }
        },
        "required": [
          "date"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "entries"
  ],
  "additionalProperties": false
}
```

## get_todays_mealplan

Returns today's meal plan.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

## patch_mealplan

Performs a batch of mixed operations on meal plan entries in a single call. Use this to move recipes between meal types, update entries, or add new ones.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "actions": {
      "minItems": 1,
      "type": "array",
      "items": {
        "oneOf": [
          {
            "type": "object",
            "properties": {
              "action": {
                "type": "string",
                "const": "delete"
              },
              "id": {
                "type": "string",
                "description": "ID of the meal plan entry to delete"
              }
            },
            "required": [
              "action",
              "id"
            ],
            "additionalProperties": false
          },
          {
            "type": "object",
            "properties": {
              "action": {
                "type": "string",
                "const": "replace"
              },
              "id": {
                "type": "string",
                "description": "ID of the meal plan entry to update"
              },
              "date": {
                "description": "New date (YYYY-MM-DD)",
                "type": "string"
              },
              "recipeId": {
                "description": "New recipe ID",
                "type": "string"
              },
              "title": {
                "description": "New title",
                "type": "string"
              },
              "entryType": {
                "description": "New entry type (breakfast | lunch | dinner | snack)",
                "type": "string"
              }
            },
            "required": [
              "action",
              "id"
            ],
            "additionalProperties": false
          },
          {
            "type": "object",
            "properties": {
              "action": {
                "type": "string",
                "const": "append"
              },
              "date": {
                "type": "string",
                "description": "Date for the new entry (YYYY-MM-DD)"
              },
              "recipeId": {
                "description": "Recipe ID to add",
                "type": "string"
              },
              "title": {
                "description": "Title for the entry",
                "type": "string"
              },
              "entryType": {
                "default": "breakfast",
                "description": "Entry type (breakfast | lunch | dinner | snack)",
                "type": "string"
              }
            },
            "required": [
              "action",
              "date"
            ],
            "additionalProperties": false
          }
        ]
      },
      "description": "Ordered list of actions. Deletions and replacements execute before appends, so you can move a recipe by deleting it from one slot and appending it to another in a single call."
    }
  },
  "required": [
    "actions"
  ],
  "additionalProperties": false
}
```

## get_categories

Lists and searches the household's recipe categories with pagination.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "page": {
      "type": "number"
    },
    "perPage": {
      "type": "number"
    }
  },
  "additionalProperties": false
}
```

## get_empty_categories

Returns categories that have no recipes assigned.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

## create_category

Creates a new recipe category.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "name": {
      "type": "string"
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

## get_category

Retrieves a single category by its UUID.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "categoryId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    }
  },
  "required": [
    "categoryId"
  ],
  "additionalProperties": false
}
```

## get_category_by_slug

Retrieves a single category by its URL slug.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "categorySlug": {
      "type": "string"
    }
  },
  "required": [
    "categorySlug"
  ],
  "additionalProperties": false
}
```

## update_category

Updates a category's name.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "categoryId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    },
    "name": {
      "type": "string"
    }
  },
  "required": [
    "categoryId"
  ],
  "additionalProperties": false
}
```

## delete_category

Deletes a category. Mealie may refuse if recipes still reference it.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "categoryId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    }
  },
  "required": [
    "categoryId"
  ],
  "additionalProperties": false
}
```

## get_tags

Lists and searches the household's recipe tags with pagination.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "page": {
      "type": "number"
    },
    "perPage": {
      "type": "number"
    }
  },
  "additionalProperties": false
}
```

## get_empty_tags

Returns tags that have no recipes assigned.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

## create_tag

Creates a new recipe tag.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "name": {
      "type": "string"
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

## get_tag

Retrieves a single tag by its UUID.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "tagId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    }
  },
  "required": [
    "tagId"
  ],
  "additionalProperties": false
}
```

## get_tag_by_slug

Retrieves a single tag by its URL slug.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "tagSlug": {
      "type": "string"
    }
  },
  "required": [
    "tagSlug"
  ],
  "additionalProperties": false
}
```

## update_tag

Updates a tag's name.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "tagId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    },
    "name": {
      "type": "string"
    }
  },
  "required": [
    "tagId"
  ],
  "additionalProperties": false
}
```

## delete_tag

Deletes a tag. Mealie may refuse if recipes still reference it.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "tagId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    }
  },
  "required": [
    "tagId"
  ],
  "additionalProperties": false
}
```

## get_shopping_lists

Lists the household's shopping lists with pagination.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "page": {
      "type": "number"
    },
    "perPage": {
      "type": "number"
    }
  },
  "additionalProperties": false
}
```

## create_shopping_list

Creates a new shopping list.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "name": {
      "type": "string"
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

## get_shopping_list

Retrieves a shopping list by its UUID.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "listId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    }
  },
  "required": [
    "listId"
  ],
  "additionalProperties": false
}
```

## update_shopping_list

Updates a shopping list's name.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "listId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    },
    "name": {
      "type": "string"
    }
  },
  "required": [
    "listId"
  ],
  "additionalProperties": false
}
```

## delete_shopping_list

Deletes a shopping list.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "listId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    }
  },
  "required": [
    "listId"
  ],
  "additionalProperties": false
}
```

## add_recipe_to_shopping_list

Adds a recipe's ingredients to a shopping list.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "listId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    },
    "recipeId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    },
    "recipeIncrementQuantity": {
      "type": "number"
    }
  },
  "required": [
    "listId",
    "recipeId"
  ],
  "additionalProperties": false
}
```

## remove_recipe_from_shopping_list

Removes a recipe's ingredients from a shopping list.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "listId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    },
    "recipeId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    }
  },
  "required": [
    "listId",
    "recipeId"
  ],
  "additionalProperties": false
}
```

## get_shopping_list_items

Lists all shopping list items across lists with pagination.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "page": {
      "type": "number"
    },
    "perPage": {
      "type": "number"
    },
    "search": {
      "type": "string"
    }
  },
  "additionalProperties": false
}
```

## create_shopping_list_item

Creates a single shopping list item.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "shoppingListId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    },
    "note": {
      "type": "string"
    },
    "quantity": {
      "type": "number"
    },
    "unitId": {
      "type": "string"
    },
    "foodId": {
      "type": "string"
    },
    "labelId": {
      "type": "string"
    }
  },
  "required": [
    "shoppingListId",
    "note"
  ],
  "additionalProperties": false
}
```

## create_shopping_list_items_bulk

Creates multiple shopping list items at once.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "shoppingListId": {
            "type": "string"
          },
          "id": {
            "type": [
              "string",
              "null"
            ]
          },
          "note": {
            "type": [
              "string",
              "null"
            ]
          },
          "display": {
            "type": "string"
          },
          "quantity": {
            "type": "number"
          },
          "checked": {
            "type": "boolean"
          },
          "position": {
            "type": "integer",
            "minimum": -9007199254740991,
            "maximum": 9007199254740991
          },
          "unitId": {
            "type": [
              "string",
              "null"
            ]
          },
          "foodId": {
            "type": [
              "string",
              "null"
            ]
          },
          "labelId": {
            "type": [
              "string",
              "null"
            ]
          },
          "unit": {
            "anyOf": [
              {
                "type": "object",
                "propertyNames": {
                  "type": "string"
                },
                "additionalProperties": {}
              },
              {
                "type": "null"
              }
            ]
          },
          "food": {
            "anyOf": [
              {
                "type": "object",
                "propertyNames": {
                  "type": "string"
                },
                "additionalProperties": {}
              },
              {
                "type": "null"
              }
            ]
          },
          "referencedRecipe": {
            "anyOf": [
              {
                "type": "object",
                "propertyNames": {
                  "type": "string"
                },
                "additionalProperties": {}
              },
              {
                "type": "null"
              }
            ]
          },
          "extras": {
            "anyOf": [
              {
                "type": "object",
                "propertyNames": {
                  "type": "string"
                },
                "additionalProperties": {}
              },
              {
                "type": "null"
              }
            ]
          },
          "recipeReferences": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "recipeId": {
                  "type": "string"
                },
                "recipeQuantity": {
                  "type": "number"
                },
                "recipeScale": {
                  "type": [
                    "number",
                    "null"
                  ]
                },
                "recipeNote": {
                  "type": [
                    "string",
                    "null"
                  ]
                }
              },
              "required": [
                "recipeId"
              ],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "shoppingListId"
        ],
        "additionalProperties": false
      },
      "description": "Items to create; every item needs shoppingListId."
    }
  },
  "required": [
    "items"
  ],
  "additionalProperties": false
}
```

## update_shopping_list_item

Updates a shopping list item's note, quantity, or checked status.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "itemId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    },
    "note": {
      "type": "string"
    },
    "quantity": {
      "type": "number"
    },
    "checked": {
      "type": "boolean"
    }
  },
  "required": [
    "itemId"
  ],
  "additionalProperties": false
}
```

## delete_shopping_list_item

Deletes a single shopping list item.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "itemId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$"
    }
  },
  "required": [
    "itemId"
  ],
  "additionalProperties": false
}
```

## delete_shopping_list_items_bulk

Deletes multiple shopping list items at once.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "itemIds": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "itemIds"
  ],
  "additionalProperties": false
}
```

## get_foods

Lists and searches the household's foods (reusable structured ingredient entities such as "chicken breast" or "onion") with plain pagination. For resolving several already-interpreted food concepts to candidate IDs at once (e.g. after an LLM parses a batch of ingredients), prefer get_food_matches instead — it checks aliases too and answers many lookups in one call. Performs no fuzzy matching itself; matching is delegated entirely to Mealie's search.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "search": {
      "description": "Matches against food name and pluralName only, per Mealie's search behavior — despite having aliases, a food is NOT found by searching for one of its aliases here (confirmed by live testing: a food named \"fermented pork\" with alias \"cured pork (som moo)\" is not returned by search=\"som moo\"). Use get_food_matches for alias-aware lookup.",
      "type": "string"
    },
    "page": {
      "type": "number"
    },
    "perPage": {
      "type": "number"
    }
  },
  "additionalProperties": false
}
```

## get_food

Retrieves a single food by ID, including its aliases and label information when present.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "foodId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
      "description": "UUID of the food to retrieve."
    }
  },
  "required": [
    "foodId"
  ],
  "additionalProperties": false
}
```

## get_food_matches

Finds existing canonical Mealie food candidates for multiple already-interpreted food concepts in one call, including stored aliases (which get_foods' search does not check). Use this after deciding what foods an ingredient refers to (e.g. an LLM parsing "2 tbsp chopped fresh parsley" into unit=tablespoon, food=parsley) and before calling create_food, to check whether a matching food or alias already exists. Returns ranked candidates per query rather than choosing one — the caller decides which candidate (if any) to use. Each query's result includes truncated: true when additional matching candidates may exist beyond the returned items (either because there were more than maxMatchesPerQuery, or because Mealie's own retrieval for that query was itself incomplete) — narrow the query text or raise maxMatchesPerQuery if that matters for a given lookup. Does not parse ingredient text, does not perform fuzzy/semantic matching, and does not create, update, or otherwise modify any food or alias.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "queries": {
      "minItems": 1,
      "maxItems": 25,
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1,
        "maxLength": 200
      },
      "description": "Food concepts to resolve, e.g. [\"fresh mozzarella\", \"basil\", \"som moo\"]. 1-25 plain lookup strings (not search syntax) — duplicates (case-insensitive) are resolved once but still returned once per input entry."
    },
    "maxMatchesPerQuery": {
      "description": "Maximum ranked candidates to return per query (default 10, capped at 25). Strongest matches (exact name/pluralName/alias, then substring matches) are kept first when a query has more candidates than this.",
      "type": "integer",
      "minimum": 1,
      "maximum": 25
    }
  },
  "required": [
    "queries"
  ],
  "additionalProperties": false
}
```

## create_food

Creates a new food. Call get_foods first to check whether an existing food or alias already covers this name — creating a duplicate food fragments the taxonomy instead of reusing what is already there.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Name of the new food. Cannot be blank."
    },
    "pluralName": {
      "description": "Plural form of the name, if different.",
      "type": "string"
    },
    "description": {
      "type": "string"
    },
    "aliases": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Alternate names Mealie should also recognize for this food (e.g. \"scallions\" as an alias for \"green onion\"), given as plain strings — converted internally to the alias object shape Mealie expects."
    },
    "labelId": {
      "description": "ID of an existing food label to assign. Does not create a new label.",
      "type": "string"
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

## update_food

Updates an existing food. Fields left unspecified keep their current value. Sufficient for adding an alias: get_food the current record, append to its existing aliases, and pass the complete list back here. householdsWithIngredientFood (household slugs for which the food is on hand) is replaced whole the same way: get_food first and edit the existing list.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "foodId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
      "description": "UUID of the food to update."
    },
    "name": {
      "type": "string"
    },
    "pluralName": {
      "type": "string"
    },
    "description": {
      "type": "string"
    },
    "aliases": {
      "description": "Alternate names Mealie should also recognize for this food (e.g. \"scallions\" as an alias for \"green onion\"), given as plain strings — converted internally to the alias object shape Mealie expects. Replaces the food's entire alias collection when provided — pass an empty array to clear all aliases, or omit this field entirely to leave existing aliases untouched.",
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "labelId": {
      "description": "ID of an existing food label to assign. Pass null to clear the food's label, or omit to leave the current label unchanged.",
      "type": [
        "string",
        "null"
      ]
    },
    "householdsWithIngredientFood": {
      "description": "Household slugs for which this food is flagged on hand (a food is on hand for a household when its slug is in the list). Replaces the whole list when provided — call get_food first and edit the existing list so another household's slug is not dropped by accident. Pass an empty array to clear the flag for every household, or omit to leave it unchanged.",
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "foodId"
  ],
  "additionalProperties": false
}
```

## delete_food

DESTRUCTIVE and irreversible: permanently deletes a food. Use get_food first to verify this is the exact food intended. Deleting a food may affect recipes and shopping list items that reference it — Mealie may refuse the deletion in that case, leaving the food intact.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "foodId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
      "description": "UUID of the food to delete."
    }
  },
  "required": [
    "foodId"
  ],
  "additionalProperties": false
}
```

## merge_foods

DESTRUCTIVE and irreversible: merges one food into another. Every recipe ingredient referencing the from-food is moved to the to-food, and the from-food is permanently deleted. Its name and aliases are NOT kept on the to-food — call update_food afterwards to add them as aliases if wanted. Mealie fails the merge while shopping list items still reference the from-food, leaving both foods untouched; those items are not moved, so find them with get_shopping_list_items and delete them first (delete_shopping_list_items_bulk). Use get_food first to verify both foods. Returns the target food.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "fromFoodId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
      "description": "UUID of the food to merge away; it is deleted."
    },
    "toFoodId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
      "description": "UUID of the food that remains and receives the references."
    }
  },
  "required": [
    "fromFoodId",
    "toFoodId"
  ],
  "additionalProperties": false
}
```

## get_units

Search or list canonical Mealie ingredient units (e.g. "tablespoon", "cup", "gram") with plain pagination. Use this after interpreting an ingredient's unit text (e.g. deciding that "tbsp" in "2 tbsp olive oil" means tablespoon) to resolve the existing Mealie unit and its ID for use with update_recipe_ingredients. This tool does not parse ingredient language or infer units from free text — search matches only against existing unit name, pluralName, abbreviation, and pluralAbbreviation, not aliases. For resolving several already-interpreted unit concepts at once, and for alias-aware matching, prefer get_unit_matches.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "search": {
      "description": "Matches against unit name, pluralName, abbreviation, and pluralAbbreviation, per Mealie's search behavior.",
      "type": "string"
    },
    "page": {
      "type": "number"
    },
    "perPage": {
      "type": "number"
    }
  },
  "additionalProperties": false
}
```

## get_unit

Retrieves a single canonical Mealie ingredient unit by ID, including its aliases, abbreviations, and standard-quantity conversion metadata when present.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "unitId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
      "description": "UUID of the unit to retrieve."
    }
  },
  "required": [
    "unitId"
  ],
  "additionalProperties": false
}
```

## get_unit_matches

Finds existing canonical Mealie unit candidates for multiple already-interpreted unit concepts in one call, matching against names, plural names, abbreviations, plural abbreviations, and stored aliases (which get_units' search does not check). Use after interpreting unit text (e.g. an LLM parsing "2 tbsp olive oil" into unit=tablespoon) and before calling create_unit, to check whether a matching unit or alias already exists. Returns ranked candidates per query rather than choosing one — the caller decides which candidate (if any) to use. Each query's result includes truncated: true when additional matching candidates may exist beyond the returned items (either because there were more than maxMatchesPerQuery, or because Mealie's own retrieval for that query was itself incomplete) — narrow the query text or raise maxMatchesPerQuery if that matters for a given lookup. Does not parse ingredient text, does not perform fuzzy/semantic matching, and does not create, update, or otherwise modify any unit or alias.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "queries": {
      "minItems": 1,
      "maxItems": 25,
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1,
        "maxLength": 200
      },
      "description": "Unit concepts to resolve, e.g. [\"tablespoon\", \"ounce\", \"cup\"]. 1-25 plain lookup strings (not search syntax) — duplicates (case-insensitive) are resolved once but still returned once per input entry."
    },
    "maxMatchesPerQuery": {
      "description": "Maximum ranked candidates to return per query (default 10, capped at 25). Strongest matches (exact name/pluralName/abbreviation/pluralAbbreviation/alias, then substring matches) are kept first when a query has more candidates than this.",
      "type": "integer",
      "minimum": 1,
      "maximum": 25
    }
  },
  "required": [
    "queries"
  ],
  "additionalProperties": false
}
```

## create_unit

Creates a canonical Mealie ingredient unit when an appropriate unit does not already exist. Call get_units first to check whether an existing unit or alias already covers this name — creating a duplicate unit fragments the vocabulary instead of reusing what is already there. Note: if the new unit's name/abbreviation matches one of Mealie's built-in standardized units (e.g. "tablespoon"), Mealie will automatically populate standardQuantity/standardUnit itself unless both are explicitly supplied here — this tool does not perform that matching itself.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Name of the new unit. Cannot be blank."
    },
    "pluralName": {
      "description": "Plural form of the name, if different.",
      "type": "string"
    },
    "description": {
      "type": "string"
    },
    "abbreviation": {
      "description": "Short form used for display when useAbbreviation is true (e.g. \"tbsp\").",
      "type": "string"
    },
    "pluralAbbreviation": {
      "description": "Plural form of abbreviation, used for display when useAbbreviation is true and quantity > 1.",
      "type": "string"
    },
    "useAbbreviation": {
      "description": "Whether Mealie should render this unit using its abbreviation instead of its name. Display-only; does not affect matching or search.",
      "type": "boolean"
    },
    "fraction": {
      "description": "Whether Mealie should render this unit's quantity as a fraction (e.g. \"1 1/2\") instead of a decimal. Display-only.",
      "type": "boolean"
    },
    "aliases": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Alternate names Mealie should also recognize for this unit (e.g. \"tbsp\" or \"tbs\" as aliases for \"tablespoon\"), given as plain strings — converted internally to the alias object shape Mealie expects. Note: aliases are not matched by get_units' search — search only matches name, pluralName, abbreviation, and pluralAbbreviation."
    },
    "standardQuantity": {
      "type": "number",
      "description": "How many standardUnit this unit is equivalent to (e.g. a tablespoon might have standardQuantity 0.5 with standardUnit \"fluid_ounce\"). Used only by Mealie's own shopping-list item merging to combine quantities across differently-expressed but equivalent units — this tool does not compute or validate conversions. Must be provided together with standardUnit: supplying only one causes Mealie to silently clear both."
    },
    "standardUnit": {
      "type": "string",
      "description": "The reference unit standardQuantity is expressed in, as a plain string Mealie's conversion library (pint) can parse (e.g. \"fluid_ounce\", \"cup\", \"gram\"). Must be provided together with standardQuantity: supplying only one causes Mealie to silently clear both."
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

## update_unit

Updates an existing canonical Mealie ingredient unit. Fields left unspecified keep their current value. Sufficient for adding an alias: get_unit the current record, append to its existing aliases, and pass the complete list back here. Units are shared vocabulary referenced by many recipes' ingredients — update deliberately, since renaming or repurposing a unit changes how every recipe using it displays.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "unitId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
      "description": "UUID of the unit to update."
    },
    "name": {
      "type": "string"
    },
    "pluralName": {
      "type": "string"
    },
    "description": {
      "type": "string"
    },
    "abbreviation": {
      "type": "string"
    },
    "pluralAbbreviation": {
      "type": "string"
    },
    "useAbbreviation": {
      "type": "boolean"
    },
    "fraction": {
      "type": "boolean"
    },
    "aliases": {
      "description": "Alternate names Mealie should also recognize for this unit (e.g. \"tbsp\" or \"tbs\" as aliases for \"tablespoon\"), given as plain strings — converted internally to the alias object shape Mealie expects. Note: aliases are not matched by get_units' search — search only matches name, pluralName, abbreviation, and pluralAbbreviation. Replaces the unit's entire alias collection when provided — pass an empty array to clear all aliases, or omit this field entirely to leave existing aliases untouched.",
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "standardQuantity": {
      "description": "How many standardUnit this unit is equivalent to (e.g. a tablespoon might have standardQuantity 0.5 with standardUnit \"fluid_ounce\"). Used only by Mealie's own shopping-list item merging to combine quantities across differently-expressed but equivalent units — this tool does not compute or validate conversions. Must be provided together with standardUnit: supplying only one causes Mealie to silently clear both. Pass null (together with standardUnit: null) to clear both.",
      "anyOf": [
        {
          "type": "number",
          "description": "How many standardUnit this unit is equivalent to (e.g. a tablespoon might have standardQuantity 0.5 with standardUnit \"fluid_ounce\"). Used only by Mealie's own shopping-list item merging to combine quantities across differently-expressed but equivalent units — this tool does not compute or validate conversions. Must be provided together with standardUnit: supplying only one causes Mealie to silently clear both."
        },
        {
          "type": "null"
        }
      ]
    },
    "standardUnit": {
      "description": "The reference unit standardQuantity is expressed in, as a plain string Mealie's conversion library (pint) can parse (e.g. \"fluid_ounce\", \"cup\", \"gram\"). Must be provided together with standardQuantity: supplying only one causes Mealie to silently clear both. Pass null (together with standardQuantity: null) to clear both.",
      "anyOf": [
        {
          "type": "string",
          "description": "The reference unit standardQuantity is expressed in, as a plain string Mealie's conversion library (pint) can parse (e.g. \"fluid_ounce\", \"cup\", \"gram\"). Must be provided together with standardQuantity: supplying only one causes Mealie to silently clear both."
        },
        {
          "type": "null"
        }
      ]
    }
  },
  "required": [
    "unitId"
  ],
  "additionalProperties": false
}
```

## delete_unit

DESTRUCTIVE and irreversible: permanently deletes a canonical Mealie ingredient unit. Use get_unit first to verify this is the exact unit intended. Deleting a unit that is still referenced by existing recipe ingredients will be refused by Mealie rather than cascaded.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "unitId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
      "description": "UUID of the unit to delete."
    }
  },
  "required": [
    "unitId"
  ],
  "additionalProperties": false
}
```

## get_tools

Search or list canonical Mealie Tool organizers (kitchen equipment, e.g. "Whisk", "Sheet Pan") with plain pagination. Search uses Mealie's native name-based search. Read-only. For resolving several already-decided equipment names at once, prefer get_tool_matches.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "search": {
      "description": "Matched against the tool name, per Mealie's search behavior.",
      "type": "string"
    },
    "page": {
      "type": "number"
    },
    "perPage": {
      "type": "number"
    }
  },
  "additionalProperties": false
}
```

## get_tool

Retrieves a single Mealie Tool organizer by ID, including metadata such as householdsWithTool when present.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "toolId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
      "description": "UUID of the tool to retrieve."
    }
  },
  "required": [
    "toolId"
  ],
  "additionalProperties": false
}
```

## get_tool_matches

Finds existing canonical Mealie Tool organizer candidates for multiple equipment names in one call, matching against tool name and slug. You decide which equipment a recipe needs (e.g. that it needs a whisk); this tool only finds the canonical organizer for a name you already chose. Returns ranked candidates per query (exact matches before substring matches, name before slug) and never picks a winner. Each query's result includes truncated: true when more candidates may exist than were returned. Deterministic string matching only — no fuzzy or semantic equipment inference — and it never creates, updates, or deletes anything. Use before create_tool.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "queries": {
      "minItems": 1,
      "maxItems": 25,
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1,
        "maxLength": 200
      },
      "description": "Tool names to resolve, e.g. [\"whisk\", \"sheet pan\"]. 1-25 plain lookup strings (not search syntax) — duplicates (case-insensitive) are resolved once but still returned once per input entry."
    },
    "maxMatchesPerQuery": {
      "description": "Maximum ranked candidates to return per query (default 10, capped at 25).",
      "type": "integer",
      "minimum": 1,
      "maximum": 25
    }
  },
  "required": [
    "queries"
  ],
  "additionalProperties": false
}
```

## create_tool

Creates a canonical Mealie Tool organizer when no appropriate one exists. Call get_tool_matches first to check whether an existing Tool already covers this equipment — creating a duplicate fragments the shared vocabulary. This tool does not manage household "on hand" ownership.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Name of the new tool. Cannot be blank."
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

## update_tool

Renames an existing Mealie Tool organizer. Reads the current Tool first and carries forward its existing householdsWithTool ownership metadata, since Mealie's PUT is a full replacement; household ownership itself cannot be changed here. Tools are shared by every recipe that uses them, so rename deliberately.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "toolId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
      "description": "UUID of the tool to update."
    },
    "name": {
      "description": "New name. At least one update field is required.",
      "type": "string"
    }
  },
  "required": [
    "toolId"
  ],
  "additionalProperties": false
}
```

## delete_tool

DESTRUCTIVE and irreversible: permanently deletes a Mealie Tool organizer. Use get_tool first to verify this is the exact Tool intended. If Mealie refuses the deletion, its error is surfaced unchanged.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "toolId": {
      "type": "string",
      "format": "uuid",
      "pattern": "^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$",
      "description": "UUID of the tool to delete."
    }
  },
  "required": [
    "toolId"
  ],
  "additionalProperties": false
}
```
