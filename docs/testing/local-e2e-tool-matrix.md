# Matriz E2E por herramienta

Cada fila se ejecuta en las cuatro combinaciones stdio/HTTP y MCP2026-07-28/2025-11-25. Los identificadores de comprobación corresponden a los informes JSON del controlador; los argumentos públicos están en [tools.md](../tools.md). El [ledger](local-e2e-progress.md) identifica las ejecuciones y sus límites.

Las77 filas positivas verifican operaciones correctas. La fila de archivo verifica un rechazo SSRF y una imagen sin cambios; su descarga positiva desde URL pública no está cubierta por este E2E local. Cada herramienta tiene además un rechazo de campo desconocido con redacción del valor en las cuatro combinaciones.

| Herramienta | Resultado en4 combinaciones | Comprobaciones ejecutadas |
|---|---|---|
| `add_recipe_to_shopping_list` | Positivo (4/4) | `recipe_association_persisted` |
| `create_category` | Positivo (4/4) | `created_value_persisted` |
| `create_food` | Positivo (4/4) | `created_value_persisted`, `merge_target_persisted` |
| `create_mealplan` | Positivo (4/4) | `recipe_plan_persisted` |
| `create_mealplan_bulk` | Positivo (4/4) | `both_entries_created`, `bulk_entry_persisted` |
| `create_recipe` | Positivo (4/4) | `recipe_and_ingredient_persisted` |
| `create_shopping_list` | Positivo (4/4) | `list_persisted` |
| `create_shopping_list_item` | Positivo (4/4) | `item_quantity_persisted` |
| `create_shopping_list_items_bulk` | Positivo (4/4) | `both_bulk_rows_persisted` |
| `create_tag` | Positivo (4/4) | `created_value_persisted` |
| `create_tool` | Positivo (4/4) | `created_value_persisted` |
| `create_unit` | Positivo (4/4) | `created_value_persisted` |
| `delete_category` | Positivo (4/4) | `deleted_identity_absent` |
| `delete_food` | Positivo (4/4) | `deleted_identity_absent` |
| `delete_recipe` | Positivo (4/4) | `deleted_recipe_absent` |
| `delete_shopping_list` | Positivo (4/4) | `list_absent` |
| `delete_shopping_list_item` | Positivo (4/4) | `single_row_absent` |
| `delete_shopping_list_items_bulk` | Positivo (4/4) | `bulk_rows_absent` |
| `delete_tag` | Positivo (4/4) | `deleted_identity_absent` |
| `delete_tool` | Positivo (4/4) | `deleted_identity_absent` |
| `delete_unit` | Positivo (4/4) | `deleted_identity_absent` |
| `duplicate_recipe` | Positivo (4/4) | `independent_duplicate_persisted` |
| `find_recipes_for_ingredients` | Positivo (4/4) | `food_lookup_finds_linked_recipe` |
| `get_all_mealplans` | Positivo (4/4) | `created_plan_and_recipe_returned` |
| `get_categories` | Positivo (4/4) | `created_identity_in_page` |
| `get_category` | Positivo (4/4) | `identity_and_name` |
| `get_category_by_slug` | Positivo (4/4) | `slug_resolves_created_identity` |
| `get_empty_categories` | Positivo (4/4) | `unused_identity_is_empty` |
| `get_empty_tags` | Positivo (4/4) | `unused_identity_is_empty` |
| `get_food` | Positivo (4/4) | `created_identity_returned` |
| `get_food_matches` | Positivo (4/4) | `lookup_resolves_real_identity` |
| `get_foods` | Positivo (4/4) | `search_finds_created_identity` |
| `get_mealplan_with_recipes` | Positivo (4/4) | `created_plan_and_recipe_returned` |
| `get_recipe_concise` | Positivo (4/4) | `recipe_content_returned` |
| `get_recipe_detailed` | Positivo (4/4) | `recipe_content_returned` |
| `get_recipes` | Positivo (4/4) | `search_and_taxonomy_filter_find_recipe` |
| `get_recipes_batch` | Positivo (4/4) | `both_requested_recipes_returned` |
| `get_recipes_detailed_batch` | Positivo (4/4) | `both_requested_recipes_returned` |
| `get_recipes_for_classification` | Positivo (4/4) | `real_recipe_present_in_queue` |
| `get_recipes_for_data_enrichment` | Positivo (4/4) | `real_recipe_present_in_queue` |
| `get_recipes_for_ingredient_parsing` | Positivo (4/4) | `real_recipe_present_in_queue` |
| `get_shopping_list` | Positivo (4/4) | `identity_and_name_returned` |
| `get_shopping_list_items` | Positivo (4/4) | `search_finds_created_item` |
| `get_shopping_lists` | Positivo (4/4) | `created_list_in_page` |
| `get_tag` | Positivo (4/4) | `identity_and_name` |
| `get_tag_by_slug` | Positivo (4/4) | `slug_resolves_created_identity` |
| `get_tags` | Positivo (4/4) | `created_identity_in_page` |
| `get_todays_mealplan` | Positivo (4/4) | `created_plan_and_recipe_returned` |
| `get_tool` | Positivo (4/4) | `created_identity_returned` |
| `get_tool_matches` | Positivo (4/4) | `lookup_resolves_real_identity` |
| `get_tools` | Positivo (4/4) | `search_finds_created_identity` |
| `get_unit` | Positivo (4/4) | `created_identity_returned` |
| `get_unit_matches` | Positivo (4/4) | `lookup_resolves_real_identity` |
| `get_units` | Positivo (4/4) | `search_finds_created_identity` |
| `mark_recipe_last_made` | Positivo (4/4) | `household_timestamp_persisted` |
| `merge_foods` | Positivo (4/4) | `source_removed_and_recipe_reference_rewritten` |
| `patch_mealplan` | Positivo (4/4) | `all_three_phases_succeeded`, `owned_plans_deleted`, `replacement_persisted` |
| `patch_recipe` | Positivo (4/4) | `scalar_fields_persisted` |
| `remove_recipe_from_shopping_list` | Positivo (4/4) | `recipe_association_removed` |
| `set_recipe_image` | Positivo (4/4) | `binary_image_persisted` |
| `set_recipe_image_from_file` | Rechazo SSRF esperado (4/4) | `image_unchanged`, `private_address_refused` |
| `set_recipe_image_from_url` | Positivo (4/4) | `local_url_image_persisted_and_readable` |
| `set_recipe_rating` | Positivo (4/4) | `personal_rating_and_favorite_persisted` |
| `update_category` | Positivo (4/4) | `rename_persisted` |
| `update_food` | Positivo (4/4) | `updated_fields_persisted` |
| `update_recipe_ingredients` | Positivo (4/4) | `structured_reference_and_food_persisted` |
| `update_recipe_ingredients_batch` | Positivo (4/4) | `batch_success_and_quantity_persisted` |
| `update_recipe_instructions` | Positivo (4/4) | `instruction_and_ingredient_link_persisted` |
| `update_recipe_instructions_batch` | Positivo (4/4) | `appended_instruction_persisted`, `batch_entries_succeeded` |
| `update_recipe_taxonomy` | Positivo (4/4) | `taxonomy_persisted` |
| `update_recipe_taxonomy_batch` | Positivo (4/4) | `batch_taxonomy_persisted` |
| `update_recipe_tools` | Positivo (4/4) | `equipment_persisted` |
| `update_recipe_tools_batch` | Positivo (4/4) | `batch_equipment_persisted` |
| `update_shopping_list` | Positivo (4/4) | `name_persisted` |
| `update_shopping_list_item` | Positivo (4/4) | `zero_checked_and_note_persisted` |
| `update_tag` | Positivo (4/4) | `rename_persisted` |
| `update_tool` | Positivo (4/4) | `updated_fields_persisted` |
| `update_unit` | Positivo (4/4) | `updated_fields_persisted` |
