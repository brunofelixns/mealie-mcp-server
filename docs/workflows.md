# Flujos de uso

## Consulta y propuesta

Buscar recetas por texto, categorías y etiquetas usando sus nombres/slugs/IDs. Los filtros estructurados se resuelven contra los organizadores Mealie; las búsquedas aproximadas de alimentos, unidades y equipamiento devuelven candidatos, sin inventar asociaciones. Las colas de clasificación, parseo y enriquecimiento son lecturas paginadas con cursor estable; no aplican cambios por consultarlas.

El prompt weekly-meal-plan admite preferencias y prepara una propuesta semanal. Sus mensajes conservan la confirmación humana antes de guardar. El servidor no incorpora un modelo de IA: el cliente decide cuándo invocar herramientas y el operador controla las credenciales.

## Guardar recetas y normalizar ingredientes

Crear una receta permite texto de ingredientes/instrucciones. Para estructurarla, resolver primero entidades existentes y conservar la línea original; foodId/unitId requieren sus nombres coherentes. update_recipe_ingredients admite reemplazo o deltas por referenceId, valida antes de escribir y verifica el resultado. No mezclar ambos modos.

Para instrucciones usar el updatedAt leído como expectedUpdatedAt y operar por índices del snapshot. Referenciar ingredientReferenceIds existentes; no reutilizar IDs efímeros de instrucciones como claves de edición. Si otra operación modifica la receta, releer antes de volver a proponer cambios. Una restauración fallida se informa explícitamente y exige inspección del estado Mealie antes de repetir.

Taxonomías y equipamiento permiten reemplazo/merge o deltas según su contrato. createMissing habilita creación solo cuando se solicita. Los batches preservan orden y resultados individuales; no interpretar una respuesta de lote como éxito de cada entrada.

## Planificación y compras

Crear o modificar entradas del plan con fechas YYYY-MM-DD y recipeId real. patch_mealplan procesa borrados, reemplazos y anexados en ese orden y entrega resultados por fase. El valor por defecto de entryType conserva breakfast; indicar dinner/lunch cuando corresponda.

Las listas de compra admiten entradas, lotes y asociación de recetas. Preservar quantity=0, false, null y listas vacías según cada herramienta. Algunas respuestas Mealie describen cambios de colección, no un único item: usar la referencia pública y releer la lista cuando se necesite confirmar su estado.

## Imágenes, rating y fechas

set_recipe_image acepta base64 hasta10MiB, con detección real de PNG/JPEG/GIF/WebP; null elimina. set_recipe_image_from_file usa el objeto download_url/file_id del cliente, rechaza destinos privados y no confía en nombre/MIME sugeridos. set_recipe_image_from_url delega la URL a Mealie. Las tres formas tienen efectos diferentes y límites documentados en sus schemas.

set_recipe_rating modifica el rating/favorito del usuario autenticado, separado del rating agregado de la receta; null limpia el rating. mark_recipe_last_made interpreta fechas con TZ explícita y conserva las reglas de la referencia. En Mealie3.29, lastMade pertenece al resumen del hogar y no aparece en RecipeRead; no se inventa ese campo en la respuesta de get_recipe_detailed.

## Desconexión y operación

El cliente puede desconectarse después de una escritura que Mealie ya aceptó. Las mutaciones verificadas completan su comprobación/restauración con plazo acotado; no repetir a ciegas una petición cuyo resultado se desconoce. No existe recuperación duradera después de matar el proceso.

Las credenciales Mealie y Bearer personal son independientes. stdio usa solo la primera; HTTP exige ambas. [Clientes](clients.md), [HTTP](http-deployment.md) y [contenedores](containers.md) describen configuración, límites y shutdown. Consultar el [informe de aceptación](migration/acceptance.md) para distinguir lo probado localmente de un despliegue público.

## CI y publicación

La [CI y publicación automática](ci.md) verifica cada push/PR en Linux amd64 y
arm64 nativos. Release Please acumula la versión y el CHANGELOG en una PR.
Fusionarla crea el tag/Release y despacha los checks y publicación de ese tag;
otras ramas y PR solo se verifican, sin permisos para publicar.

`.github/workflows/ci.yaml` utiliza el Dev Container. Instala desde el lock frozen,
comprueba Ruff/mypy y documentación, construye runtime, ejecuta pytest con
JUnit/cobertura y el checker78/78, integra Mealie desechable y analiza la imagen.
Conserva logs, métricas, reportes, SBOM y wheel. Cada comando falla al primer error.

La integración ejecuta `uv run python -m tests.e2e.runner --image mealie-mcp-server:local --no-build` sobre la imagen ya construida. El gate exige cuatro combinaciones de transporte/protocolo,78 herramientas y78 rechazos por combinación, sin skips; un fallo de prueba, cobertura de llamadas o limpieza hace fallar el comando. Los [informes E2E](testing/local-e2e.md) se conservan también si falla el job.

El job `publish` carga las imágenes verificadas desde artefactos de la misma
ejecución, comprueba sus IDs y plataformas, y las sube con `GITHUB_TOKEN`. Verifica
el manifest `sha-<commit>` antes de actualizar `latest`. No reconstruye después de
probar ni utiliza credenciales de publicación durante el build. Los scripts de
publicación local y el workflow de release manual se retiraron.

Renovate propone cambios sin automerge. Revisar dependencias, bases e ICU con el corpus de contratos y ambos transportes; no actualizar snapshots para ocultar diferencias. Los comandos y requisitos de entorno están en [desarrollo](development.md).
