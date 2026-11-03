# Recetas con Mealie 3.30.0

La referencia de integración es Mealie **3.30.0**, fijada por digest. El catálogo
actual tiene **162 herramientas**: conserva las 102 anteriores y añade 60. Los
[esquemas generados](tools.md) son el contrato exacto; esta guía explica decisiones,
efectos y límites. El MCP no es un proxy libre de toda la administración Mealie.

## Buscar y obtener sugerencias

`search_recipes` añade filtros nativos de alimentos, utensilios, hogares y
recetarios, ordenación, `queryFilter` y paginación. `get_recipes` conserva sus
argumentos originales. Para ordenar por tiempo normalizado:

```json
{"orderBy":"totalTimeSeconds","orderDirection":"asc","page":1,"perPage":20}
```

`get_recipe_suggestions` expone las opciones nativas de faltantes de alimentos y
utensilios, existencias disponibles y sustituciones. Los filtros y sustitutos
deben identificar las entidades del vocabulario de Mealie; no se inventan
equivalencias. `find_recipes_for_ingredients` sigue ofreciendo su búsqueda por
nombres y aliases. El resultado es una sugerencia, no una edición de receta.

## Sustituciones y duración de pasos

`update_recipe_ingredient_substitutions` administra alternativas de un ingrediente
por `referenceId`; `update_food_substitutions` administra las del alimento del
vocabulario. Las referencias usan IDs canónicos existentes; también se admiten
alternativas explícitas solo textuales mediante `note`, sin crear alimentos.
Mealie recorta espacios de esas notas y convierte las vacías en `null`; la
verificación reconoce únicamente esa normalización nativa. Leer el estado antes
de cambiarlo; las escrituras de receta requieren `expectedUpdatedAt`, conservan
orden, otros campos y referencias, y verifican el resultado. Una lista vacía
elimina las sustituciones del destino seleccionado.

Las herramientas antiguas de ingredientes y alimentos conservan ahora las
sustituciones y campos de proveedor que sus entradas no representan. Los campos
conocidos siguen su semántica anterior de reemplazo/delta. D14 registra esta
diferencia de persistencia; no se reescriben las capturas originales.

`update_recipe_instruction_durations` utiliza índices del snapshot actual y
`durationSeconds`: entero de 1 a 2.147.483.647; `null` elimina el temporizador.
Conserva texto, títulos, referencias y otros datos. Los IDs de pasos pueden
regenerarse en Mealie: el índice solo vale con el `expectedUpdatedAt` de la lectura.

`parse_recipe_ingredient` y `parse_recipe_ingredients` delegan expresamente en el
parser elegido de Mealie. No aplican el resultado a una receta: inspeccionarlo y
usar después la herramienta de escritura correspondiente. El flujo de
interpretación del cliente sigue disponible y no se cambia automáticamente.

## Adjuntos, imágenes y recetas compartidas

`get_recipe_assets` lista metadatos. `download_recipe_asset` exige un archivo
presente en esa receta. `download_recipe_image` y `download_recipe_timeline_image`
leen variantes `original.webp`, `min-original.webp` o `tiny-original.webp`;
el evento debe pertenecer a la receta seleccionada.

Las descargas devuelven `filename`, `mediaType`, `size` y `dataBase64`, con máximo
20 MiB, sin escribir archivos del host. Se rechazan rutas inseguras y redirecciones
fuera del origen configurado. `get_shared_recipe` y `download_shared_recipe`
usan un token existente para leer la receta o su ZIP. Los tokens siguen siendo
datos sensibles: compartirlos solo cuando el usuario lo pida.

Mealie 3.30 elimina la imagen física del evento al enviar
`update_recipe_timeline_event` con `image:"does not have image"`; se conserva el
campo explícito ya disponible. No se inventa un endpoint de borrado de adjuntos
que el proveedor no ofrece.

## Importaciones y trabajos masivos

