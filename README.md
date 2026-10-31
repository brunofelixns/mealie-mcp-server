<p align="center">
  <img src="docs/assets/mealie-mcp-banner.png" alt="Un recetario conectado a la planificación semanal, la lista de compra y las herramientas de un asistente" width="1200">
</p>

<h1 align="center">Mealie MCP · Python</h1>

<p align="center">
  Tu recetario, tus menús y tu compra, conectados a tu asistente.
</p>

<p align="center">
  <a href="https://github.com/brunofelixns/mealie-mcp-server/actions/workflows/ci.yaml"><img src="https://github.com/brunofelixns/mealie-mcp-server/actions/workflows/ci.yaml/badge.svg?branch=main" alt="Estado del CI"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.14-3776AB?logo=python&amp;logoColor=white" alt="Python 3.14"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/FastMCP-4.1.4-245348" alt="FastMCP 4.1.4"></a>
  <a href="docs/clients.md"><img src="https://img.shields.io/badge/MCP-2026--07--28-245348" alt="MCP 2026-07-28"></a>
  <a href="#herramientas-disponibles-78"><img src="https://img.shields.io/badge/Herramientas-78-C5653E" alt="78 herramientas"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/Licencia-MIT-C5653E" alt="Licencia MIT"></a>
</p>

<p align="center">
  <a href="#inicio-rápido">Inicio rápido</a> ·
  <a href="#conectar-un-cliente-mcp">Clientes MCP</a> ·
  <a href="#configuración">Configuración</a> ·
  <a href="#herramientas-disponibles-78">Herramientas</a> ·
  <a href="#documentación">Documentación</a>
</p>

