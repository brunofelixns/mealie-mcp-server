# Contenedor de producción

El Dockerfile tiene etapas development, builder y runtime. El runtime instala el wheel y sus dependencias de producción; conserva CA, tzdata e ICU72. No incorpora Node, compiladores, uv, pip, ensurepip, herramientas de tests ni secretos. Ejecuta como10001:10001 y admite raíz de solo lectura con /tmp temporal.

## Construcción y prueba

Ejecutar dentro del Dev Container:

```sh
docker buildx build --platform linux/amd64 --target runtime -t mealie-mcp-server:local --sbom=true --provenance=mode=max --load .
uv run pytest tests/containers -q
docker buildx build --platform linux/arm64 --target runtime -t mealie-mcp-server:local-arm64 --sbom=true --provenance=mode=max --load .
MCP_TEST_IMAGE=mealie-mcp-server:local-arm64 MCP_TEST_ARCH=arm64 uv run pytest tests/containers -q
```

Docker Desktop proporciona emulación arm64 en la máquina x86_64 validada. La compilación nativa de PyICU bajo emulación puede tardar bastante más; no confundirla con una prueba en hardware ARM nativo. Los workflows proponen runners nativos ubuntu-24.04 y ubuntu-24.04-arm; no se han ejecutado en GitHub todavía.

Las bases Python3.14 y uv están fijadas por digest en Dockerfile; uv.lock fija los paquetes. development contiene compiladores y herramientas; runtime parte de una base limpia y solo copia el entorno instalado desde builder. `uv pip check` verifica sus64 paquetes durante build. [La evidencia](migration/evidence/runtime-images.json) identifica hashes, plataformas y análisis observados; un nuevo build puede cambiar paquetes Debian y los hashes.

## Configuración y secretos

Copiar .env.example a una configuración privada e indicar MEALIE_BASE_URL. Crear dos archivos UTF-8 fuera de Git: secrets/mealie_api_key y secrets/mcp_auth_token. El primero contiene una API key Mealie; el segundo, un valor aleatorio independiente de al menos32 caracteres visibles. No introducir secretos en build args, imágenes o comandos versionados. En Linux el proceso10001 debe poder leer cada archivo: por ejemplo, directorio privado0700 y archivos0444. Revisar los permisos efectivos del montaje; los secrets de archivo de Compose utilizan bind mounts.

Generar un token dentro del Dev Container, escribiéndolo directamente al archivo:

```sh
mkdir -p secrets
uv run python -c 'from pathlib import Path; import secrets; Path("secrets/mcp_auth_token").write_text(secrets.token_urlsafe(32))'
```

Guardar la API key con el editor o un mecanismo de secretos del operador; el ejemplo no la imprime. Dockerfile y .dockerignore excluyen estos archivos. Para desplegar Compose, los archivos deben existir **en el host del daemon Docker**. Ejecutar los siguientes launchers Docker desde el checkout de ese host; no pasar una ruta interna /workspaces del Dev Container como bind mount del host. Esto no requiere instalar Python en el host. Las pruebas desde el Dev Container utilizan la API Docker, volúmenes temporales y redes compartidas.

## stdio

```sh
docker compose -f compose.production.yaml --profile stdio run --rm -T stdio
```

No asignar TTY. Usar docker como comando del cliente y esos argumentos, con una ruta absoluta a compose.production.yaml si el cliente arranca en otro directorio. El perfil solo monta la credencial Mealie y no configura healthcheck. El contenedor recibe EOF al cerrar el cliente y sale0; también convierte SIGTERM/SIGINT en EOF.

## HTTP

Configurar MCP_PUBLIC_URL=https://mcp.example.com/mcp y, si procede, MCP_ALLOWED_ORIGINS. El perfil exige HTTPS público y utiliza el token propio:

```sh
docker compose -f compose.production.yaml --profile http up --detach
docker compose -f compose.production.yaml --profile http ps
```

El puerto8000 se publica solo en127.0.0.1. El proxy TLS debe ejecutarse en ese host o compartir una red privada con el servicio; consultar [HTTP](http-deployment.md). /readyz sirve al healthcheck sin contactar Mealie. Los secretos se montan en solo lectura; el filesystem raíz es read-only, /tmp es tmpfs, se eliminan capabilities y se activa no-new-privileges. init reenvía señales y Compose concede45 segundos de cierre. Uvicorn sale143 después de limpiar SIGTERM.

MEALIE_BASE_URL debe ser accesible desde esta red: localhost dentro del contenedor apunta al propio MCP. Docker Desktop permite host.docker.internal para un Mealie en el host; en Linux configurar una dirección alcanzable o una red Docker externa común con Mealie. No se configura una instancia Mealie de producción automáticamente.

## Artefactos y actualizaciones

Con el almacén containerd validado, `docker image save -o artifacts/runtime.tar mealie-mcp-server:local` conserva el índice OCI y sus attestations. Usar un exportador OCI de Buildx o publicar en un registry cuando el almacén clásico no preserve attestations. SBOM/provenance describen el build; no certifican ausencia de vulnerabilidades.

```sh
uv run python scripts/scan_runtime.py mealie-mcp-server:local --output artifacts/runtime-security.json --enforce
```

El escáner fijado por digest recibe una copia del archivo de imagen y genera informe JSON, SBOM CycloneDX y versión/fecha de su DB. No recibe el socket Docker ni bind mounts del host. --enforce rechaza secretos y vulnerabilidades HIGH/CRITICAL con versión corregida disponible; conserva todos los avisos sin corregir en el informe. [El análisis actual](migration/evidence/P23-security.md) contiene limitaciones materiales de Debian12.

Revisar actualizaciones de imágenes y uv.lock explícitamente, reconstruir y repetir ambos transportes, payloads grandes y plataformas. PyICU/ICU forman parte de la compatibilidad de ordenación; cambiar Debian/ICU exige repetir el corpus de matching y golden tests.

release.yaml solo publica por workflow_dispatch con publish=true, después de CI, pruebas de la imagen por arquitectura, escaneo y release_gate. Este último exige las24 tareas verificadas y que la versión solicitada coincida con pyproject.toml. Publica en el namespace GHCR del repositorio que ejecuta el workflow y compone un manifest multiarch; no publica al upstream por crear estos archivos. No se ha ejecutado ninguna publicación.
