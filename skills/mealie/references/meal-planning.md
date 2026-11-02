# Meal planning

Establish the dates, meal slots, people, and dietary needs from the request and
known context. Resolve relative dates using the user's timezone. Ask about a
missing constraint only when it changes the plan materially.

Read existing entries with `get_all_mealplans` or `get_mealplan_with_recipes` for
the target range. Search the recipe collection, then fetch selected recipes in
batches when possible. Use stored recipe IDs for plan entries, not slugs. Do not
assume that nutrition or allergen information missing from a recipe is verified.

The `weekly-meal-plan` prompt offers a seven-day breakfast/lunch/dinner starting
point. Adapt the workflow to the meals and dates actually requested. Present the
complete proposed plan as a table before saving and obtain confirmation of that
concrete plan. A confirmation already given for the displayed plan is sufficient.

For saving new entries, `create_mealplan_bulk` accepts `entries` with `date`,
`entryType`, and `recipeId` or `title`. Use explicit `entryType` for every entry;
its default is breakfast. Use `patch_mealplan` only for requested changes to
existing entries, preserving other meals in the period.

Bulk creation consists of independent writes. Its `created`, `failed`, and
per-entry `results` describe partial success; successful entries remain saved.
Read the affected date range after an ambiguous result. Do not resubmit the
whole plan and duplicate entries that were already created.

For a shopping stage, read `references/shopping.md` from the skill root. Saving a menu alone
does not authorize creating or modifying a shopping list. Report menu and
shopping outcomes separately if one stage succeeds and the other fails.
