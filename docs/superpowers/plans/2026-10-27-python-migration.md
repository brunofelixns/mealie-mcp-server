# Mealie MCP Python Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for sequential native execution, or superpowers:subagent-driven-development if the user chooses delegation. Execute task-by-task and track steps with checkboxes. Do not start implementation in this planning turn.

**Goal:** Migrar completamente el upstream fijado a Python, conservar sus 78 herramientas y un prompt, y entregar stdio, HTTP Bearer, Dev Container e imagen de producción verificados.

**Architecture:** Un catálogo FastMCP y servicios deterministas comparten un cliente Mealie asíncrono. El proceso elige stdio o HTTP; la misma imagen soporta ambos comandos. El TypeScript original se ejecuta solo como referencia temporal y queda fuera del producto final.

**Tech Stack:** Python 3.14, FastMCP 4.1.4, SDK mcp 2.3.0, Pydantic 2, HTTPX2, uv, hatchling, Ruff, mypy, pytest y Docker.

**Spec:** [Diseño completo](../specs/2026-10-27-python-migration-design.md). Leer también [inventario](../../migration/compatibility-inventory.md) e [inventario JSON](../../migration/compatibility-inventory.json).

Fecha: 2026-10-27. Estado: implementación autorizada; P01..P11 verificadas y P12 en curso. Ver implementation-state.json para la evidencia. No se ha publicado ni desplegado un endpoint público.

## Global Constraints

- Referencia inmutable: d027e1b4a314d781a322f1f91e37840f01464d77; 78 herramientas, un prompt, cero resources registrados.
- Conservar nombres, camelCase público, omisión/null/0/false/[], errores y efectos. Inputs declarados estrictos; payloads Mealie conservan campos ajenos.
- CPython 3.14; resolver FastMCP 4.1.4/mcp 2.3.0 y fijar versiones/digests reales en P02. Sin usar main/latest como dependencia.
- Toda instalación, ejecución Python/Node, tests y builds dentro de contenedores. El host permite edición y launcher Docker para el bootstrap de P01; no ejecutar la aplicación en el host.
- stdio por defecto; HTTP en /mcp:8000 con Bearer independiente de MEALIE_API_KEY; un proceso y un transporte, un worker HTTP inicial.
- stdout solo JSON-RPC en stdio; logs a stderr, sin secretos, cuerpos de recetas ni URLs firmadas.
- Cliente: connect5/read30/write30/pool5 segundos, pool20; detalle concurrente4; escritores concurrentes5 donde original lo define.
- Lotes de ingredientes/instrucciones/equipamiento de recetas:1..25. No imponer ese máximo al lote de taxonomía que no lo declara.
- Colas default25/max50; cursor v1 con createdAt/id y página50; auditoría20s, lotes de detalle20.
- Descargador file:10 MiB/30s totales/3 redirecciones; DNS fijado por salto, Host/SNI/TLS originales y rechazo de IP privadas. Mealie privado configurado sigue válido.
- Imagen no root, filesystem read-only compatible, sin Node/devtools/secrets; stdio sin TTY y healthcheck solo en HTTP; stop_grace_period45s.
- TZ UTC por defecto; probar también Europe/Madrid. Sin OpenAI API, OAuth, multiusuario, base de datos propia o nuevas herramientas por iniciativa de la migración.
- Preservar MIT y procedencia; retirar código/infraestructura JS propia al cerrar. No publicar al upstream.
- Aceptación:78 casos MCP positivos y78 rechazos como mínimo, escenarios profundos obligatorios, >=90% líneas y >=85% ramas; ambos transportes, ambas eras y ambas arquitecturas documentadas.
- Un fallo de baseline no se corrige ocultamente; una diferencia intencionada se registra antes de modificar expectativas.
- No se marca una tarea completada porque esté escrita: exige pruebas, evidencia y revisión de sus límites.

## Review Focus

1. Bootstrap circular: abrir el Dev Container sin uv.lock y sin ejecutar Python en el host; P01/P02 prueban apertura inicial y reinstalación frozen.
2. Cambio de namespace/red: Mealie en host/subruta o Docker, sin filtrar Authorization a otro origen; P05 prueba URL base con subruta y redirects, P23 prueba red real.
3. Desconexión tras una escritura: no duplicar ni dejar sin verificar silenciosamente; P16/P17/P22 prueban cancelación antes/después del PATCH y cleanup acotado.
4. Payloads legítimos grandes:10 MiB binarios más overhead base64, límites32 MiB y tamaño de eventos SSE del cliente; P18/P22/P23 prueban borde y streaming.
5. Aislamiento de identidad y tiempo: dos instancias/configuraciones no comparten self-user cache ni asumen TZ del host; P06/P19 prueban aislamiento y DST Madrid/UTC.

---

## Cómo seguir el plan

Recomendación de ejecución: secuencial en este chat, con una tarea activa y una revisión de fase antes de avanzar. Los contratos compartidos y la paridad hacen conveniente cerrar primero las interfaces. La delegación es una alternativa que se elegirá al revisar el plan; no se lanzan agentes por defecto ni se ejecutan tareas de este documento ahora.

Leer el diseño y el inventario antes de cada familia. En cada tarea funcional: añadir primero las pruebas de comportamiento, ejecutar y observar un fallo relevante, implementar lo mínimo, verificar y registrar evidencia. No aceptar un fallo por entorno roto como el RED de una función. Para configuración de bajo impacto se usan checks reales de entorno/build en lugar de tests que repitan el archivo de configuración.

P03 define los casos de contrato; P06 añade **assert_contract_matches(server: FastMCP, case: ContractCase, fake: FakeMealie) -> None** en tests/support/contracts.py. La aserción comprueba método/ruta/query/body y respuesta completa, incluidos isError y ausencia de llamadas en rechazos de input. Solo campos volátiles identificados por caso pueden normalizarse; no borrar IDs/errores/listas para hacer pasar la comparación.

Las pruebas que lanzan contenedores hermanos usan una red Compose común para MCP/fake Mealie y artefactos por build context, volumen nombrado o docker cp. El daemon externo no conoce automáticamente una ruta /workspaces interna del Dev Container: no usar ese path como bind mount del host. Probar esta topología con una llamada real al fake en P03 y con la imagen final en P23.

Cada herramienta lleva un modelo público <PascalCaseDelNombre>Input, con aliases exactos del inventario, y un handler del mismo nombre MCP. Cada módulo expone su register_*(server: FastMCP) -> None; get_state(ctx) resuelve el cliente en lifespan. Los servicios no reciben Context ni conocen el transporte. JsonValue se importa de Pydantic; JsonObject y UnsetType se definen en P04. No introducir un despachador genérico que cambie esquemas o envuelva respuestas.

Los paths de cada tarea son futuros salvo los docs ya existentes. Los consumidores de herramientas aún no migradas no se publican; un catálogo parcial solo sirve al desarrollo.