Servidor del **Model Context Protocol** para [Mealie](https://github.com/mealie-recipes/mealie), escrito en Python con FastMCP. Ofrece **78 herramientas**, el prompt **`weekly-meal-plan`** y dos formas de conexión: **stdio local** y **Streamable HTTP con Bearer personal**.

Mealie conserva las recetas; el cliente MCP aporta el modelo y utiliza las herramientas para consultar o aplicar cambios. El servidor admite el protocolo **2026-07-28** y clientes de la era **2025-11-25**.

## Qué puedes hacer

| Flujo | Capacidades |
|---|---|
| **Tu recetario** | Buscar por texto, categorías y etiquetas; crear, duplicar y editar recetas. |
| **Una semana organizada** | Proponer un menú con `weekly-meal-plan` y gestionar las entradas del plan. |
| **La compra preparada** | Crear listas, añadir ingredientes y asociar recetas a la compra. |
| **Ingredientes e instrucciones** | Trabajar con alimentos, unidades y referencias; verificar escrituras y restaurar ante fallos cuando corresponda. |
| **Recetas completas** | Gestionar imágenes, equipamiento, valoraciones, favoritos y última preparación. |
| **El cliente que prefieras** | Conexión por stdio o HTTP con credenciales independientes para Mealie y el MCP. |

## Inicio rápido

### Desplegar con Docker

La carpeta **[docker/](docker/README.md)** funciona de forma independiente en el servidor de destino. Configura una versión publicada en GHCR; el Compose descarga la imagen y no necesita construirla ni instalar Python en el host.

```sh
cd docker
cp .env.example .env
# Edita .env antes de continuar.
docker compose pull mealie-mcp
docker compose up --detach --wait --wait-timeout 60 mealie-mcp
```

En PowerShell, sustituye el comando de copia por `Copy-Item .env.example .env`.

Estos son los valores que debes completar en `.env`:

```dotenv
MEALIE_MCP_IMAGE=ghcr.io/brunofelixns/mealie-mcp-server:0.1.0
MEALIE_BASE_URL=https://mealie.example.com
MEALIE_API_KEY=
MCP_AUTH_TOKEN=
MCP_PUBLIC_URL=https://mcp.example.com/mcp
```

La API key y el Bearer deben ser distintos. Genera el Bearer con al menos32 bytes aleatorios; por ejemplo, `openssl rand -hex 32`. El archivo `.env` queda fuera de Git y del contexto de build. La [guía Docker](docker/README.md) explica también el acceso a paquetes privados, las redes y las actualizaciones.

> [!IMPORTANT]
> El servicio HTTP se publica en `127.0.0.1:8000`. Para conectarte desde fuera del host, configura un proxy HTTPS hacia ese puerto y conserva el streaming de MCP. [Ejemplo de proxy](docs/http-deployment.md#tls-y-proxy).

La versión `0.1.0` ya está publicada en GHCR para amd64 y arm64. Para publicar futuras versiones desde tu máquina, consulta la [guía de publicación local](docs/publishing-local.md); también existe el workflow manual de [release](.github/workflows/release.yaml).

### Usar stdio

Desde la misma carpeta `docker/`, con la URL y la API key Mealie configuradas:

```sh
docker compose -f compose.stdio.yaml run --rm --no-deps -T stdio
```

El cliente MCP debe iniciar este proceso y mantener stdin abierto. No añadas TTY. El archivo stdio es independiente: no publica puertos ni recibe el token HTTP.

## Conectar un cliente MCP

### Local por stdio

Ejemplo de configuración para un cliente que acepte `mcpServers`. Adapta las rutas a la carpeta Docker del host:

<details>
<summary>Ver ejemplo de configuración JSON</summary>

```json
{
  "mcpServers": {
    "mealie": {
      "command": "docker",
      "args": [
        "compose",
        "--env-file", "/srv/mealie-mcp/.env",
        "-f", "/srv/mealie-mcp/compose.stdio.yaml",
        "run", "--rm", "--no-deps", "-T", "stdio"
      ]
    }
  }
}
```

</details>

### Remoto por HTTP

En un cliente que permita configurar un Bearer manualmente:

```text
URL: https://mcp.example.com/mcp
Authorization: Bearer <tu-token-personal>
```

El token personal autentica al cliente frente al MCP; la API key Mealie se configura en el servidor. El formato de configuración depende del cliente. Consulta [clientes MCP](docs/clients.md) para más ejemplos y las limitaciones del modo personal.

### Una primera consulta

Selecciona `get_recipes` en tu cliente y usa estos argumentos:

```json
{
  "search": "pasta",
  "page": 1,
  "perPage": 10
}
```

Para preparar un menú, selecciona el prompt `weekly-meal-plan` y utiliza `preferences`, por ejemplo: «Cenas vegetarianas para dos, con ingredientes de temporada». Revisa la propuesta antes de guardar el plan.

## Configuración

### Variables del servidor

| Variable | Valor por defecto | Uso |
|---|---|---|
| `MEALIE_BASE_URL` | Obligatoria | URL de Mealie accesible desde el contenedor; admite subruta. |
| `MEALIE_API_KEY` / `MEALIE_API_KEY_FILE` | Obligatoria | Credencial Mealie como valor o archivo; elegir una sola forma. |
| `MCP_TRANSPORT` | `stdio` | `stdio` o `http`; los argumentos CLI prevalecen. |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8000` | Dirección y puerto internos del servidor HTTP. |
| `MCP_AUTH_TOKEN` / `MCP_AUTH_TOKEN_FILE` | Obligatoria en HTTP | Bearer independiente; mínimo32 caracteres ASCII visibles, sin espacios. Elegir una sola forma. |
| `MCP_PUBLIC_URL` | Sin definir | URL pública; obligatoria con HTTPS cuando `MCP_REQUIRE_HTTPS=true`. |
| `MCP_REQUIRE_HTTPS` | `false` | El Compose de producción lo activa como `true`. TLS termina en el proxy. |
| `MCP_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | Hosts adicionales separados por comas; el host de la URL pública se añade automáticamente. |
| `MCP_ALLOWED_ORIGINS` | Vacío | Orígenes de navegador de confianza separados por comas. |
| `TZ` | `UTC` | Zona horaria para las fechas; por ejemplo, `Europe/Madrid`. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` o `CRITICAL`. |
| `MEALIE_MCP_DEBUG` | `false` | Activa mediciones de tiempos en stderr. |

Compose carga su `.env` y pasa las variables al contenedor. El proceso Python recibe variables explícitas y no carga `.env` automáticamente. Los perfiles Docker seleccionan el transporte mediante argumentos CLI. [Configuración completa](docs/configuration.md).

### Parámetros de Docker Compose

| Variable de `docker/.env` | Valor de la plantilla | Uso |
|---|---|---|
| `MEALIE_MCP_IMAGE` | `ghcr.io/brunofelixns/mealie-mcp-server:0.1.0` | Imagen publicada; permite versión concreta o digest. |
| `COMPOSE_PROJECT_NAME` | `mealie-mcp` | Identifica la instancia Compose. |
| `MCP_BIND_IP` | `127.0.0.1` | Interfaz del host donde se publica HTTP. |
| `MCP_PUBLISHED_PORT` | `8000` | Puerto del host; el puerto interno sigue siendo8000. |

### Argumentos CLI

Desde el Dev Container:

```sh
uv run --frozen mealie-mcp-server --help
uv run --frozen mealie-mcp-server --transport stdio
```

| Argumento | Descripción |
|---|---|
| `--transport stdio\|http` | Selecciona el transporte. |
| `--host HOST` | Cambia la dirección de escucha HTTP. |
| `--port PORT` | Cambia el puerto HTTP. |
| `--log-level NIVEL` | Selecciona el nivel de logs. |
| `--debug` | Activa mediciones de tiempos en stderr. |
| `--version` | Muestra la versión del paquete. |
| `--help` | Muestra la ayuda. |

<!-- BEGIN GENERATED TOOLS -->
## Herramientas disponibles (78)

Catálogo de la versión 0.1.0. Consulta los [esquemas completos](docs/tools.md) y la [cobertura de API](docs/api-coverage.md).

| Familia | Herramientas |
|---|---:|
| Recetas | 26 |
| Planificación | 6 |
| Categorías | 7 |
| Etiquetas | 7 |
| Compras | 13 |
| Alimentos | 7 |
| Unidades | 6 |
| Equipamiento | 6 |
| **Total** | **78** |

<details>
<summary><strong>Recetas</strong> · 26 herramientas</summary>

`create_recipe`, `delete_recipe`, `duplicate_recipe`, `find_recipes_for_ingredients`, `get_recipe_concise`, `get_recipe_detailed`, `get_recipes`, `get_recipes_batch`, `get_recipes_detailed_batch`, `get_recipes_for_classification`, `get_recipes_for_data_enrichment`, `get_recipes_for_ingredient_parsing`, `mark_recipe_last_made`, `patch_recipe`, `set_recipe_image`, `set_recipe_image_from_file`, `set_recipe_image_from_url`, `set_recipe_rating`, `update_recipe_ingredients`, `update_recipe_ingredients_batch`, `update_recipe_instructions`, `update_recipe_instructions_batch`, `update_recipe_taxonomy`, `update_recipe_taxonomy_batch`, `update_recipe_tools`, `update_recipe_tools_batch`

</details>

<details>
<summary><strong>Planificación</strong> · 6 herramientas</summary>

`create_mealplan`, `create_mealplan_bulk`, `get_all_mealplans`, `get_mealplan_with_recipes`, `get_todays_mealplan`, `patch_mealplan`

</details>

<details>
<summary><strong>Categorías</strong> · 7 herramientas</summary>

`create_category`, `delete_category`, `get_categories`, `get_category`, `get_category_by_slug`, `get_empty_categories`, `update_category`

</details>

<details>
<summary><strong>Etiquetas</strong> · 7 herramientas</summary>

`create_tag`, `delete_tag`, `get_empty_tags`, `get_tag`, `get_tag_by_slug`, `get_tags`, `update_tag`

</details>

<details>
<summary><strong>Compras</strong> · 13 herramientas</summary>

`add_recipe_to_shopping_list`, `create_shopping_list`, `create_shopping_list_item`, `create_shopping_list_items_bulk`, `delete_shopping_list`, `delete_shopping_list_item`, `delete_shopping_list_items_bulk`, `get_shopping_list`, `get_shopping_list_items`, `get_shopping_lists`, `remove_recipe_from_shopping_list`, `update_shopping_list`, `update_shopping_list_item`

</details>

<details>
<summary><strong>Alimentos</strong> · 7 herramientas</summary>

`create_food`, `delete_food`, `get_food`, `get_food_matches`, `get_foods`, `merge_foods`, `update_food`

</details>

<details>
<summary><strong>Unidades</strong> · 6 herramientas</summary>

`create_unit`, `delete_unit`, `get_unit`, `get_unit_matches`, `get_units`, `update_unit`

</details>

<details>
<summary><strong>Equipamiento</strong> · 6 herramientas</summary>

`create_tool`, `delete_tool`, `get_tool`, `get_tool_matches`, `get_tools`, `update_tool`

</details>
<!-- END GENERATED TOOLS -->

## Desarrollo

Abrir el repositorio con **Dev Containers: Reopen in Container**. Docker Desktop debe usar contenedores Linux. Python, dependencias, tests y builds se ejecutan dentro del Dev Container.

```sh
uv sync --frozen --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python scripts/generate_docs.py --check
uv run pytest
```

La suite incluye pruebas reales de la imagen runtime: constrúyela primero como indica la [guía de desarrollo](docs/development.md). El generador actualiza el catálogo de este README desde el registro público y conserva el texto manual.

## Documentación

| Necesitas… | Documento |
|---|---|
| Instalar una imagen de GHCR | [Despliegue Docker](docker/README.md) |
| Configurar variables y credenciales | [Configuración](docs/configuration.md) |
| Conectar tu cliente | [Clientes MCP](docs/clients.md) |
| Preparar HTTPS, proxy y acceso remoto | [Despliegue HTTP](docs/http-deployment.md) |
| Construir la imagen o usar secretos de archivo | [Contenedores](docs/containers.md) |
| Consultar parámetros de cada herramienta | [Referencia MCP](docs/tools.md) |
| Conocer módulos y flujos | [Arquitectura](docs/architecture.md) · [Flujos](docs/workflows.md) |
| Revisar la migración y sus resultados | [Aceptación](docs/migration/acceptance.md) · [Diferencias](docs/migration/differences.md) |

[Índice completo de documentación](docs/README.md).

## Calidad y seguridad

El proyecto usa modelos estrictos, pruebas de contrato frente a capturas originales, tests con sockets reales e imágenes instaladas, Ruff y mypy. Las mutaciones verificadas tienen recuperación acotada ante cancelación; consultar el estado de Mealie antes de repetir una escritura cuyo resultado se desconoce.

Para probar las **78 herramientas con Mealie real en Docker**, por stdio y HTTP con Bearer, ejecutar `uv run python -m tests.e2e.runner` dentro del Dev Container. El entorno es local y desechable; los cuatro recorridos y el rechazo de descargas privadas se explican en [pruebas E2E](docs/testing/local-e2e.md).

Para **construir y publicar amd64/arm64 desde tu máquina sin GitHub Actions**, usar `uv run python scripts/publish_local.py` en el Dev Container. Primero valida todo en local; `--publish` habilita la subida a GHCR. [Guía de publicación local](docs/publishing-local.md).

El runtime se prueba con usuario sin privilegios, raíz de solo lectura y ambas arquitecturas; ARM local se verificó mediante emulación. Los resultados medidos están en el [informe de aceptación](docs/migration/acceptance.md). El último escaneo documentado conserva avisos críticos y altos de Debian: consulta [el análisis](docs/migration/evidence/P23-security.md) y sus límites antes de exponer un servicio público.

## Licencia y procedencia

[Licencia MIT](LICENSE). Migración a Python del proyecto de [Timo Reymann](https://github.com/timo-reymann/mealie-mcp-server), con referencia fijada en `d027e1b4a314d781a322f1f91e37840f01464d77`. Se conservan su atribución, licencia y capturas de contrato. Las diferencias intencionadas están [documentadas](docs/migration/differences.md).

La [ilustración de cabecera](docs/assets/README.md) se creó para este repositorio.