`preview_recipe_from_url` extrae sin crear la receta. Las variantes
`import_recipe_from_url_with_progress` y
`import_recipe_from_html_or_json_with_progress` consumen el SSE nativo. El cliente
MCP puede recibir notificaciones de progreso cuando solicita un token de progreso.
La respuesta final identifica la receta creada. Se limitan bytes y eventos; una
interrupción no provoca un segundo intento de escritura.

`import_recipe_with_ai` y `import_recipe_with_ai_with_progress` aceptan contenido,
URL e imágenes según el contrato. Usan el proveedor IA **configurado en Mealie**;
no se crea ni utiliza una clave OpenAI local. Sin proveedor, el error de
configuración se propaga de forma saneada. Las imágenes se envían como partes
multipart repetidas, con límites individuales y conjuntos. Form multipart no
distingue `null` de ausencia; las cadenas vacías y los booleanos sí se transmiten
cuando están presentes.

`import_recipes_from_urls` crea un trabajo y devuelve su informe. Consultarlo con
`get_recipe_import_reports`/`get_recipe_import_report`: aceptar el trabajo no
significa que todas las URL hayan terminado bien. `delete_recipes_bulk`,
`export_recipes_bulk`, `get_recipe_bulk_exports`, `download_recipe_bulk_export`
y `purge_recipe_bulk_exports` cubren los lotes del proveedor. El purgado afecta
los exports de ese ámbito; no usarlo como limpieza automática de otro trabajo.

`update_recipe_metadata_batch` aplica snapshots por receta y devuelve resultados
individuales con concurrencia limitada. No hay transacción global ni rollback
entre recetas. Las herramientas por lotes existentes de taxonomía, ingredientes
e instrucciones siguen siendo las opciones especializadas.

Antes de cualquier PATCH, el lote resuelve todos los destinos a sus IDs canónicos
con lecturas acotadas. Un slug y un UUID de la misma receta se consideran un
duplicado y rechazan el lote completo antes de escribir. Esto añade una lectura
por destino; la edición vuelve a leer por ID para verificar el snapshot fresco.
Si una identidad no puede resolverse, ese elemento devuelve `failed` indicando
que no se emitió una escritura; otros destinos distintos pueden continuar.
`unknown` se conserva para mutaciones que no se pueden confirmar. Ninguna fase
reintenta escrituras y el control de snapshot sigue sin ser un CAS atómico.

## Recetarios, favoritos y lecturas completas

Los recetarios tienen CRUD explícito (`get_cookbooks`, `create_cookbook`,
`get_cookbook`, `update_cookbook`, `delete_cookbook`). `get_recipe_favorites` y
`get_recipe_ratings` añaden consulta personal; marcar favoritos sigue disponible
con `set_recipe_rating`.
Mealie recorta espacios del nombre y genera el slug, incluida la resolución de
colisiones; no se ofrece editar ese slug derivado. Las mutaciones resuelven un
slug de entrada al UUID actual antes de escribir o borrar.

`list_recipe_comments`, `get_recipe_comment`, `get_recipe_timeline_event` y
`get_recipe_share_link` completan las lecturas. Las acciones de receta tienen
CRUD y `trigger_recipe_action`; este último puede ejecutar una petición externa
configurada y solo debe llamarse cuando se pide esa acción. Una aceptación
asíncrona no confirma la entrega al destino.

`get_recipe_household` recupera `recipeId` y `lastMade` del hogar actual, incluido
`null` si todavía no se ha preparado. Esta información tiene su propio endpoint;
la fecha no se deduce del contenido general de la receta.

## Planificación avanzada

Las nuevas herramientas `list_mealplan_entries`, `create_mealplan_entry`,
`get_mealplan_entry`, `update_mealplan_entry` y `delete_mealplan_entry` admiten texto,
`recipeScale` positivo y `endDate`. Una entrada semanal termina exactamente seis
días después de `date`. Las seis herramientas anteriores mantienen su contrato.

Se incluyen creación aleatoria de entrada, CRUD de reglas y gestión del token
iCal con descarga del calendario. Rotar o eliminar el token modifica el acceso
a esa suscripción; no hacerlo como efecto secundario de consultar el plan.

