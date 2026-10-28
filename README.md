# Mealie MCP Server · Python

Servidor MCP para Mealie con **78 herramientas**, el prompt `weekly-meal-plan`, transporte local **stdio** y **Streamable HTTP** remoto con token Bearer personal. Migración del proyecto MIT de [timo-reymann](https://github.com/timo-reymann/mealie-mcp-server), fijada al commit `d027e1b4a314d781a322f1f91e37840f01464d77`.

Python 3.14, FastMCP 4.1.4 y MCP SDK 2.3.0. Negociación moderna 2026-07-28 y compatibilidad 2025-11-25. Se conservan nombres, argumentos camelCase, efectos y resultados del catálogo original; las diferencias intencionadas se describen en [compatibilidad](docs/migration/differences.md).

## Desarrollo

Abrir el repositorio en VS Code y seleccionar **Dev Containers: Reopen in Container**. Docker Desktop debe usar contenedores Linux. Todas las instalaciones, pruebas y builds se ejecutan dentro del Dev Container; no hace falta Python ni Node en el host.

```sh
uv sync --frozen --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src/mealie_mcp_server
uv run pytest
uv run python scripts/generate_docs.py --check
```

La suite usa fixtures declarativas y tests Python. Las capturas originales se conservan; los runners temporales Node se retiraron al cerrar la migración. Ver [desarrollo](docs/development.md) y [aceptación](docs/migration/acceptance.md).

## Arranque local por stdio

Inyectar `MEALIE_BASE_URL` y `MEALIE_API_KEY` (o `MEALIE_API_KEY_FILE`) desde el cliente. No se carga `.env` automáticamente.

```sh
uv run --frozen mealie-mcp-server --transport stdio
```

`python -m mealie_mcp_server` es equivalente. `--help` y `--version` no requieren secretos. stdout se reserva para JSON-RPC; logs seguros van a stderr. En Windows y Linux se puede conectar el cliente del host con `docker exec -i` o la imagen de producción, sin TTY. [Configuraciones de clientes](docs/clients.md).

## HTTP e imagen de producción

HTTP exige un `MCP_AUTH_TOKEN` independiente de la API key Mealie, o su variante `_FILE`:

```sh
uv run --frozen mealie-mcp-server --transport http --host 0.0.0.0 --port 8000
```

El endpoint es `/mcp`; `/healthz` y `/readyz` no consultan Mealie. En producción configurar HTTPS externo mediante un proxy y hosts/orígenes explícitos. El modo personal no anuncia OAuth. [Despliegue HTTP](docs/http-deployment.md).

```sh
docker build --target runtime -t mealie-mcp-server:local .
```

La imagen funciona en amd64 y arm64, con usuario no root, filesystem read-only y secretos externos. [Construcción, Compose y uso](docs/containers.md). Los escaneos y sus limitaciones están en [el informe de seguridad de la imagen](docs/migration/evidence/P23-security.md); no se declara una imagen sin vulnerabilidades. No se ha publicado una imagen en un registry ni desplegado un endpoint público.

## Documentación

- [Índice y estado](docs/README.md).
- [Configuración](docs/configuration.md), [clientes](docs/clients.md) y [contenedores](docs/containers.md).
- [Arquitectura](docs/architecture.md) y [flujos](docs/workflows.md).
- [Cobertura de endpoints](docs/api-coverage.md) y [schemas de las herramientas](docs/tools.md).
- [Inventario de compatibilidad](docs/migration/compatibility-inventory.md), [diferencias](docs/migration/differences.md) y [evidencia de aceptación](docs/migration/acceptance.md).

<!-- BEGIN GENERATED TOOLS -->
## Herramientas disponibles (78)

Versión Python 2.1.0; un prompt weekly-meal-plan y cero resources propios.

### Recetas (26)

`create_recipe`, `delete_recipe`, `duplicate_recipe`, `find_recipes_for_ingredients`, `get_recipe_concise`, `get_recipe_detailed`, `get_recipes`, `get_recipes_batch`, `get_recipes_detailed_batch`, `get_recipes_for_classification`, `get_recipes_for_data_enrichment`, `get_recipes_for_ingredient_parsing`, `mark_recipe_last_made`, `patch_recipe`, `set_recipe_image`, `set_recipe_image_from_file`, `set_recipe_image_from_url`, `set_recipe_rating`, `update_recipe_ingredients`, `update_recipe_ingredients_batch`, `update_recipe_instructions`, `update_recipe_instructions_batch`, `update_recipe_taxonomy`, `update_recipe_taxonomy_batch`, `update_recipe_tools`, `update_recipe_tools_batch`

### Planificación (6)

`create_mealplan`, `create_mealplan_bulk`, `get_all_mealplans`, `get_mealplan_with_recipes`, `get_todays_mealplan`, `patch_mealplan`

### Categorías (7)

`create_category`, `delete_category`, `get_categories`, `get_category`, `get_category_by_slug`, `get_empty_categories`, `update_category`

### Etiquetas (7)

`create_tag`, `delete_tag`, `get_empty_tags`, `get_tag`, `get_tag_by_slug`, `get_tags`, `update_tag`

### Compras (0)



### Alimentos (7)

`create_food`, `delete_food`, `get_food`, `get_food_matches`, `get_foods`, `merge_foods`, `update_food`

### Unidades (6)

`create_unit`, `delete_unit`, `get_unit`, `get_unit_matches`, `get_units`, `update_unit`

### Equipamiento (0)
<!-- END GENERATED TOOLS -->

## Licencia y procedencia

[MIT](LICENSE). Se conserva la licencia y atribución del upstream. Las capturas de contrato y sus referencias identifican el commit original; el runtime Python no ejecuta TypeScript ni Node.
