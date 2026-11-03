<p align="center">
  <img src="docs/assets/mealie-mcp-banner.png" alt="A recipe book connected to weekly meal planning, a shopping list, and assistant tools" width="1200">
</p>

<h1 align="center">Mealie MCP · Python</h1>

<p align="center">
  Your recipes, meal plans, and shopping lists, connected to your assistant.
</p>

<p align="center">
  <strong>English</strong> · <a href="docs/README.es.md">Español</a> · <a href="docs/README.md">Documentación en español</a>
</p>

<p align="center">
  <a href="https://github.com/brunofelixns/mealie-mcp-server/actions/workflows/ci.yaml"><img src="https://github.com/brunofelixns/mealie-mcp-server/actions/workflows/ci.yaml/badge.svg?branch=main" alt="CI status"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.14-3776AB?logo=python&amp;logoColor=white" alt="Python 3.14"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/FastMCP-4.1.4-245348" alt="FastMCP 4.1.4"></a>
  <a href="docs/clients.md"><img src="https://img.shields.io/badge/MCP-2026--07--28-245348" alt="MCP 2026-07-28"></a>
  <a href="#available-tools-162"><img src="https://img.shields.io/badge/Tools-162-C5653E" alt="162 tools"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-C5653E" alt="MIT license"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#connect-your-mcp-client">MCP clients</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#available-tools-162">Tools</a> ·
  <a href="#documentation">Documentation</a>
</p>