## Validación y alcance

Las pruebas de contratos exigen positivos y rechazos de argumentos por cada
herramienta. La integración desechable verifica stdio/HTTP y ambas eras MCP con
la imagen instalada y lecturas independientes de Mealie. El entorno no configura
un proveedor IA real: sus dos herramientas tienen positivos HTTP/SSE controlados
y un rechazo de configuración comprobado en la instancia real, contabilizado
aparte de las operaciones positivas. Esto no demuestra una llamada satisfactoria
a un proveedor LLM real.

La [evidencia local de 3.30](testing/mealie-3.30-evidence.md) identifica la imagen
probada, los cuatro recorridos, las comprobaciones y sus límites.

Los usuarios, backups, configuración de proveedores, migraciones y administración
general siguen fuera de esta ampliación de recetas. Variantes API redundantes
pueden estar cubiertas por una herramienta equivalente; contar rutas no es medir
por sí solo la cobertura funcional.

La comparación del OpenAPI de la imagen fijada se conserva en la
[auditoría API](testing/mealie-3.30-api-audit.json). Distingue rutas utilizadas
directamente y alternativas nativas de lotes. Los PUT/PATCH masivos de recetas,
tag/categorize/settings masivos y PUT masivo de recetarios se cubren mediante
editores explícitos y sus lotes especializados, con sus propios contratos de
snapshot, orden y resultados parciales; no se afirma equivalencia exacta de
efectos o errores con esas rutas. No se incorpora un editor JSON irrestricto.
La exploración pública de otros grupos mantiene otro ámbito de acceso y no
forma parte de esta ampliación del hogar configurado.

La captura contiene 283 operaciones de API; 90 pertenecen al ámbito de recetas y
planificación definido aquí: 84 aparecen como dependencias del catálogo y seis
usan contratos alternativos. No quedan rutas sin clasificar en ese ámbito. Esto
no implica que todos los parámetros de las 283 operaciones se expongan al cliente.
Para repetir la comparación desde el Dev Container, guardar el OpenAPI de la
instancia 3.30.0 desechable y ejecutar:

```bash
uv run --frozen python scripts/audit_mealie_api.py \
  --schema artifacts/mealie330/openapi.json --expected-version v3.30.0 \
  --output artifacts/mealie330/api-audit.json
```

El comando utiliza por defecto el contrato revisado
`tests/fixtures/mealie330/provider-contract.json`. Falla ante una versión distinta,
nuevas rutas de recetas sin clasificar, dependencias inexistentes y cambios
estructurales incompatibles en las peticiones/respuestas seleccionadas: tipos,
nulabilidad, campos requeridos, enums y límites. Las ampliaciones compatibles y
las anotaciones documentales no requieren rehacer el contrato. Las formas de
schema fuera del comparador acotado se rechazan, sin resolver referencias remotas.

El controlador E2E descarga el OpenAPI real y ejecuta esta auditoría antes del
bootstrap con credenciales y de los escenarios de mutación. La CI ya ejecuta
ese controlador y falla si la auditoría falla, manteniendo la limpieza del stack.
Cada ejecución conserva `openapi.json` y `api-audit.json`, con hashes del OpenAPI,
catálogo y contrato. El fixture tiene procedencia de la imagen 3.30.0 fijada; no se
actualiza automáticamente con el proveedor ni modifica los baselines históricos.
No se comprueban todos los valores predeterminados o validadores de negocio: las
pruebas de comportamiento siguen siendo necesarias.

Los límites enteros de las nuevas herramientas se publican mediante los keywords
JSON Schema `minimum` y `maximum`, incluidos paginación, IDs de planificación,
duración iCal, `recipeCount` y concurrencia del lote. Se conservan enteros JSON
como `1.0` cuando representan un entero, y se rechazan booleanos, fracciones y
valores fuera de los límites. Las pruebas comparan la aceptación del esquema
publicado con la validación del servidor.
