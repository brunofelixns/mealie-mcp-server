# Shopping lists

Use `get_shopping_lists` to find the requested list and `get_shopping_list` to
inspect its current contents and recipe references. Preserve unrelated items and
checked states. Do not create a new list when the user asked to update an existing
one; resolve ambiguity when several names match.

When shopping from recipes or a menu, resolve recipe IDs from stored recipes or
plan entries. Use `add_recipe_to_shopping_list` with `listId` and `recipeId` to
retain Mealie's recipe linkage. Check existing recipe references before adding
the same recipe again. Its `recipeIncrementQuantity` controls the recipe increment;
do not assume it is a target number of servings without checking the recipe and
tool semantics.

For standalone items, use `create_shopping_list_item` or
`create_shopping_list_items_bulk`. Resolve canonical foods and units when a
structured item is useful. Preserve the user's quantity and note; do not assume
that millilitres equal grams or that all pieces have the same weight.

Do not both link a recipe and manually add all its ingredients for the same
request: this can double the shopping quantities. If separate ingredients are
needed instead of recipe links, choose that representation deliberately.

For removals or updates, use the corresponding list/item tool and the actual
stored IDs. Bulk deletion is limited to the identified items; an empty selection
is not an instruction to clear a list. Read the list after an ambiguous write
before deciding whether a further change is necessary.

Summarize the destination list, recipes linked, items changed, and any unresolved
quantity or duplication issue. Distinguish a shopping proposal from a saved list.
