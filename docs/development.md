# Desarrollo en Dev Container

Abrir el repositorio con **Dev Containers: Reopen in Container**. Docker Desktop debe usar contenedores Linux. Python, uv, los tests y los builds se ejecutan dentro del Dev Container; el host sirve como editor y launcher de Docker.

El target development fija Python3.14 y uv por digest, usa el usuario vscode y guarda .venv y la caché de uv en volúmenes Linux. postCreateCommand ejecuta `uv sync --frozen --group dev`; no regenera el lock. En hosts Linux, updateRemoteUserUID alinea el usuario con el propietario del checkout. La feature docker-outside-of-docker comparte el daemon del host. Los bind mounts de contenedores hermanos se resuelven en ese host: no asumir que conoce /workspaces.

PyICU2.17 e ICU72.1 reproducen la ordenación de la referencia. Development incluye libicu-dev, pkg-config y g++; runtime solo necesita libicu72. Reconstruir el Dev Container si cambia Dockerfile. El puerto8000 se reenvía como privado; el servidor arranca mediante el CLI descrito en [clientes](clients.md).

## Comprobaciones

Desde el terminal del contenedor:

```bash
uv sync --frozen --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python scripts/generate_docs.py --check
uv run pytest -q --cov=mealie_mcp_server --cov-branch --cov-report=json:artifacts/coverage.json --cov-report=xml:artifacts/coverage.xml --junitxml=artifacts/pytest.xml
uv run python scripts/check_compatibility.py --require-all --coverage-json artifacts/coverage.json --junit-xml artifacts/pytest.xml
uv build
```

Construir primero la imagen runtime como indica [contenedores](containers.md): la suite incluye pruebas reales de esa imagen. Los umbrales se comprueban independientemente: líneas >=90% y ramas >=85%. coverage activa la medición de los subprocess Python para observar el CLI real; la imagen de producción no incorpora coverage. El JUnit demuestra la ejecución de casos positivos y rechazos para las78 herramientas; un índice de fixtures por sí solo no demuestra que pasaron.

`uv run python scripts/generate_docs.py` regenera docs/tools.md, docs/api-coverage.md, el índice API_COVERAGE.md y únicamente la sección delimitada de herramientas en README.md. Conserva el texto manual y escribe mediante reemplazo atómico. `--check` falla ante diferencias, incluidos cambios de esquema.

## Integración real desechable

Desde el terminal del Dev Container, con Docker Desktop disponible:

```bash
uv run python -m tests.e2e.runner
```

El controlador construye el runtime y crea un proyecto Compose único con Mealie3.29.0 fijado por digest. Ejecuta las78 herramientas y78 rechazos de argumentos por cada combinación stdio/HTTP y MCP2026-07-28/2025-11-25, con Bearer independiente en HTTP. Usa red interna, sin puertos publicados ni credenciales personales, y elimina sus contenedores/volúmenes incluso si fallan las pruebas. La descarga privada por archivo se verifica como rechazo SSRF esperado; las otras77 herramientas requieren operaciones positivas. Consultar el [runbook E2E](testing/local-e2e.md) para requisitos, evidencias, limpieza tras interrupciones y límites.

## Referencia de compatibilidad

Las capturas declarativas originales de tests/fixtures/compatibility, su procedencia y la licencia se conservan y se verifican mediante las pruebas Python. Node no es necesario para desarrollo, tests ni producción. Los runners temporales y sus scripts de captura se retiraron; su versión histórica está identificada en [baseline.md](migration/baseline.md).

El caso positivo de imagen por archivo usa un downloader Python inyectado; no se presenta como captura positiva original. La [limpieza final](migration/cleanup.md) registra qué se retiró y las comprobaciones posteriores.

Para cambios funcionales, añadir primero una prueba de comportamiento, preservar el contrato de src/mealie_mcp_server/resources/tool-catalog.json y registrar diferencias intencionadas en [differences.md](migration/differences.md). No modificar expectativas de referencia para ocultar regresiones.

[Plan](superpowers/plans/2026-10-27-python-migration.md) · [Avance](migration/progress.md) · [Ledger](migration/execution-log.md).
