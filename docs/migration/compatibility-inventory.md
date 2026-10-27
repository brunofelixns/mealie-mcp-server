# Inventario de compatibilidad: Mealie MCP en Python

Fecha: 2026-10-27. Estado:14/78herramientas Python verificadas; ver implementation-state.json y evidence/P08.md.

La referencia es [timo-reymann/mealie-mcp-server, commit d027e1b4a314d781a322f1f91e37840f01464d77](https://github.com/timo-reymann/mealie-mcp-server/tree/d027e1b4a314d781a322f1f91e37840f01464d77). El alcance es migrar lo que implementa este commit, incluidos sus flujos compuestos. No equivale a implementar todos los endpoints posibles de Mealie.

El directorio local estaba vacío y sin repositorio Git al comenzar. Este entregable contiene documentación; posteriormente P01..P03 incorporaron el historial, abrieron el Dev Container, crearon el paquete Python y ejecutaron el original; ver evidence/P03.md.

## 1. Evidencia y reglas de lectura

- 78 herramientas registradas en ocho módulos, un prompt y las instrucciones generales del servidor.
- Cero resources MCP registrados en el entrypoint y los módulos revisados.
- 42 archivos TypeScript revisados y ejecutados en P03:1058pruebas pasan,0fallan; informe JSON extraído del contenedor.
- El paquete declara 2.1.0, mientras el servidor anuncia 1.0.0. La introducción del README habla de 71 herramientas; la lista generada y los registros reales contienen 78.
- El inventario JSON conserva los nombres, las descripciones y expresiones Zod originales, las declaraciones compartidas, los parámetros expandidos de factories, los endpoints declarados y enlaces al commit. Las expresiones Zod son evidencia estática, no JSON Schema ya obtenido por MCP.
- runtimeInputSchema y la presencia/ausencia de runtimeOutputSchema se capturaron en P03. runtimeExamples se completará por familia. La ausencia de outputSchema está marcada explícitamente, no se considera dato perdido.
- Las referencias a tests se obtuvieron buscando el nombre completo de cada herramienta en los 42 archivos. Una referencia no demuestra cobertura ejecutada; su ausencia tampoco prueba que no haya pruebas de la API interna.
- Los nombres públicos y el camelCase actual se conservan. Las listas de argumentos de las tablas incluyen obligatorios y opcionales: el esquema exacto y sus defaults se consultan en el JSON y se verificarán después en tools/list.
- migrationStatus y runtimeExamples del JSON identifican las familias implementadas y los casos ejecutados; las demás siguen pendientes.

Archivos relacionados: [inventario JSON](compatibility-inventory.json), [diseño](../superpowers/specs/2026-10-27-python-migration-design.md), [licencia original](upstream-LICENSE.txt).

## 2. Herramientas

### Recetas (26)

| ID y herramienta | Argumentos públicos | Contrato que conservar |
|---|---|---|
| T001 [`get_recipes`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L343) | `search`, `page`, `perPage`, `categories`, `tags`, `requireAllTags`, `requireAllCategories` | Resolver categorías y tags por nombre/slug/ID; arrays como claves repetidas al llamar a Mealie. |
| T002 [`find_recipes_for_ingredients`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L375) | `ingredients`, `categories`, `tags`, `requireAllIngredients`, `requireAllCategories`, `requireAllTags`, `limit` | Búsqueda determinista por alimentos, sugerencias y fallback textual; informar procedencia y ambigüedad. |
| T003 [`get_recipe_detailed`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L424) | `slug` | Devolver el detalle completo, conservando campos de Mealie que el MCP no conozca. |
| T004 [`get_recipe_concise`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L439) | `slug` | Mantener exactamente la proyección resumida del original. |
| T005 [`get_recipes_batch`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L460) | `slugs` | Resultados en orden de entrada; concurrencia de detalle 4 y errores aislados. |
| T006 [`get_recipes_detailed_batch`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L475) | `slugs` | Detalle completo por slug con el mismo aislamiento y orden que el original. |
| T007 [`get_recipes_for_classification`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L490) | `cursor`, `limit`, `taxonomyState` | Cursor v1; límite por defecto 25/máximo 50; taxonomyState por defecto missing_either. |
| T008 [`get_recipes_for_ingredient_parsing`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L548) | `cursor`, `limit`, `state` | Solo auditar estado almacenado; no interpretar texto ni crear alimentos/unidades. |
| T009 [`get_recipes_for_data_enrichment`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L633) | `cursor`, `limit`, `match`, `filters` | Filtros completos: reemplazan los defaults; filters={} se rechaza; match any/all. |
| T010 [`create_recipe`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L719) | `name`, `ingredients`, `instructions` | POST inicial devuelve slug; con ingredientes/instrucciones hay lectura y actualización posteriores; puede quedar creada si esa fase falla. |
| T011 [`patch_recipe`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L752) | `slug`, `name`, `description`, `recipeYield`, `totalTime`, `recipeServings`, `recipeYieldQuantity`, `orgURL`, `categories`, `tags`, `taxonomyMode`, `createMissing`, `instructions` | PATCH focalizado; taxonomyChanges; omisión preserva campos; no escribir una taxonomía idéntica. |
| T012 [`update_recipe_ingredients`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L808) | `slug`, `ingredients`, `addIngredients`, `updateIngredients`, `removeIngredientReferenceIds` | Reemplazo o delta por referenceId; validar, persistir, verificar y restaurar best effort. |
| T013 [`update_recipe_ingredients_batch`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L865) | `updates` | 1..25, slugs únicos, concurrencia 5; resultado independiente por receta, sin transacción global. |
| T014 [`update_recipe_instructions`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L931) | `slug`, `expectedUpdatedAt`, `instructions`, `addInstructions`, `updateInstructions`, `removeInstructionIndexes` | expectedUpdatedAt obligatorio; índices del snapshot; IDs efímeros; verificación y restauración best effort. |
| T015 [`update_recipe_instructions_batch`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L975) | `updates` | 1..25 y concurrencia 5; snapshot, validación y recuperación por receta. |
| T016 [`update_recipe_taxonomy`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L1016) | `slug`, `categories`, `tags`, `addCategories`, `removeCategories`, `addTags`, `removeTags`, `mode`, `createMissing` | Merge/replace o add/remove; resolver canónicos; createMissing solo explícito. |
| T017 [`update_recipe_taxonomy_batch`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L1045) | `updates` | Duplicados rechazan todo; concurrencia 5; creación de canónicos serializada. No inventar un máximo 25: el contrato original no lo declara. |
| T018 [`update_recipe_tools`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L1083) | `slug`, `tools`, `mode`, `add`, `remove`, `createMissing` | Asignar utensilios; merge/replace o add/remove; preservar otros campos y evitar escrituras sin cambios. |
| T019 [`update_recipe_tools_batch`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L1107) | `updates` | 1..25, concurrencia 5; creación serializada; fallos independientes y canónicos creados no se revierten. |
| T020 [`duplicate_recipe`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L1141) | `slug`, `name` | Conservar slug de origen y nombre opcional. |
| T021 [`mark_recipe_last_made`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L1156) | `slug`, `timestamp` | Fecha sin hora = mediodía local; hoy limitado a ahora; fechas futuras inválidas. |
| T022 [`set_recipe_image`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L1175) | `slug`, `imageBase64`, `extension` | Base64 con tipos comprobados por bytes y máximo 10 MiB; null elimina; extensión debe coincidir. |
| T023 [`set_recipe_rating`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L1194) | `slug`, `rating`, `isFavorite` | Rating propio del usuario de la API key: 0.5..5 en pasos 0.5; null envía 0 para borrar; no-op del lookup fallido no se cachea. |
| T024 [`set_recipe_image_from_file`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L1225) | `slug`, `file` | file es objeto download_url/file_id, no ruta local. Mantener _meta openai/fileParams y descarga con DNS fijado. |
| T025 [`set_recipe_image_from_url`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L1252) | `slug`, `imageUrl` | Mealie obtiene imageUrl mediante su endpoint; no sustituir por la descarga local del MCP. |
| T026 [`delete_recipe`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/recipes.ts#L1267) | `slug` | Borrado permanente; capturar comportamiento real de respuesta, incluyendo 204. |

### Planes de comidas (6)

| ID y herramienta | Argumentos públicos | Contrato que conservar |
|---|---|---|
| T027 [`get_all_mealplans`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/mealplans.ts#L34) | `startDate`, `endDate`, `page`, `perPage` | Filtrado por fecha y paginación; preservar semántica de los parámetros. |
| T028 [`get_mealplan_with_recipes`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/mealplans.ts#L54) | `startDate`, `endDate` | Recorrer todas las páginas necesarias; filtrar fechas y adjuntar detalles con concurrencia 4. |
| T029 [`create_mealplan`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/mealplans.ts#L98) | `date`, `recipeId`, `title`, `entryType` | Una entrada en fecha dada; mantener entryType y valores por defecto originales. |
| T030 [`create_mealplan_bulk`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/mealplans.ts#L118) | `entries` | Entradas independientes y resultados en orden de entrada; isError solo si todas fallan. |
| T031 [`get_todays_mealplan`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/mealplans.ts#L160) | Sin argumentos | Usar el endpoint today de Mealie; no sustituir por la fecha calculada en el contenedor. |
| T032 [`patch_mealplan`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/mealplans.ts#L175) | `actions` | Ejecutar delete, luego replace y luego append; resultados agrupados por fase, no por orden global de entrada. |

### Categorías (7)

| ID y herramienta | Argumentos públicos | Contrato que conservar |
|---|---|---|
| T033 [`get_categories`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/categories.ts#L7) | `page`, `perPage` | Paginación con page/perPage; no añadir search al contrato porque la descripción lo sugiera. |
| T034 [`get_empty_categories`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/categories.ts#L22) | Sin argumentos | Endpoint específico de categorías sin recetas. |
| T035 [`create_category`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/categories.ts#L37) | `name` | Crear por nombre, conservando forma de respuesta y errores. |
| T036 [`get_category`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/categories.ts#L52) | `categoryId` | Consultar por categoryId. |
| T037 [`get_category_by_slug`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/categories.ts#L67) | `categorySlug` | Consultar por categorySlug; validar/codificar un único segmento. |
| T038 [`update_category`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/categories.ts#L82) | `categoryId`, `name` | Cambiar nombre por ID. |
| T039 [`delete_category`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/categories.ts#L99) | `categoryId` | Borrado; conservar el error de Mealie si sigue referenciada. |

### Etiquetas (7)

| ID y herramienta | Argumentos públicos | Contrato que conservar |
|---|---|---|
| T040 [`get_tags`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tags.ts#L7) | `page`, `perPage` | Paginación con page/perPage; no ampliar parámetros silenciosamente. |
| T041 [`get_empty_tags`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tags.ts#L22) | Sin argumentos | Endpoint específico de etiquetas sin recetas. |
| T042 [`create_tag`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tags.ts#L37) | `name` | Crear por nombre. |
| T043 [`get_tag`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tags.ts#L52) | `tagId` | Consultar por tagId. |
| T044 [`get_tag_by_slug`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tags.ts#L67) | `tagSlug` | Consultar por tagSlug; validar/codificar segmento. |
| T045 [`update_tag`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tags.ts#L82) | `tagId`, `name` | Cambiar nombre por ID. |
| T046 [`delete_tag`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tags.ts#L99) | `tagId` | Borrado; conservar rechazo de Mealie si está referenciada. |

### Listas de compra (13)

| ID y herramienta | Argumentos públicos | Contrato que conservar |
|---|---|---|
| T047 [`get_shopping_lists`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L36) | `page`, `perPage` | Listar listas del household con paginación. |
| T048 [`create_shopping_list`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L51) | `name` | Crear lista por nombre. |
| T049 [`get_shopping_list`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L66) | `listId` | Consultar lista por ID. |
| T050 [`update_shopping_list`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L81) | `listId`, `name` | Actualizar nombre por ID. |
| T051 [`delete_shopping_list`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L98) | `listId` | Borrado permanente de lista; caracterizar cuerpo vacío/204. |
| T052 [`add_recipe_to_shopping_list`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L113) | `listId`, `recipeId`, `recipeIncrementQuantity` | Añadir ingredientes con recipeIncrementQuantity opcional. |
| T053 [`remove_recipe_from_shopping_list`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L128) | `listId`, `recipeId` | Operación POST específica /recipe/{recipeId}/delete; no convertirla en DELETE. |
| T054 [`get_shopping_list_items`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L143) | `page`, `perPage`, `search` | Listar items entre listas; search/page/perPage; no aceptar listId inexistente. |
| T055 [`create_shopping_list_item`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L158) | `shoppingListId`, `note`, `quantity`, `unitId`, `foodId`, `labelId` | Crear item con referencias explícitas de lista, alimento, unidad y etiqueta. |
| T056 [`create_shopping_list_items_bulk`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L180) | `items` | Endpoint create-bulk: conservar su contrato de resultado sin imponer la semántica de lotes de recetas. |
| T057 [`update_shopping_list_item`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L195) | `itemId`, `note`, `quantity`, `checked` | Solo note/quantity/checked, manteniendo omisión y false/0. |
| T058 [`delete_shopping_list_item`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L214) | `itemId` | Borrado por itemId. |
| T059 [`delete_shopping_list_items_bulk`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/shopping-lists.ts#L229) | `itemIds` | DELETE con query ids unida por comas; no cambiar a JSON body. |

### Alimentos (7)

| ID y herramienta | Argumentos públicos | Contrato que conservar |
|---|---|---|
| T060 [`get_foods`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/foods.ts#L31) | `search`, `page`, `perPage` | Búsqueda/paginación del vocabulario de alimentos. |
| T061 [`get_food`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/foods.ts#L62) | `foodId` | Leer aliases y label además de campos básicos. |
| T062 [`get_food_matches`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/foods.ts#L77) | `queries`, `maxMatchesPerQuery` | 1..25 consultas de hasta 200 caracteres; candidatos exactos/substring y alias; no elegir automáticamente. |
| T063 [`create_food`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/foods.ts#L122) | `name`, `pluralName`, `description`, `aliases`, `labelId` | Crear canónico con aliases/label opcionales; respetar validaciones y compatibilidad de payload. |
| T064 [`update_food`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/foods.ts#L144) | `foodId`, `name`, `pluralName`, `description`, `aliases`, `labelId`, `householdsWithIngredientFood` | Leer antes del PUT; preservar campos omitidos y hogares, traducir aliases según API. |
| T065 [`delete_food`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/foods.ts#L191) | `foodId` | Destructivo; mantener rechazo/errores y no reintentar automáticamente. |
| T066 [`merge_foods`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/foods.ts#L208) | `fromFoodId`, `toFoodId` | PUT /api/foods/merge; comprobar posterior desaparición del origen; irreversible. |

### Unidades (6)

| ID y herramienta | Argumentos públicos | Contrato que conservar |
|---|---|---|
| T067 [`get_units`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/units.ts#L50) | `search`, `page`, `perPage` | Búsqueda/paginación de unidades canónicas. |
| T068 [`get_unit`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/units.ts#L77) | `unitId` | Leer aliases, abreviaturas y metadatos de conversión. |
| T069 [`get_unit_matches`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/units.ts#L93) | `queries`, `maxMatchesPerQuery` | Mismos límites que alimentos; comparar nombres, plurales, abreviaturas y aliases. |
| T070 [`create_unit`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/units.ts#L140) | `name`, `pluralName`, `description`, `abbreviation`, `pluralAbbreviation`, `useAbbreviation`, `fraction`, `aliases`, `standardQuantity`, `standardUnit` | Crear unidad con aliases y metadatos de conversión; no inferir equivalencias. |
| T071 [`update_unit`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/units.ts#L180) | `unitId`, `name`, `pluralName`, `description`, `abbreviation`, `pluralAbbreviation`, `useAbbreviation`, `fraction`, `aliases`, `standardQuantity`, `standardUnit` | Leer y preservar campos omitidos antes del PUT; null y [] tienen semántica propia. |
| T072 [`delete_unit`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/units.ts#L222) | `unitId` | Borrado irreversible de unidad canónica. |

### Utensilios (6)

| ID y herramienta | Argumentos públicos | Contrato que conservar |
|---|---|---|
| T073 [`get_tools`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tools.ts#L24) | `search`, `page`, `perPage` | Búsqueda/paginación de organizadores de utensilios. |
| T074 [`get_tool`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tools.ts#L44) | `toolId` | Leer metadatos y householdsWithTool cuando existan. |
| T075 [`get_tool_matches`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tools.ts#L58) | `queries`, `maxMatchesPerQuery` | Candidatos por nombre/slug; límites compartidos y sin selección semántica. |
| T076 [`create_tool`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tools.ts#L98) | `name` | Crear utensilio canónico por nombre normalizado. |
| T077 [`update_tool`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tools.ts#L114) | `toolId`, `name` | Renombrar mediante PUT preservando householdsWithTool y campos admitidos. |
| T078 [`delete_tool`](https://github.com/timo-reymann/mealie-mcp-server/blob/d027e1b4a314d781a322f1f91e37840f01464d77/src/tools/tools.ts#L133) | `toolId` | Borrado irreversible de utensilio canónico. |

## 3. Prompt, instrucciones y metadatos

| Elemento | Contrato |
|---|---|
| weekly-meal-plan | preferences opcional, string; dos mensajes con roles assistant y user. Conservar planificación de siete días, variedad y presentación del plan completo para confirmación antes de guardarlo. |
| Instrucciones del servidor | Migrar todo src/server-instructions.ts: principios generales, creación/importación y política de estructuración de ingredientes. Conservar inglés en el contrato para evitar cambios de comportamiento por traducción durante la migración. |
| openai/fileParams | Solo set_recipe_image_from_file declara _meta: {"openai/fileParams":["file"]}. Comprobar que aparece en tools/list; es una extensión opcional del host, no una capacidad universal de MCP. |
| Anotaciones MCP | Conservar las existentes. Añadir las ausentes solo con clasificación revisada por herramienta; son pistas para clientes y no sustituyen autorización. |
| Resources | No hay una superficie que portar. No añadir recursos como condición artificial de modernización. |

La instalación Python no incluirá una llamada a un LLM ni requerirá una clave de OpenAI. El modelo del cliente sigue interpretando; el MCP resuelve, consulta y persiste de forma determinista.

## 4. Contratos transversales

| ID | Contrato | Fuente / evidencia | Aceptación |
|---|---|---|---|
| C01 | Inputs estrictos en todos los objetos declarados, incluso anidados; records/unknown abiertos siguen abiertos. | src/tools/strict-schema.ts y strict-tool-inputs.test.ts | Un campo desconocido no llega al cliente Mealie; probar tipos sin coerciones accidentales. |
| C02 | Omitido, null, 0, false y [] son distintos. | Zod de cada herramienta y tests de ingredientes/taxonomía/unidades | Usar presencia explícita de campos; comparar los cuerpos REST y respuestas, no solo objetos Python. |
| C03 | Mezcla actual de contenido textual JSON y errores isError. | Handlers de los ocho módulos | Capturar el envelope completo y JSON semántico; registrar separadamente diferencias de formato del SDK. |
| C04 | Path segments trimados/codificados; vacíos, punto, doble punto y barras rechazados. | src/api/client.ts y path-segments.test.ts | Ningún ID/slug puede alterar ruta/query/fragment. No añadir requisitos UUID a parámetros que solo eran strings. |
| C05 | Arrays de queries: claves repetidas o comas según endpoint; booleanos en minúsculas. | buildQueryString, formatParams y tests de taxonomy-filter | Comparar URL y payload exactos, incluyendo 204, string JSON y multipart. |
| C06 | Concurrencia limitada y orden contractual. | src/lib/concurrency.ts, lotes y tests | 4 lecturas de detalle, 5 escritores de recetas; no aplicar un límite universal inventado. |
| C07 | Cursor base64url con payload {v:1,lastCreatedAt,lastId,page}, orden por createdAt/id y página 50. | src/lib/recipe-scan.ts | Continuar un cursor TypeScript en Python y viceversa con el mismo dataset. No prometer aislamiento transaccional ante borrados concurrentes. |
| C08 | Colas con default 25/máximo 50, fallos por receta, plazo interno de auditoría 20 s y lectura en lotes. | classification/parsing/enrichment/audit | Una página corta puede tener hasMore=true; cursor y presupuesto deben seguir siendo coherentes. |
| C09 | Ingredientes: referenceId estable cuando existe; display recalculado por Mealie; foodId/unitId pueden no persistir correctamente. | ARCHITECTURE.md e ingredient tests | Verificación tras guardar y restauración best effort; informar cuando la restauración falla. |
| C10 | Instrucciones: expectedUpdatedAt, índice del snapshot, IDs regenerados y preservación de referencias. | recipe-instructions.ts y tests | Rechazar snapshot ya obsoleto; explicitar que Mealie no ofrece compare-and-swap y queda una ventana de carrera. |
| C11 | Lotes independientes y creación serializada de canónicos. | taxonomy/tools/ingredients/instructions libs | Error parcial no implica rollback global; conservar forma y orden particular de cada herramienta. |
| C12 | Descarga file: 10 MiB, 30 s total, máximo 3 redirecciones, firma de bytes y DNS fijado por salto. | recipe-image.ts, safe-download.ts y recipe-image-file.test.ts | Resolver una vez por salto, conectar solo a IP validada conservando Host/SNI/TLS y rechazar IP privada también al conectar. Validar redirects y timeout DNS. |
| C13 | set_recipe_image_from_url delega en Mealie; set_recipe_image_from_file descarga en el MCP. | handlers y src/api/recipes.ts | Mantener dos caminos distintos; las defensas del descargador MCP no prueban la política de descarga del servidor Mealie. |
| C14 | Rating asociado al usuario de MEALIE_API_KEY; caché de self solo tras éxito. | recipe-rating.ts y recipe-rating.test.ts | null borra mediante valor REST 0; conservar favoritos y agregado; caché por cliente/credenciales, nunca global entre configuraciones. |
| C15 | last-made usa zona local del proceso; today usa el servidor Mealie. | last-made.ts y src/api/mealplans.ts | Pruebas de zona, cambio horario y mediodía; TZ explícita en contenedores, default UTC propuesto. |
| C16 | Ningún retry automático de escritura tras timeout o desconexión. | Consecuencia de las escrituras y ausencia de transacciones globales | Documentar resultado incierto; una cancelación no garantiza que Mealie no haya escrito. |

C03 requiere caracterización adicional: algunos handlers pasan el resultado de un DELETE a JSON.stringify. Ante un 204 el cliente retorna undefined y el texto puede ser inválido para MCP. No está demostrado que todos los endpoints reales respondan 204. Se añade un caso de caracterización por DELETE; si se confirma el defecto, la corrección propuesta será una respuesta textual de éxito válida y documentada, con los mismos efectos REST.

## 5. Mapa de módulos y artefactos

| Original | Destino Python propuesto | Evidencia que portar |
|---|---|---|
| src/config.ts | config.py | Variables obligatorias, normalización de URL y errores de arranque sin secretos. |
| src/api/client.ts | mealie/client.py, mealie/errors.py | Lifecycle asíncrono, REST, queries, errores y segmentos. |
| src/api/{recipes,mealplans,shopping-lists,categories,tags,foods,units,tools,users}.ts | mealie/api/*.py | Las mismas operaciones, métodos, proyecciones y normalizaciones. |
| src/lib/*.ts (21 archivos) | services/*.py y support/*.py | Algoritmos deterministas, cursores, auditoría, resolución, escrituras y descargas. Mantener trazabilidad por módulo. |
| src/tools/*.ts (8 catálogos + index + strict-schema) | tools/*.py, tools/registry.py y models/inputs/*.py | 78 registros explícitos y validación de contratos. |
| src/index.ts | server.py, cli.py y prompts.py | Factory, un prompt, transporte elegible y metadatos de versión coherentes. |
| src/server-instructions.ts | resources/server-instructions.md | Contenido completo como dato empaquetado, no nuevo resource MCP. |
| src/__tests__/*.test.ts (42) | tests/unit, tests/contracts, tests/integration | Portar escenarios, fixtures y propiedades; no exigir igual número de archivos ni confundirlo con cobertura. |
| scripts/gen-docs.mjs | scripts/generate_docs.py | Generar catálogo y cobertura API desde el registro Python y comprobar --check. |
| README.md, API_COVERAGE.md, ARCHITECTURE.md, WORKFLOWS.md, CONTRIBUTING.md | Documentación equivalente actualizada | Conservar los flujos existentes y corregir recuentos/versiones; ejemplos uvx/Docker/stdin/HTTP. |
| Dockerfile, workflows CI/Docker, package/release config, hooks, renovate, sonar, opencode.json | Dockerfile por etapas, workflows Python, pyproject/lock y configuración equivalente aplicable | Auditar también infraestructura; retirar Node/npm/Yarn/TypeScript del producto y de herramientas permanentes. Mantener attribution MIT. |

## 6. Pruebas por familia y huecos observados

El JSON relaciona cada herramienta con archivos que mencionan su nombre y conserva el manifiesto de los 42 tests originales. Casos principales:

- Cliente: client, formatParams, query-filter y path-segments.
- Recetas/búsqueda: recipes, recipes-tool-registration, recipes-batch-concurrency, find-recipes-for-ingredients y su tool.
- Colas: recipe-classification, recipe-ingredient-parsing, recipe-enrichment y recipe-audit.
- Ingredientes/instrucciones: recipe-ingredients, recipe-ingredients-tool, recipe-ingredient-parsing-tool, recipe-instructions y referencias cruzadas.
- Taxonomía/equipamiento: recipe-taxonomy, recipe-tools-taxonomy, recipe-tools-update, taxonomy-resolution, tools-api y tools-tools.
- Vocabularios: foods-api/tools, units-api/tools, multi-query-lookup y candidate-matching.
- Imágenes: recipe-image, recipe-image-file y set-recipe-image-from-file-tool.
- Rating/fechas: recipe-rating, last-made y mark-recipe-last-made-tool.
- MCP y documentación: strict-tool-inputs, server-instructions, docs-generation y pruebas de registro.

Hay **24 herramientas sin referencia literal a su nombre completo** en los tests originales revisados:

- set_recipe_rating
- get_empty_categories
- create_category
- get_category
- get_category_by_slug
- update_category
- delete_category
- get_empty_tags
- create_tag
- get_tag
- get_tag_by_slug
- update_tag
- delete_tag
- create_shopping_list
- get_shopping_list
- update_shopping_list
- delete_shopping_list
- add_recipe_to_shopping_list
- remove_recipe_from_shopping_list
- get_shopping_list_items
- create_shopping_list_item
- update_shopping_list_item
- delete_shopping_list_item
- delete_shopping_list_items_bulk

Se requiere un caso MCP positivo y uno de rechazo/error por cada una de las 78 herramientas, incluidas estas 24, además de los escenarios profundos de la lógica compartida. Las pruebas reales de escritura usarán una instancia Mealie desechable con fixtures, nunca datos de producción.

## 7. Ampliaciones acordadas y diferencias controladas

1. Añadir HTTP Streamable autenticado con Bearer para uso personal; mantener stdio por defecto.
2. Modernizar al protocolo 2026-07-28 conservando negociación con clientes anteriores soportados por el SDK; no implementar el protocolo a mano.
3. Empaquetado, entorno de desarrollo, tests, generador documental y runtime en Python. Se admite un runner TypeScript de referencia temporal y aislado para capturar el original; no estará en la imagen final ni será dependencia permanente.
4. Versionado coherente desde metadata de paquete; corregir el desacuerdo original 2.1.0/1.0.0 y las instrucciones con per_page cuando el argumento público real es perPage.
5. Añadir health/readiness HTTP fuera del catálogo MCP y errores seguros sin credenciales.
6. structuredContent/outputSchema será una ampliación por herramienta, solo donde se pueda preservar el contenido contractual existente y demostrar compatibilidad. No inventar un wrapper uniforme que cambie respuestas.
7. Todo endurecimiento adicional que restrinja entradas actualmente aceptadas tendrá una entrada explícita de cambio, motivo y prueba. No esconder cambios de producto bajo la etiqueta de migración.

## 8. Cierre del inventario en implementación

Completar las capturas tools/list, prompts/list, prompt expandido, instrucciones, ejemplos y errores; fijar un esquema JSON del propio inventario; registrar resultados de la suite original y la Python por separado. La conformidad de protocolo y las pruebas de ambos transportes son evidencias independientes de la paridad de negocio. No marcar la migración completa mientras queden herramientas, flujos, documentación o artefactos operativos pendientes.
