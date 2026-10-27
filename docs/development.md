# Desarrollo en Dev Container

El proyecto usa Docker Desktop en modo Linux y Dev Containers de VS Code. Abrir esta carpeta y ejecutar **Dev Containers: Reopen in Container**.

El target development incluye Python3.14 y uv fijados por digest. El usuario remoto es vscode (no root); .venv y caché uv usan volúmenes Linux. Docker CLI comparte el daemon del host mediante la feature docker-outside-of-docker. No hay daemon anidado ni secrets incorporados a la imagen.

ICU reproduce la ordenación por nombres de la referencia Node. Development incluye libicu-dev, pkg-config y g++ para construir PyICU; el runtime solo necesita libicu72. El lock fija PyICU2.17. Reabrir/reconstruir el Dev Container después de cambiar Dockerfile.

En el primer arranque, sin uv.lock, solo se prepara el entorno. P02 crea el lock dentro del contenedor; los arranques posteriores ejecutan uv sync --frozen --group dev.

Comprobaciones en el terminal del contenedor:

```bash
python --version
id -u
uv --version
docker version
docker compose -f .devcontainer/compose.yaml config
```

El puerto8000 se reenvía como privado; todavía no hay un servidor HTTP implementado en P01. No se arranca Mealie ni se requiere una API key para preparar el entorno.

[Plan](superpowers/plans/2026-10-27-python-migration.md) · [Avance](migration/progress.md) · [Ledger](migration/execution-log.md).
