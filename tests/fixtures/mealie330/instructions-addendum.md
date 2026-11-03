
## Mealie 3.30 Recipe Capabilities

Use search_recipes for native advanced filters/order/queryFilter and get_recipe_suggestions for missing-food/tool, stock and substitution options. Legacy get_recipes/find_recipes_for_ingredients retain their original contracts.

Substitution edits use update_recipe_ingredient_substitutions or update_food_substitutions with explicit canonical food IDs or meaningful text-only alternatives; never invent or create a food to fill an ID. update_recipe_instruction_durations sets or clears durationSeconds by fresh snapshot index; do not use ephemeral instruction IDs. Preserve unrelated content and refresh after stale or ambiguous writes.

Native parse_recipe_ingredient/parse_recipe_ingredients and AI imports are explicit optional interpretation paths delegated to Mealie; they do not authorize silently applying their output to existing recipes. Existing client interpretation remains available. Native AI imports use Mealie's provider configuration, not a local API key.

Recipe media downloads return bounded base64 data without writing host files or accepting arbitrary URLs. Share and iCal tokens are sensitive. Bulk imports/exports/actions may be asynchronous: accepted is not completed. Report per-item failures, propagate unknown write outcomes and never automatically replay an import, trigger or other write. External recipe actions and token rotations only run on an explicit request.

Cookbook CRUD, current-household last-made data via get_recipe_household, personal favorites/ratings reads, single comment/event/share reads and advanced meal plans are available as separate tools. Advanced meal plans support text, positive recipeScale and weekly endDate exactly six days after date. Keep the scope of the user's request; do not turn recipe editing into provider or account administration.