A **Model Context Protocol server for [Mealie](https://github.com/mealie-recipes/mealie)**, built with Python and FastMCP. Give your assistant access to **162 tools** for recipes, meal planning, and shopping, plus the **`weekly-meal-plan`** prompt. Connect locally over **stdio** or remotely over **Streamable HTTP with a personal Bearer token**.

Mealie stores your recipes; your MCP client supplies the model and uses the tools to read data or make changes. The server supports protocol **2026-07-28** and clients from the **2025-11-25** protocol era.

## What you can do

| Bring your… | Into your assistant |
|---|---|
| **Recipe collection** | Search by text, categories, and tags; create, duplicate, and edit recipes. |
| **Weekly routine** | Draft a menu with `weekly-meal-plan` and manage meal plan entries. |
| **Shopping list** | Create lists, add ingredients, and link recipes to your shopping. |
| **Ingredients and instructions** | Manage foods, units, and references, with write verification and recovery where supported. |
| **Recipe details** | Manage images, equipment, ratings, favorites, and the last-made date. |
| **Preferred MCP client** | Use stdio or HTTP, with separate credentials for Mealie and the MCP endpoint. |

## Quick start

### Deploy with Docker

The **[docker/](docker/README.md)** directory is self-contained: copy it to your server, configure a published GHCR image, and start the service. Compose downloads the image; Python installation and local builds are unnecessary on the deployment host.

```sh
cd docker
cp .env.example .env
# Edit .env before continuing.
docker compose pull mealie-mcp
docker compose up --detach --wait --wait-timeout 60 mealie-mcp
```

In PowerShell, replace the copy command with `Copy-Item .env.example .env`.

Set these values in `.env`:

```dotenv
MEALIE_MCP_IMAGE=ghcr.io/brunofelixns/mealie-mcp-server:latest
MEALIE_BASE_URL=https://mealie.example.com
MEALIE_API_KEY=
MCP_AUTH_TOKEN=
MCP_PUBLIC_URL=https://mcp.example.com/mcp
```

Use different values for the Mealie API key and MCP Bearer token. Generate the Bearer token with at least 32 random bytes, for example with `openssl rand -hex 32`. The `.env` file is excluded from Git and the build context. See the [Docker guide](docker/README.md) for private registry access, networking, and updates.

> [!IMPORTANT]
> HTTP binds to `127.0.0.1:8000`. For access from another machine, place an HTTPS reverse proxy in front of the service and preserve MCP streaming. See the [proxy example](docs/http-deployment.md#tls-y-proxy).

Every push and pull request runs CI on native amd64 and arm64 runners. Successful
changes reach protected `main` through PRs. Official Release Please maintains one release PR with the
next semantic version and accumulated `CHANGELOG`. Merge that PR when ready to publish;
after both native checks pass, CI publishes `X.Y.Z`, `latest`, and `sha-<merge-commit>`
to GHCR, with a Git tag and GitHub Release. Breaking changes increment major,
`feat`/`fix` increment minor, and other commits increment patch.
The dedicated Release Please GitHub App starts the release PR checks automatically;
wait for both checks before merging. App setup is required for a fork.
See [CI and automatic publication](docs/ci.md).

### Run over stdio

From the same `docker/` directory, with your Mealie URL and API key configured:

```sh
docker compose -f compose.stdio.yaml run --rm --no-deps -T stdio
```

Your MCP client must launch this process and keep stdin open. Do not allocate a TTY. The separate stdio Compose file exposes no ports and does not receive the HTTP token.

## Connect your MCP client

### Local connection over stdio

For clients that accept an `mcpServers` configuration, adapt these paths to the Docker directory on your host:

<details>
<summary>Show client configuration</summary>

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

### Remote connection over HTTP

For clients that let you configure a Bearer token manually:

```text
URL: https://mcp.example.com/mcp
Authorization: Bearer <your-personal-token>
```

The personal token authenticates your client to the MCP server. Configure the Mealie API key on the server itself. Client configuration formats vary; see the [MCP client guide](docs/clients.md) for examples and the limits of personal-token mode.

### Try your first query

Select `get_recipes` in your client and use:

```json
{
  "search": "pasta",
  "page": 1,
  "perPage": 10
}
```

To draft a menu, select the `weekly-meal-plan` prompt and set `preferences`, for example: “Vegetarian dinners for two, using seasonal ingredients.” Review the suggestion before saving the plan.

## Skills: served by MCP or installed manually

The portable **`mealie` skill** guides recipe maintenance, meal planning, and
shopping. Source builds serve it through the official
`io.modelcontextprotocol/skills` extension: discover it with `skills/list` or
`skills/get`, then read `skill://mealie/SKILL.md` and its references through
`resources/read`. The client controls activation; support varies by client.

You can also copy **[`skills/mealie/`](skills/mealie/SKILL.md)** into your client's
local skills directory and configure the MCP separately. Both methods use the
same files. See the **[English installation guide](skills/README.md)** or
**[guía completa en español](docs/skills.md)**. Skills are included in the runtime
published by [CI](docs/ci.md).

## Configuration

### Server environment variables

| Variable | Default | Purpose |
|---|---|---|
| `MEALIE_BASE_URL` | Required | Mealie URL reachable from the container; subpaths are supported. |
| `MEALIE_API_KEY` / `MEALIE_API_KEY_FILE` | Required | Mealie credential as a value or file; choose one source. |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http`; CLI arguments take precedence. |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8000` | Internal HTTP bind address and port. |
| `MCP_AUTH_TOKEN` / `MCP_AUTH_TOKEN_FILE` | Required for HTTP | Separate Bearer token; at least 32 visible ASCII characters, without spaces. Choose one source. |
| `MCP_PUBLIC_URL` | Unset | Public URL; required and must use HTTPS when `MCP_REQUIRE_HTTPS=true`. |
| `MCP_REQUIRE_HTTPS` | `false` | Production Compose enables it; TLS terminates at the proxy. |
| `MCP_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | Additional comma-separated hosts; the public URL host is added automatically. |
| `MCP_ALLOWED_ORIGINS` | Empty | Comma-separated trusted browser origins. |
| `TZ` | `UTC` | Time zone for date handling, for example `Europe/Madrid`. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |
| `MEALIE_MCP_DEBUG` | `false` | Enables timing diagnostics on stderr. |

Compose loads `.env` and passes variables to the container. The Python process reads explicit environment variables and does not load `.env` automatically. Docker configurations select the transport through CLI arguments. See the [full configuration guide](docs/configuration.md).

### Docker Compose settings

| Variable in `docker/.env` | Template value | Purpose |
|---|---|---|
| `MEALIE_MCP_IMAGE` | `ghcr.io/brunofelixns/mealie-mcp-server:latest` | Latest published release; also accepts a version, commit tag, or digest. |
| `COMPOSE_PROJECT_NAME` | `mealie-mcp` | Compose project name. |
| `MCP_BIND_IP` | `127.0.0.1` | Host interface for HTTP. |
| `MCP_PUBLISHED_PORT` | `8000` | Host port; the internal port remains `8000`. |

### CLI arguments

Inside the Dev Container:

```sh
uv run --frozen mealie-mcp-server --help
uv run --frozen mealie-mcp-server --transport stdio
```

| Argument | Purpose |
|---|---|
| `--transport stdio\|http` | Select the transport. |
| `--host HOST` | Set the HTTP bind address. |
| `--port PORT` | Set the HTTP port. |
| `--log-level LEVEL` | Set the logging level. |
| `--debug` | Enable timing diagnostics on stderr. |
| `--version` | Print the package version. |
| `--help` | Show CLI help. |

Recipe editing, native import/export and limits: [recipe guide](docs/recipes.md) (Spanish).

<!-- BEGIN GENERATED TOOLS -->
## Available tools (162)

Catalog for version 0.2.0. See the [full schemas](docs/tools.md) and [API coverage](docs/api-coverage.md) (in Spanish). <!-- x-release-please-version -->

| Family | Tools |
|---|---:|
| Recipes | 95 |
| Meal planning | 21 |
| Categories | 7 |
| Tags | 7 |
| Shopping lists | 13 |
| Foods | 7 |
| Units | 6 |
| Equipment | 6 |
| **Total** | **162** |

<details>
<summary><strong>Recipes</strong> · 95 tools</summary>

`add_recipe_note`, `create_cookbook`, `create_recipe`, `create_recipe_action`, `create_recipe_asset_from_url`, `create_recipe_comment`, `create_recipe_share_link`, `create_recipe_timeline_event`, `delete_cookbook`, `delete_recipe`, `delete_recipe_action`, `delete_recipe_comment`, `delete_recipe_note`, `delete_recipe_share_link`, `delete_recipe_timeline_event`, `delete_recipes_bulk`, `download_recipe_asset`, `download_recipe_bulk_export`, `download_recipe_image`, `download_recipe_timeline_image`, `download_shared_recipe`, `duplicate_recipe`, `export_recipe`, `export_recipes_bulk`, `find_recipes_for_ingredients`, `get_cookbook`, `get_cookbooks`, `get_recipe_action`, `get_recipe_actions`, `get_recipe_assets`, `get_recipe_bulk_exports`, `get_recipe_comment`, `get_recipe_comments`, `get_recipe_concise`, `get_recipe_detailed`, `get_recipe_export_formats`, `get_recipe_favorites`, `get_recipe_household`, `get_recipe_import_report`, `get_recipe_import_reports`, `get_recipe_notes`, `get_recipe_ratings`, `get_recipe_share_link`, `get_recipe_share_links`, `get_recipe_suggestions`, `get_recipe_timeline`, `get_recipe_timeline_event`, `get_recipes`, `get_recipes_batch`, `get_recipes_detailed_batch`, `get_recipes_for_classification`, `get_recipes_for_data_enrichment`, `get_recipes_for_ingredient_parsing`, `get_shared_recipe`, `import_recipe_from_html_or_json`, `import_recipe_from_html_or_json_with_progress`, `import_recipe_from_url`, `import_recipe_from_url_with_progress`, `import_recipe_from_zip`, `import_recipe_with_ai`, `import_recipe_with_ai_with_progress`, `import_recipes_from_urls`, `list_recipe_comments`, `mark_recipe_last_made`, `parse_recipe_ingredient`, `parse_recipe_ingredients`, `patch_recipe`, `preview_recipe_from_url`, `purge_recipe_bulk_exports`, `search_recipes`, `set_recipe_image`, `set_recipe_image_from_file`, `set_recipe_image_from_url`, `set_recipe_rating`, `set_recipe_timeline_event_image`, `trigger_recipe_action`, `update_cookbook`, `update_food_substitutions`, `update_recipe_action`, `update_recipe_comment`, `update_recipe_ingredient_substitutions`, `update_recipe_ingredients`, `update_recipe_ingredients_batch`, `update_recipe_instruction_durations`, `update_recipe_instructions`, `update_recipe_instructions_batch`, `update_recipe_metadata`, `update_recipe_metadata_batch`, `update_recipe_note`, `update_recipe_taxonomy`, `update_recipe_taxonomy_batch`, `update_recipe_timeline_event`, `update_recipe_tools`, `update_recipe_tools_batch`, `upload_recipe_asset`

</details>

<details>
<summary><strong>Meal planning</strong> · 21 tools</summary>

`create_mealplan`, `create_mealplan_bulk`, `create_mealplan_entry`, `create_mealplan_rule`, `create_random_mealplan_entry`, `delete_mealplan_entry`, `delete_mealplan_ical_token`, `delete_mealplan_rule`, `get_all_mealplans`, `get_mealplan_entry`, `get_mealplan_ical_feed`, `get_mealplan_ical_token`, `get_mealplan_rule`, `get_mealplan_rules`, `get_mealplan_with_recipes`, `get_todays_mealplan`, `list_mealplan_entries`, `patch_mealplan`, `rotate_mealplan_ical_token`, `update_mealplan_entry`, `update_mealplan_rule`

</details>

<details>
<summary><strong>Categories</strong> · 7 tools</summary>

`create_category`, `delete_category`, `get_categories`, `get_category`, `get_category_by_slug`, `get_empty_categories`, `update_category`

</details>

<details>
<summary><strong>Tags</strong> · 7 tools</summary>

`create_tag`, `delete_tag`, `get_empty_tags`, `get_tag`, `get_tag_by_slug`, `get_tags`, `update_tag`

</details>

<details>
<summary><strong>Shopping lists</strong> · 13 tools</summary>

`add_recipe_to_shopping_list`, `create_shopping_list`, `create_shopping_list_item`, `create_shopping_list_items_bulk`, `delete_shopping_list`, `delete_shopping_list_item`, `delete_shopping_list_items_bulk`, `get_shopping_list`, `get_shopping_list_items`, `get_shopping_lists`, `remove_recipe_from_shopping_list`, `update_shopping_list`, `update_shopping_list_item`

</details>

<details>
<summary><strong>Foods</strong> · 7 tools</summary>

`create_food`, `delete_food`, `get_food`, `get_food_matches`, `get_foods`, `merge_foods`, `update_food`

</details>

<details>
<summary><strong>Units</strong> · 6 tools</summary>

`create_unit`, `delete_unit`, `get_unit`, `get_unit_matches`, `get_units`, `update_unit`

</details>

<details>
<summary><strong>Equipment</strong> · 6 tools</summary>

`create_tool`, `delete_tool`, `get_tool`, `get_tool_matches`, `get_tools`, `update_tool`

</details>
<!-- END GENERATED TOOLS -->

## Development

Open this repository with **Dev Containers: Reopen in Container** and Docker Desktop set to Linux containers. Run Python, dependency installation, tests, and builds inside the Dev Container.

```sh
uv sync --frozen --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python scripts/generate_docs.py --check
uv run pytest
```

The suite includes tests against the real runtime image: build it first as described in the [development guide](docs/development.md). The documentation generator updates the tool catalog in both README languages from the public registry while preserving the surrounding text.

## Documentation

**[Read this guide in Spanish](docs/README.es.md)** · **[Browse all Spanish documentation](docs/README.md)**

The detailed guides, tool schemas, and migration evidence below are maintained in Spanish.

| I want to… | Read |
|---|---|
| Deploy a published GHCR image | [Docker deployment](docker/README.md) |
| Configure variables and credentials | [Configuration](docs/configuration.md) |
| Connect an MCP client | [MCP clients](docs/clients.md) |
| Run CI and publish verified images automatically | [CI and GHCR](docs/ci.md) |
| Use skills over MCP or install them manually | [Skills guide](skills/README.md) · [Español](docs/skills.md) |
| Set up HTTPS and remote access | [HTTP deployment](docs/http-deployment.md) |
| Build the image or use file-based secrets | [Containers](docs/containers.md) |
| Look up tool parameters | [MCP reference](docs/tools.md) |
| Use recipe notes, files and Mealie 3.30 features | [Recipe editing](docs/recipes.md) · [Mealie 3.30](docs/mealie-3.30.md) |
| Understand modules and workflows | [Architecture](docs/architecture.md) · [Workflows](docs/workflows.md) |
| Review migration results and compatibility | [Acceptance](docs/migration/acceptance.md) · [Intentional differences](docs/migration/differences.md) |

## Quality and security

The project uses strict models, contract tests against original snapshots, real-socket and installed-image tests, Ruff, and mypy. Verified mutations have bounded cancellation recovery. Check the current Mealie state before repeating a write whose outcome is unknown.

To test **all 162 tools against real Mealie in Docker**, over stdio and Bearer-authenticated HTTP, run `uv run python -m tests.e2e.runner` inside the Dev Container. The environment is local and disposable. The [E2E guide](docs/testing/local-e2e.md) describes the four runs and private-download rejection checks.

The [CI workflow](.github/workflows/ci.yaml) runs the full suite, real disposable
Mealie integration, compatibility checks, and image scanning before publication.
It uploads the exact tested images without rebuilding. See the [CI guide](docs/ci.md)
for tags, permissions, evidence, and recovery.

The runtime is tested as a non-root user, with a read-only root filesystem and both architectures; local ARM verification used emulation. Measured results and their limits are recorded in the [acceptance report](docs/migration/acceptance.md). The last documented scan retains critical and high Debian advisories; review the [image security analysis](docs/migration/evidence/P23-security.md) and its limits before exposing a public service.

## Contributing and reporting issues

Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [code of conduct](CODE_OF_CONDUCT.md).
Use the issue templates for bugs and feature requests. Report vulnerabilities
privately using the process in [SECURITY.md](SECURITY.md).

## License and credits

[MIT license](LICENSE). This is a Python migration of [Timo Reymann's original project](https://github.com/timo-reymann/mealie-mcp-server), pinned to `d027e1b4a314d781a322f1f91e37840f01464d77`. Its attribution, license, and contract snapshots are preserved. See the documented [intentional differences](docs/migration/differences.md).

The [header illustration](docs/assets/README.md) was created for this repository.