## Fases y puntos de revisión

| Fase | Tareas en orden | Resultado verificable antes de continuar |
|---|---|---|
| F1 Entorno y contratos | P01..P06 | Dev Container reproducible, baseline real, cliente y factory sin negocio publicado. |
| F2 Vocabularios y operaciones base | P07..P14 | Matching, organizadores, compras, recetas básicas y planes pasan su corpus. |
| F3 Flujos de recetas | P15..P19 | Cursores, ingredientes, instrucciones, imágenes y ratings preservan los contratos delicados. |
| F4 MCP utilizable | P20..P22 | Catálogo78+prompt, CLI stdio y HTTP autenticado con protocolos modernos/anteriores. |
| F5 Producción y cierre | P23..P24 | Imagen final probada, integración Mealie desechable, docs y aceptación completas. |

No hay estimaciones de fechas inventadas. El ritmo se medirá por tareas cerradas y evidencia. Si cambia un contrato, primero actualizar diseño/inventario/diferencias y las tareas afectadas.

## Estructura y responsabilidades

El árbol de archivos definitivo está en el diseño, sección5. Este plan concreta además:

| Archivos | Responsabilidad |
|---|---|
| .devcontainer/* y Dockerfile:development | Herramientas y workspace Linux; no secretos incorporados. |
| tests/reference/* | Runner TS congelado, temporal y aislado. |
| tests/support/{fake_mealie,contracts}.py | Fake determinista, corpus y aserciones de requests/resultados. |
| tests/fixtures/compatibility/* | Snapshots/versiones/casos con procedencia y sin credenciales. |
| config.py, models/common.py | Settings, transporte, presencia de campos y tipos JSON comunes. |
| mealie/client.py, mealie/errors.py, mealie/api/* | HTTP, normalizaciones y métodos REST; no decisiones de LLM. |
| services/* y support/* | Algoritmos de dominio y utilidades, independientes de MCP. |
| tools/*, prompts.py, resources/server-instructions.md | Contrato MCP explícito, prompt e instrucciones empaquetadas. |
| server.py, cli.py, auth.py, health.py | Lifecycle, transportes, autenticación y salud. |
| scripts/{generate_docs,check_compatibility}.py | Documentación y control de paridad; sin runtime JS permanente. |
| compose.production.yaml y workflows | Imagen ejecutable, smoke/CI y publicación condicionada. |
| [Estado de ejecución](../../migration/implementation-state.json) | Fuente de estado por tarea, dependencias, propietario de cada herramienta y evidencias. |
| [Avance](../../migration/progress.md) | Vista legible del orden y reglas de cierre. |
| [Aceptación](../../migration/acceptance.md) | Informe de resultados, aún vacío; no confundir plan con prueba. |

## Tareas ejecutables

<a id="p01"></a>
### P01: Arrancar el Dev Container sin depender de un lock inexistente

**Depende de:** ninguna. **Estado:** verificada; ver registro de ejecución.

**Archivos:** `.devcontainer/devcontainer.json`, `.devcontainer/compose.yaml`, `Dockerfile`, `.dockerignore`, `.gitignore`, `docs/development.md`.

**Interfaces:** consume Docker Desktop con contenedores Linux y la carpeta actual con docs preservada. Produce Target development utilizable sin pyproject ni uv.lock; usuario no root, Python 3.14 y Docker CLI con daemon externo. Repositorio Git basado en el upstream fijado con docs preservada; no se fuerza checkout sobre trabajo ajeno.

- [x] **1. Preparar el bootstrap conservando docs y el historial fijado.** Comprobar estado Git/archivos antes de importar fuentes; no sobreescribir trabajo ajeno. Después crear los archivos de entorno descritos.
- [x] **2. Reabrir en Dev Container y ejecutar las comprobaciones reales.** Reabrir desde cero; python --version informa 3.14.x; id -u no es 0; docker version conecta al daemon; .venv usa volumen Linux; puerto 8000 privado. El arranque inicial no ejecuta uv sync --frozen si todavía no existe uv.lock. Antes de crear Dockerfile, incorporar el historial upstream fijado a una rama local migration/python mediante un contenedor Git auxiliar, preservando docs. El launcher Docker y la edición de archivos son el bootstrap del host; ningún comando Python/Node de la aplicación se ejecuta en el host. Leer instrucciones de repositorio tras incorporar fuentes; no configurar origin ni hacer push.

- [x] **3. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
docker compose -f .devcontainer/compose.yaml config
python --version
id -u
docker version
```

- [x] **4. Revisar, documentar y cerrar.** Entrar en el Dev Container limpio y verificar requisitos reales. No escribir tests que solo repitan la configuración. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `chore: bootstrap reproducible Python dev container`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p02"></a>
### P02: Fijar paquete, dependencias y checks Python

**Depende de:** P01. **Estado:** verificada; ver registro de ejecución.

**Archivos:** `pyproject.toml`, `uv.lock`, `.python-version`, `src/mealie_mcp_server/__init__.py`, `tests/conftest.py`, `.github/workflows/ci.yaml`, `docs/development.md`.
**Tests:** `tests/unit/test_package_metadata.py`.

**Interfaces:** consume Dev Container P01. Produce Paquete mealie_mcp_server con version() -> str; build hatchling; uv.lock fijado; comandos Ruff/mypy/pytest disponibles dentro del contenedor.

- [x] **1. Añadir las pruebas antes del código funcional.** test_package_version_matches_metadata: assert version() == importlib.metadata.version('mealie-mcp-server'). Verificar import desde wheel instalado fuera del source tree. Aún no crear una CLI operativa ni afirmar que existe un servidor.
- [x] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [x] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. Resolver FastMCP 4.1.4 y mcp 2.3.0 compatibles con Python 3.14; fijar uv/base image reales. Crear lock dentro del Dev Container y después activar postCreateCommand uv sync --frozen --group dev. CI usa el mismo entorno y no permite publicar todavía.

- [x] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv lock
uv sync --frozen --group dev
uv run pytest tests/unit/test_package_metadata.py -q
uv run ruff check .
uv run mypy src
uv build
```

- [x] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `build: add locked Python package and container checks`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p03"></a>
### P03: Capturar la referencia original y el corpus de compatibilidad

**Depende de:** P02. **Estado:** verificada; ver registro de ejecución.

**Archivos:** `tests/reference/Dockerfile`, `tests/reference/compose.yaml`, `tests/fixtures/compatibility/upstream-manifest.json`, `tests/fixtures/compatibility/catalog.json`, `tests/fixtures/compatibility/prompts.json`, `tests/fixtures/compatibility/instructions.txt`, `tests/fixtures/compatibility/cases/`, `tests/support/fake_mealie.py`, `tests/support/contracts.py`, `scripts/capture_reference.py`, `docs/migration/baseline.md`.
**Tests:** `tests/contracts/test_reference_catalog.py`.

**Interfaces:** consume Commit upstream d027e1b4a314d781a322f1f91e37840f01464d77 e inventario de 78 nombres. Produce FakeMealie(scenario: str) con server_url y recorded_requests; load_cases(family: str) -> list[ContractCase]; ContractCase contiene tool, arguments, scenario, expected_requests, expected_result. Runner TS aislado y temporal.

- [x] **1. Añadir las pruebas antes del código funcional.** test_reference_catalog: assert len(catalog.tools) == 78; assert prompts == ['weekly-meal-plan']; capturar capability/error de resources y confirmar cero recursos registrados sin fabricar una respuesta []; assert file_tool.meta == {'openai/fileParams':['file']}. Ejecutar la suite original y registrar resultado, incluidas fallas reales; no inventar éxito. Capturar ausencia de outputSchema como ausencia observada.
- [x] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [x] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. Identificar hashes/SDK/Node/lock y snapshots; catálogo/prompt/instrucciones completos. Los casos de comportamiento se amplían en cada familia antes de portarla. El fake no conoce credenciales ni datos reales.

- [x] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
docker compose -f tests/reference/compose.yaml build
uv run python scripts/capture_reference.py --commit d027e1b4a314d781a322f1f91e37840f01464d77
uv run pytest tests/contracts/test_reference_catalog.py -q
```

- [x] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `test: capture pinned upstream MCP baseline`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p04"></a>
### P04: Configurar entorno, secretos y presencia de campos

**Depende de:** P03. **Estado:** verificada; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/config.py`, `src/mealie_mcp_server/models/common.py`, `.env.example`, `docs/configuration.md`.
**Tests:** `tests/unit/test_config.py`, `tests/unit/test_field_presence.py`.

**Interfaces:** consume Metadata del paquete P02; contratos fuente P03. Produce Settings; load_settings(environ: Mapping[str,str], overrides: Mapping[str,object] | None = None) -> Settings; Transport = Literal['stdio','http']; class UnsetType y su singleton UNSET; JsonObject = dict[str,JsonValue] (JsonValue de Pydantic).

- [x] **1. Añadir las pruebas antes del código funcional.** test_stdio_needs_only_mealie_credentials: assert settings.transport == 'stdio'. test_http_requires_own_token: HTTP sin token falla; API key Mealie no lo sustituye. test_secret_file_conflicts y test_unknown_fields_and_presence: omitido != None, 0, False, []; los campos de entorno ajenos no rompen Settings. Nunca repr/log de un SecretStr en claro.
- [x] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [x] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. URL sin barras finales; http(s) privado válido para Mealie; *_FILE mutuamente excluyente; UTC default; overrides CLI > entorno; sin I/O Mealie ni lectura de secretos al importar módulos. Solo los secretos requeridos por el transporte activo se validan.

- [x] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_config.py tests/unit/test_field_presence.py -q
```

- [x] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: add transport-aware settings and secret loading`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p05"></a>
### P05: Implementar el cliente Mealie y las utilidades HTTP

**Depende de:** P04. **Estado:** verificada; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/mealie/client.py`, `src/mealie_mcp_server/mealie/errors.py`, `src/mealie_mcp_server/support/query_filter.py`, `src/mealie_mcp_server/support/concurrency.py`.
**Tests:** `tests/unit/test_client.py`, `tests/unit/test_path_segments.py`, `tests/unit/test_query_filter.py`, `tests/unit/test_concurrency.py`.

**Interfaces:** consume Settings, JsonObject y UNSET de P04; FakeMealie de P03. Produce MealieClient async context manager; request(method: str, path: str, *, params: list[tuple[str,str]] | None = None, json: JsonValue | UnsetType = UNSET, data: Mapping[str,str] | None = None, files: Mapping[str,tuple[str,bytes,str]] | None = None) -> JsonValue; MealieApiError(status: int, safe_message: str); encode_path_segment(value: str) -> str; async map_with_concurrency(items: Sequence[T], limit: int, fn: Callable[[T],Awaitable[R]]) -> list[R].

- [x] **1. Añadir las pruebas antes del código funcional.** test_repeated_query_and_csv: assert URL para tags contiene dos claves; csv solo en endpoints indicados. test_204_and_json_string: assert response_204 is None y slug JSON sigue siendo string. test_rejects_traversal rechaza '/', '\\', '.', '..', vacío. test_pool_shutdown_and_write_timeout: no retry de escritura; max_inflight <= 4; orden de salida igual a entrada. Preservar subruta de MEALIE_BASE_URL.
- [x] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [x] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. Bearer Mealie solo al origen configurado; TLS; timeouts 5/30/30/5 s y pool 20; no seguir redirecciones a otro origen con credenciales; binarios multipart sin Content-Type JSON; errores seguros y pool cerrado una vez.

- [x] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_client.py tests/unit/test_path_segments.py tests/unit/test_query_filter.py tests/unit/test_concurrency.py -q
```

- [x] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: add bounded async Mealie client`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p06"></a>
### P06: Crear la factory MCP y el adaptador de contratos

**Depende de:** P05. **Estado:** verificada; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/server.py`, `src/mealie_mcp_server/tools/registry.py`, `src/mealie_mcp_server/tools/helpers.py`, `src/mealie_mcp_server/models/inputs/base.py`, `src/mealie_mcp_server/models/results/base.py`, `tests/support/contracts.py`.
**Tests:** `tests/unit/test_server_lifespan.py`, `tests/contracts/test_strict_inputs.py`, `tests/contracts/test_result_adapter.py`.

**Interfaces:** consume Settings y MealieClient; corpus P03. Produce AppState(settings: Settings, client: MealieClient); create_server(settings: Settings, *, client_factory: Callable[[],AbstractAsyncContextManager[MealieClient]] | None = None) -> FastMCP; get_state(ctx: Context) -> AppState; register_all_tools(server: FastMCP) -> None; ToolInput base extra='forbid'; success_result(data: JsonValue) -> CallToolResult; error_result(error: Exception) -> CallToolResult.

- [x] **1. Añadir las pruebas antes del código funcional.** test_nested_unknown_key_never_calls_upstream: assert recorded_requests == []. test_no_import_side_effects: construir/importar no llama Mealie. test_lifespan_isolated_clients: dos settings no comparten cachés. test_result_adapter_preserves_strings_arrays_and_null: no wrapper nuevo que altere resultados; text e isError como baseline. Tests sintéticos locales no se publican como herramientas reales.
- [x] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [x] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. Lifecycle en ambos transportes preparado; aliases camelCase; campos abiertos originales siguen abiertos. El catálogo parcial es explícito durante desarrollo y no se etiqueta como completo.

- [x] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_server_lifespan.py tests/contracts/test_strict_inputs.py tests/contracts/test_result_adapter.py -q
```

- [x] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: add MCP factory and strict contract adapter`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p07"></a>
### P07: Portar candidatos y consultas agrupadas

**Depende de:** P06. **Estado:** verificada; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/services/candidate_matching.py`, `src/mealie_mcp_server/services/multi_query_lookup.py`.
**Tests:** `tests/unit/test_candidate_matching.py`, `tests/unit/test_multi_query_lookup.py`.

**Interfaces:** consume MealieClient y map_with_concurrency de P05. Produce classify_and_rank(query: str, candidates: list[JsonObject], fields: list[str]) -> list[JsonObject]; lookup_candidates(client: MealieClient, kind: Literal['food','unit','tool'], queries: list[str], max_matches: int | None = None) -> JsonObject.

- [x] **1. Añadir las pruebas antes del código funcional.** test_exact_precedes_substring_and_aliases; test_duplicate_queries_preserve_positions; test_lookup_limits: 1..25 queries, longitud <=200, maxMatches default10/cap25, chunks10, pool200, requests concurrentes4; assert results conserva una entrada por consulta incluso repetida. No elegir canónico ni crear entidades.
- [x] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [x] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. Orden y desempates reproducen baseline, incluyendo Unicode, blancos, aliases y queries con caracteres de filtros escapados.

- [x] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_candidate_matching.py tests/unit/test_multi_query_lookup.py -q
```

- [x] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port deterministic candidate matching`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p08"></a>
### P08: Migrar categorías y etiquetas

**Depende de:** P07. **Estado:** verificada; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/mealie/api/categories.py`, `src/mealie_mcp_server/mealie/api/tags.py`, `src/mealie_mcp_server/models/inputs/categories.py`, `src/mealie_mcp_server/models/inputs/tags.py`, `src/mealie_mcp_server/tools/categories.py`, `src/mealie_mcp_server/tools/tags.py`, `src/mealie_mcp_server/services/organizer_resolution.py`, `tests/fixtures/compatibility/cases/categories_tags.json`.
**Tests:** `tests/contracts/test_categories_tags.py`, `tests/unit/test_organizer_resolution.py`.

**Interfaces:** consume P05/P06 y corpus load_cases P03. Produce register_categories(server: FastMCP) -> None; register_tags(server: FastMCP) -> None; resolve_organizer_values(client: MealieClient, kind: str, values: list[str], *, create_missing: bool = False) -> ResolveResult (resolved/created/missing).

**Herramientas (14):** `get_categories`, `get_empty_categories`, `create_category`, `get_category`, `get_category_by_slug`, `update_category`, `delete_category`, `get_tags`, `get_empty_tags`, `create_tag`, `get_tag`, `get_tag_by_slug`, `update_tag`, `delete_tag`.

- [x] **1. Añadir las pruebas antes del código funcional.** test_categories_tags_contract parametrizado por 14 herramientas: comparar REST/result/isError con baseline y rechazar unknown key antes de REST. test_delete_in_use conserva rechazo Mealie. test_empty_endpoints_and_slug separa empty/slug/id. No añadir search ausente. Caracterizar 204 y registrar cualquier corrección.
- [x] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [x] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 14 nombres exactos y dos casos MCP por cada uno; resolver nombre/slug/ID sin creación implícita; preservación de errores.

- [x] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/contracts/test_categories_tags.py tests/unit/test_organizer_resolution.py -q
```

- [x] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port category and tag tools`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p09"></a>
### P09: Migrar alimentos y unidades

**Depende de:** P08. **Estado:** verificada; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/mealie/api/foods.py`, `src/mealie_mcp_server/mealie/api/units.py`, `src/mealie_mcp_server/models/inputs/foods.py`, `src/mealie_mcp_server/models/inputs/units.py`, `src/mealie_mcp_server/tools/foods.py`, `src/mealie_mcp_server/tools/units.py`, `tests/fixtures/compatibility/cases/foods_units.json`.
**Tests:** `tests/unit/test_foods_api.py`, `tests/unit/test_units_api.py`, `tests/contracts/test_foods_units.py`.

**Interfaces:** consume lookup_candidates P07 y cliente P05. Produce register_foods(server: FastMCP) -> None; register_units(server: FastMCP) -> None; API wrappers tipados de las operaciones originales.

**Herramientas (13):** `get_foods`, `get_food`, `get_food_matches`, `create_food`, `update_food`, `delete_food`, `merge_foods`, `get_units`, `get_unit`, `get_unit_matches`, `create_unit`, `update_unit`, `delete_unit`.

- [x] **1. Añadir las pruebas antes del código funcional.** test_foods_units_contract para13 herramientas. test_update_preserves_omitted_fields_and_households: PUT mantiene metadatos/aliases no tocados. test_aliases_null_empty_distinct; test_merge_foods_verifies_source_disappeared: PUT merge y GET posterior exactos, sin retries. test_units_conversion_metadata no infiere conversiones.
- [x] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [x] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 13 herramientas; límites de búsqueda P07; fallos de merge/PUT y preservación de datos cubiertos; no cambiar mapa de aliases ni scope del household.

- [x] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_foods_api.py tests/unit/test_units_api.py tests/contracts/test_foods_units.py -q
```

- [x] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port food and unit tools`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p10"></a>
### P10: Migrar el catálogo de utensilios

**Depende de:** P09. **Estado:** verificada; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/mealie/api/equipment.py`, `src/mealie_mcp_server/models/inputs/equipment.py`, `src/mealie_mcp_server/tools/equipment.py`, `tests/fixtures/compatibility/cases/equipment.json`.
**Tests:** `tests/unit/test_equipment_api.py`, `tests/contracts/test_equipment.py`.

**Interfaces:** consume lookup_candidates P07. Produce register_equipment(server: FastMCP) -> None; wrappers get_tools/get_tool/get_tool_matches/create_tool/update_tool/delete_tool, conservando esos nombres MCP.

**Herramientas (6):** `get_tools`, `get_tool`, `get_tool_matches`, `create_tool`, `update_tool`, `delete_tool`.

- [x] **1. Añadir las pruebas antes del código funcional.** test_equipment_contract para6 nombres; test_rename_preserves_households_with_tool: assert payload['householdsWithTool'] conserva original; test_candidates_do_not_create; test_delete_error_and_204.
- [x] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [x] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 6 herramientas y escrituras PUT conservadoras; equipamiento no se confunde con las herramientas MCP.

- [x] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_equipment_api.py tests/contracts/test_equipment.py -q
```

- [x] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port equipment organizer tools`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p11"></a>
### P11: Migrar listas de compra e items

**Depende de:** P10. **Estado:** verificada; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/mealie/api/shopping_lists.py`, `src/mealie_mcp_server/models/inputs/shopping_lists.py`, `src/mealie_mcp_server/tools/shopping_lists.py`, `tests/fixtures/compatibility/cases/shopping_lists.json`.
**Tests:** `tests/contracts/test_shopping_lists.py`.

**Interfaces:** consume Cliente y contratos MCP P05/P06. Produce register_shopping_lists(server: FastMCP) -> None y13 handlers con las firmas del inventario.

**Herramientas (13):** `get_shopping_lists`, `create_shopping_list`, `get_shopping_list`, `update_shopping_list`, `delete_shopping_list`, `add_recipe_to_shopping_list`, `remove_recipe_from_shopping_list`, `get_shopping_list_items`, `create_shopping_list_item`, `create_shopping_list_items_bulk`, `update_shopping_list_item`, `delete_shopping_list_item`, `delete_shopping_list_items_bulk`.

- [x] **1. Añadir las pruebas antes del código funcional.** test_shopping_lists_contract para13 herramientas; test_remove_recipe_uses_post_delete_suffix; test_delete_bulk_uses_csv_query_not_json_body; test_false_zero_and_omission: checked=False/quantity=0 llegan al PUT; get_shopping_list_items no acepta listId. Cubrir éxito/error y 204 reales por cada delete.
- [x] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [x] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 13 herramientas, incluyendo huecos de referencia literal del original; semántica bulk del endpoint preservada, sin trasplantar respuesta de lotes de recetas.

- [x] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/contracts/test_shopping_lists.py -q
```

- [x] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port shopping list tools`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p12"></a>
### P12: Migrar el núcleo de recetas

**Depende de:** P11. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/mealie/api/recipes.py`, `src/mealie_mcp_server/models/inputs/recipes.py`, `src/mealie_mcp_server/tools/recipes.py`, `src/mealie_mcp_server/services/taxonomy_resolution.py`, `tests/fixtures/compatibility/cases/recipes_core.json`.
**Tests:** `tests/contracts/test_recipes_core.py`, `tests/unit/test_recipe_batch.py`, `tests/unit/test_taxonomy_resolution.py`.

**Interfaces:** consume P05/P06; resolve_organizer_values P08. Produce register_recipe_core(server: FastMCP) -> None; get_recipe(client: MealieClient, slug: str) -> JsonObject; get_recipes_batch(client: MealieClient, slugs: list[str], *, detailed: bool) -> JsonValue; resolve_taxonomy_filter(client: MealieClient, kind: str, values: list[str] | None) -> list[str] | None.

**Herramientas (8):** `get_recipes`, `get_recipe_detailed`, `get_recipe_concise`, `get_recipes_batch`, `get_recipes_detailed_batch`, `create_recipe`, `duplicate_recipe`, `delete_recipe`.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_recipe_core_contract para8 herramientas; test_batch_limit4_preserves_order_and_errors; test_concise_projection; test_create_returns_slug_then_updates: si la segunda fase falla la creación no se inventa como revertida. test_get_recipes_repeated_categories_tags y campos desconocidos de receta preservados.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 8 herramientas; patch_recipe queda para P13; concurrencia4 y serialización de filtros exactas.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/contracts/test_recipes_core.py tests/unit/test_recipe_batch.py tests/unit/test_taxonomy_resolution.py -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port core recipe reads and CRUD`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p13"></a>
### P13: Migrar taxonomía y utensilios de recetas, incluido patch_recipe

**Depende de:** P12. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/services/recipe_taxonomy.py`, `src/mealie_mcp_server/services/recipe_equipment.py`, `src/mealie_mcp_server/models/inputs/recipe_taxonomy.py`, `src/mealie_mcp_server/tools/recipes.py`, `tests/fixtures/compatibility/cases/recipe_organizers.json`.
**Tests:** `tests/unit/test_recipe_taxonomy.py`, `tests/unit/test_recipe_equipment.py`, `tests/contracts/test_recipe_organizers.py`.

**Interfaces:** consume Recetas P12; organizadores P08/P10. Produce build_taxonomy_patch(client: MealieClient, recipe: JsonObject, changes: JsonObject) -> JsonObject; update_recipe_taxonomy(client: MealieClient, slug: str, changes: JsonObject) -> JsonObject; update_recipe_equipment(client: MealieClient, slug: str, changes: JsonObject) -> JsonObject; handlers singulares/batch y patch_recipe.

**Herramientas (5):** `patch_recipe`, `update_recipe_taxonomy`, `update_recipe_taxonomy_batch`, `update_recipe_tools`, `update_recipe_tools_batch`.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_merge_replace_and_delta_exclusive; test_noop_does_not_patch; test_duplicate_slugs_no_writes; test_batch_serializes_create_missing y scopes por entrada. test_taxonomy_batch_not_artificially_capped_at25; equipamiento sí1..25; max_inflight escritores5. test_patch_preserves_unrelated_fields y taxonomyChanges.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 5 herramientas; lotes independientes, creación serializada; canónicos creados no se revierten globalmente por fallos posteriores.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_recipe_taxonomy.py tests/unit/test_recipe_equipment.py tests/contracts/test_recipe_organizers.py -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port guarded recipe organizer updates`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p14"></a>
### P14: Migrar planes de comidas y operaciones por fases

**Depende de:** P13. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/mealie/api/mealplans.py`, `src/mealie_mcp_server/models/inputs/mealplans.py`, `src/mealie_mcp_server/tools/mealplans.py`, `tests/fixtures/compatibility/cases/mealplans.json`.
**Tests:** `tests/unit/test_mealplans_api.py`, `tests/contracts/test_mealplans.py`.

**Interfaces:** consume get_recipes_batch P12 y cliente P05. Produce register_mealplans(server: FastMCP) -> None; seis herramientas del inventario.

**Herramientas (6):** `get_all_mealplans`, `get_mealplan_with_recipes`, `create_mealplan`, `create_mealplan_bulk`, `get_todays_mealplan`, `patch_mealplan`.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_mealplans_contract para6 nombres. test_patch_phase_order: assert calls == deletes+replaces+appends y resultados agrupados por fase; replace conserva campos omitidos mediante lectura previa. test_bulk_is_error_only_if_all_fail; test_embed_fetches_all_pages; test_today_calls_mealie_endpoint, no reloj del contenedor.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 6 herramientas; límites4 y fallos parciales, fechas y paginación como baseline.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_mealplans_api.py tests/contracts/test_mealplans.py -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port meal planning and phased updates`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p15"></a>
### P15: Migrar búsqueda por ingredientes, cursores y colas de auditoría

**Depende de:** P14. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/services/recipe_discovery.py`, `src/mealie_mcp_server/services/ingredient_resolution.py`, `src/mealie_mcp_server/support/recipe_scan.py`, `src/mealie_mcp_server/services/recipe_audit.py`, `src/mealie_mcp_server/services/recipe_classification.py`, `src/mealie_mcp_server/services/recipe_ingredient_parsing.py`, `src/mealie_mcp_server/services/recipe_enrichment.py`, `src/mealie_mcp_server/tools/recipes.py`, `tests/fixtures/compatibility/cases/recipe_queues.json`.
**Tests:** `tests/unit/test_recipe_discovery.py`, `tests/unit/test_recipe_scan.py`, `tests/unit/test_recipe_audit.py`, `tests/contracts/test_recipe_queues.py`.

**Interfaces:** consume P07/P09/P12; snapshots de cursores P03. Produce encode_cursor(cursor: ScanCursor) -> str; decode_cursor(raw: str) -> ScanCursor; scan_recipes_stable(client: MealieClient, cursor: ScanCursor | None) -> AsyncIterator[JsonObject]; audit_recipe(recipe: JsonObject) -> JsonObject; cuatro herramientas.

**Herramientas (4):** `find_recipes_for_ingredients`, `get_recipes_for_classification`, `get_recipes_for_ingredient_parsing`, `get_recipes_for_data_enrichment`.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_cursor_cross_language_v1; test_same_created_at_stable_id_order; test_invalid_cursor_rejected; test_sparse_page_deadline_keeps_has_more: defaults25/max50, batch de detalle20, deadline20s; test_filters_replace_defaults_empty_rejected; test_sections_not_unparsed; test_no_unit_countable_partial_is_only_signal; read-only: assert recorded_writes == [].
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 4 herramientas; fallback y procedencia reproducibles; ningún LLM ni conversión semántica; no prometer snapshot transaccional ante borrados concurrentes.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_recipe_discovery.py tests/unit/test_recipe_scan.py tests/unit/test_recipe_audit.py tests/contracts/test_recipe_queues.py -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port stable recipe discovery and audit queues`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p16"></a>
### P16: Migrar escrituras de ingredientes y recuperación

**Depende de:** P15. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/models/inputs/recipe_ingredients.py`, `src/mealie_mcp_server/services/recipe_ingredients.py`, `src/mealie_mcp_server/tools/recipes.py`, `tests/fixtures/compatibility/cases/recipe_ingredients.json`.
**Tests:** `tests/unit/test_recipe_ingredients.py`, `tests/contracts/test_recipe_ingredients.py`.

**Interfaces:** consume Recetas y cliente; vocabularios P09; concurrencia P05. Produce update_recipe_ingredients(client: MealieClient, slug: str, changes: JsonObject) -> JsonObject; update_recipe_ingredients_batch(client: MealieClient, updates: list[JsonObject]) -> JsonObject; ambas herramientas.

**Herramientas (2):** `update_recipe_ingredients`, `update_recipe_ingredients_batch`.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_replace_or_reference_delta; test_preserves_reference_ids_notes_and_sections; test_subrecipe_reference_checked; test_food_unit_name_id_mismatch_before_write; test_silent_association_corruption_rolls_back; test_rollback_failure_reported. Batch1..25/slugs únicos/concurrencia5. test_disconnect_after_patch_finishes_verification_with_bounded_cleanup; test_cancel_before_write_has_no_effect.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 2 herramientas; verificación de persistencia y best-effort rollback con error propio por receta; no se pierde un campo ajeno por usar un modelo incompleto.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_recipe_ingredients.py tests/contracts/test_recipe_ingredients.py -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port verified ingredient writes and recovery`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p17"></a>
### P17: Migrar instrucciones con guardas de snapshot

**Depende de:** P16. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/models/inputs/recipe_instructions.py`, `src/mealie_mcp_server/services/recipe_instructions.py`, `src/mealie_mcp_server/tools/recipes.py`, `tests/fixtures/compatibility/cases/recipe_instructions.json`.
**Tests:** `tests/unit/test_recipe_instructions.py`, `tests/contracts/test_recipe_instructions.py`.

**Interfaces:** consume Recetas P12 e ingredientes P16. Produce update_recipe_instructions(client: MealieClient, slug: str, expected_updated_at: str, changes: JsonObject) -> JsonObject; update_recipe_instructions_batch(client: MealieClient, updates: list[JsonObject]) -> JsonObject.

**Herramientas (2):** `update_recipe_instructions`, `update_recipe_instructions_batch`.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_stale_snapshot_rejected_before_write; test_indexes_reference_original_snapshot; test_ephemeral_instruction_ids_ignored; test_ingredient_reference_validation; test_noop_skips_patch; test_verify_and_rollback_error. Rechazar mezclas replacement/delta; batch1..25/5; cancelar tras escribir deja verificación acotada. Documentar la carrera read->PATCH no atómica.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 2 herramientas y referencia cruzada ingrediente-instrucción preservada; no prometer compare-and-swap inexistente.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_recipe_instructions.py tests/contracts/test_recipe_instructions.py -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port snapshot-guarded recipe instructions`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p18"></a>
### P18: Migrar imágenes y el descargador con DNS fijado

**Depende de:** P17. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/support/safe_download.py`, `src/mealie_mcp_server/support/recipe_image.py`, `src/mealie_mcp_server/models/inputs/recipe_image.py`, `src/mealie_mcp_server/tools/recipes.py`, `tests/fixtures/compatibility/cases/recipe_images.json`.
**Tests:** `tests/unit/test_safe_download.py`, `tests/unit/test_recipe_image.py`, `tests/contracts/test_recipe_images.py`.

**Interfaces:** consume Cliente multipart P05 y recetas P12. Produce PinnedDownloadTransport.fetch(url: str, *, validated_addresses: tuple[str,...], deadline: float) -> AsyncIterator[bytes]; download_bounded(url: str, max_bytes: int, *, timeout_s: float = 30, max_redirects: int = 3) -> bytes; decode_recipe_image(payload: str, extension: str | None = None) -> tuple[bytes,str].

**Herramientas (3):** `set_recipe_image`, `set_recipe_image_from_file`, `set_recipe_image_from_url`.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_png_jpeg_gif_webp_magic_and_10mib; test_mime_hint_not_authority; test_three_redirects_revalidated; test_30s_includes_dns_and_body; test_mixed_public_private_rejected; test_no_second_dns_and_original_sni_host; test_ipv6_mapped_private; test_public_address_fallback_and_peer_recheck. file contiene download_url/file_id, no ruta local. set_image null borra; image_from_url delega en Mealie.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 3 herramientas, _meta openai/fileParams solo para file; suite con transporte inyectable y una prueba de socket real controlado. Si HTTPX2 no permite DNS fijado mediante API pública, usar conector asyncio TLS dedicado y probado; nunca sustituir por precheck DNS + segunda resolución.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_safe_download.py tests/unit/test_recipe_image.py tests/contracts/test_recipe_images.py -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port bounded image downloads and uploads`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p19"></a>
### P19: Migrar valoraciones, favoritos y fechas

**Depende de:** P18. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/mealie/api/users.py`, `src/mealie_mcp_server/services/recipe_rating.py`, `src/mealie_mcp_server/services/last_made.py`, `src/mealie_mcp_server/tools/recipes.py`, `tests/fixtures/compatibility/cases/ratings_dates.json`.
**Tests:** `tests/unit/test_recipe_rating.py`, `tests/unit/test_last_made.py`, `tests/contracts/test_ratings_dates.py`.

**Interfaces:** consume Cliente por configuración P05/P06 y recetas. Produce resolve_last_made_timestamp(value: str | None, *, now: datetime, zone: ZoneInfo) -> str; set_recipe_rating(client: MealieClient, slug: str, changes: JsonObject) -> JsonObject; caché self confinada al cliente.

**Herramientas (2):** `set_recipe_rating`, `mark_recipe_last_made`.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_rating_half_steps_0_5_to5_and_null_to_zero; test_favorite_only_preserves_rating; test_failed_self_lookup_not_cached; test_two_clients_do_not_share_user. test_date_noon_local_today_clamped_future_rejected; test_dst_madrid_and_utc_roundtrip; timestamp omitido=ahora, null sigue rechazado por input schema si original lo rechaza.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 2 herramientas; cache por credenciales y zona explícita, lectura final de rating y agregado como original.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_recipe_rating.py tests/unit/test_last_made.py tests/contracts/test_ratings_dates.py -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: port user ratings and local date semantics`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p20"></a>
### P20: Cerrar catálogo, prompt e instrucciones

**Depende de:** P19. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/tools/registry.py`, `src/mealie_mcp_server/prompts.py`, `src/mealie_mcp_server/resources/server-instructions.md`, `src/mealie_mcp_server/server.py`, `tests/fixtures/compatibility/catalog-differences.json`, `docs/migration/compatibility-inventory.json`.
**Tests:** `tests/contracts/test_full_catalog.py`, `tests/contracts/test_prompts.py`, `tests/contracts/test_server_instructions.py`.

**Interfaces:** consume Los78 handlers P08..P19; baseline P03. Produce register_all_tools y register_prompts(server: FastMCP) -> None completos; weekly-meal-plan(preferences: str | None = None); instrucciones empaquetadas y versión única.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_full_catalog_exact_names: assert len(names)==78; assert names==baseline_names. test_prompt_roles_and_confirmation: roles assistant,user y confirmación antes de guardar. test_instructions_preserved_with_perpage_correction; test_file_meta_exactly_one_tool; strict validation en todos los objetos; outputschema/structuredContent solo cuando no cambia contenido anterior.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. 78/78+1 prompt+instrucciones; diferencias de metadata y 204 registradas, runtimeInputSchema ya capturado y confrontado. Sigue faltando demostrar transportes/imagen final.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/contracts/test_full_catalog.py tests/contracts/test_prompts.py tests/contracts/test_server_instructions.py -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: complete MCP catalog and agent guidance`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p21"></a>
### P21: Completar CLI y stdio real

**Depende de:** P20. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/cli.py`, `src/mealie_mcp_server/__main__.py`, `pyproject.toml`, `docs/clients.md`.
**Tests:** `tests/integration/test_stdio.py`, `tests/unit/test_cli.py`.

**Interfaces:** consume create_server P06, Settings P04 y catálogo P20. Produce main(argv: Sequence[str] | None = None) -> int; entrada mealie-mcp-server; python -m mealie_mcp_server equivalente; --transport stdio default.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_help_version_without_env_no_secret_read; test_stdio_stdout_only_jsonrpc; test_stdio_modern_and_2025_11_25; test_prompt_and_tool_roundtrip; test_eof_and_sigterm_close_pool; test_missing_config_exits_nonzero_without_secret. Protocolos por cliente SDK oficial y FastMCP; token HTTP ausente no bloquea stdio.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. Subprocess real y wheel fuera del árbol fuente; nada de banner/ANSI/logs en stdout; ejemplos locales Windows/Linux documentados.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_cli.py tests/integration/test_stdio.py -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: add production CLI and stdio transport`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p22"></a>
### P22: Completar HTTP con Bearer personal y salud

**Depende de:** P21. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `src/mealie_mcp_server/auth.py`, `src/mealie_mcp_server/health.py`, `src/mealie_mcp_server/server.py`, `src/mealie_mcp_server/cli.py`, `docs/http-deployment.md`, `docs/configuration.md`.
**Tests:** `tests/unit/test_auth.py`, `tests/integration/test_http.py`, `tests/integration/test_http_cancellation.py`.

**Interfaces:** consume CLI/factory/clientes P21; token y hosts P04. Produce PersonalTokenVerifier configurado por secreto; create_http_app(server: FastMCP, settings: Settings) -> ASGIApp; /mcp, /healthz y /readyz.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_missing_wrong_token_401; test_token_never_forwarded_to_mealie; test_forbidden_origin_host; test_http_body32mib_allows_image10mib; test_health_does_not_call_mealie; test_ready_only_after_lifespan; test_http_catalog_equals_stdio; test_both_protocol_eras_and_large_results; test_disconnect_no_retry_and_bounded_verification.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. HTTP sin token no arranca; digest en tiempo constante; Bearer independiente; un worker; SSE correcto; salud mínima fuera del auth de MCP; documentar proxy/TLS sin anunciar OAuth.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run pytest tests/unit/test_auth.py tests/integration/test_http.py tests/integration/test_http_cancellation.py -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `feat: add authenticated Streamable HTTP transport`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p23"></a>
### P23: Construir y verificar la imagen de producción

**Depende de:** P22. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `Dockerfile`, `compose.production.yaml`, `.dockerignore`, `.github/workflows/ci.yaml`, `.github/workflows/release.yaml`, `docs/containers.md`.
**Tests:** `tests/containers/test_runtime_stdio.py`, `tests/containers/test_runtime_http.py`, `tests/containers/test_runtime_security.py`.

**Interfaces:** consume App completa P22 y lock P02. Produce Stages base/builder/development/runtime; mismo wheel de release; image stdio default o HTTP command; CI build/smoke y workflow release con publicación condicionada al cierre P24.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_runtime_no_node_devtools_or_secrets; test_nonroot_readonly_tmpfs; test_docker_stdio_i_no_tty; test_http_bearer_health_and_stop45s; test_wheel_contains_instructions. Probar imagen final sin source mounts, stdout JSON-RPC, stdin, señales y separación de credenciales. Salud solo para perfil HTTP.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. Imagen ejecutable linux/amd64 y linux/arm64 con smoke por arquitectura, emulación identificada; CA/tzdata; labels/SBOM/provenance; no publicar ni desplegar por crear el plan.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
docker build --target runtime -t mealie-mcp-server:local .
docker compose -f compose.production.yaml config
uv run pytest tests/containers -q
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `build: add verified production MCP image`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

<a id="p24"></a>
### P24: Cerrar integración, documentación, retirada TS y aceptación

**Depende de:** P23. **Estado:** pendiente; ver registro de ejecución.

**Archivos:** `compose.integration.yaml`, `tests/integration/test_mealie_roundtrip.py`, `scripts/generate_docs.py`, `scripts/check_compatibility.py`, `README.md`, `API_COVERAGE.md`, `ARCHITECTURE.md`, `WORKFLOWS.md`, `CONTRIBUTING.md`, `docs/README.md`, `docs/migration/acceptance.md`, `docs/migration/differences.md`, `docs/migration/progress.md`, `renovate.json`, `sonarcloud.properties`, `opencode.json`, `.github/workflows/ci.yaml`, `.github/workflows/release.yaml`.
**Tests:** `tests/contracts/test_docs_generation.py`, `tests/integration/test_mealie_roundtrip.py`.

**Interfaces:** consume P01..P23 y todos los contratos C01..C16. Produce generate_docs.main(argv: Sequence[str] | None = None) -> int con --check; check_compatibility.main(argv: Sequence[str] | None = None) -> int; informe reproducible y entrega Python completa.

- [ ] **1. Añadir las pruebas antes del código funcional.** test_mealie_disposable_end_to_end: crear receta/alimento/unidad, escribir ingredientes/instrucciones/taxonomía, leer y comprobar referencias, imagen/rating/plan/lista y limpieza solo del proyecto de test. test_docs_match_registry: --check detecta drift. test_branch_threshold_independent rechaza90% líneas/84% ramas aunque el porcentaje combinado pase. Contratos78 positivos+78 rechazos y todos los escenarios profundos del original; ejecutar conformidad en runner externo.
- [ ] **2. Ejecutar el subconjunto indicado y observar RED.** El fallo esperado es el comportamiento/handler aún ausente o incorrecto; si falta infraestructura del harness, arreglarla antes de tomar el fallo como evidencia.
- [ ] **3. Implementar las interfaces de esta tarea y sus fixtures.** Reutilizar los contratos anteriores; preservar los valores del diseño y el inventario. >=90% líneas y >=85% ramas mediante comprobador que lee coverage.json; no sustituirlo por --cov-fail-under global. Guardar versiones/imagen Mealie fijada, resultados y limitaciones. Retirar runner TS temporal del CI ordinario y cualquier JS/Node propio permanente; conservar fixtures/procedencia/licencia e historia. Revisar cambios completos, checkout limpio y smoke de imagen final. Publicación/endpoint público quedan pendientes de destino y autorización.

- [ ] **4. Verificar el resultado de esta tarea.** Ejecutar dentro del Dev Container; salida0 y todas las aserciones indicadas en verde. Para P01 el launcher y el contenedor auxiliar son la excepción de bootstrap explicada arriba.

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=mealie_mcp_server --cov-branch --cov-report=json:artifacts/coverage.json
uv run python scripts/check_compatibility.py --inventory docs/migration/compatibility-inventory.json --require-all --coverage-json artifacts/coverage.json
uv run python scripts/generate_docs.py --check
uv build
docker compose -f compose.integration.yaml up --abort-on-container-exit --exit-code-from tests
```

- [ ] **5. Revisar, documentar y cerrar.** Comprobar el criterio de salida anterior y el diff; no ampliar la suite sin una nueva causa. Actualizar estado, diferencias si las hay y evidencia con comando/resultado/entorno. Commit de implementación sugerido: `docs: finalize Python migration acceptance and delivery`. Registrar su SHA en un commit documental posterior si hace falta; no intentar incluir el hash de un commit en sí mismo.

## Trazabilidad de contratos y cobertura original

Los contratos C01..C16 pertenecen al inventario; esta tabla indica quién los demuestra:

| Contrato | Tareas responsables |
|---|---|
| C01 | P04, P06, P20 |
| C02 | P04, P08, P09, P11, P16 |
| C03 | P03, P06, P20 |
| C04 | P05 |
| C05 | P05, P11, P12 |
| C06 | P05, P12, P13, P14, P16, P17 |
| C07 | P15 |
| C08 | P15 |
| C09 | P16 |
| C10 | P17 |
| C11 | P13, P14, P16, P17 |
| C12 | P18 |
| C13 | P18 |
| C14 | P19 |
| C15 | P19 |
| C16 | P05, P16, P17, P22 |

El [registro JSON](../../migration/implementation-state.json) asigna **cada una de las78 herramientas a una única tarea de implementación**, los21 módulos lib y los42 archivos de tests originales a una tarea responsable. P20 los integra y P24 comprueba que ningún escenario se perdió. La asignación de tests no exige copiar archivos1:1: exige portar sus comportamientos.

Las interfaces de dominios compartidas se construyen primero: P07 matching -> P09/P10 vocabularios; P12 recetas -> P13/P14; P15 lectura/auditoría -> P16/P17 escritura. P21/P22 utilizan el mismo catálogo, sin duplicar lógica. Las dependencias del JSON son las explícitas de los bloques anteriores; también se respetan las fases y su orden secuencial.

## Revisión del plan realizada

- Diseño1..4: objetivo, límites y versiones en Global Constraints y P01..P04.
- Diseño5..6: arquitectura, modelos/contratos/lógica en P05..P20.
- Diseño7..8: CLI/stdin/HTTP/Bearer/salud en P21..P22.
- Diseño9: bootstrap y devcontainer reproducible en P01..P02; runner aislado en P03.
- Diseño10: runtime, hardening, multiarch y CI/release en P23.
- Diseño11: corpus, clientes independientes y aceptación en P03/P20..P24.
- Diseño12: retirada TS y entrega con evidencia en P24.
- Diseño13: registry, nombre de paquete, dominio, proxy y secretos reales difieren al despliegue; no bloquean pruebas locales.
- Review Focus1..5: pruebas concretas en P01/P02, P05/P23, P16/P17/P22, P18/P22/P23 y P06/P19.
- Tipos y nombres comunes comprobados contra sus tareas productoras. No se ha ejecutado código de aplicación por escribir el plan.

## Handoff y cambios de alcance

El usuario autorizó empezar la implementación; se utiliza ejecución secuencial nativa. Se registran avances en docs/migration y no se pide confirmación entre tareas ya autorizadas.

Una tarea bloqueada registra condición y próximo paso, sin marcarse completa. Al retomar se lee el estado y se continúa en la primera tarea pendiente con dependencias satisfechas, sin repetir fases cerradas salvo cambio/fallo concreto. Publicación de imagen/paquete y despliegue público requieren destino configurado y autorización correspondiente; no son condición para disponer de la imagen local de producción probada.
