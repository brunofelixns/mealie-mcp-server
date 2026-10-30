# Construir y publicar en GHCR desde el Dev Container

El script `scripts/publish_local.py` ejecuta el proceso en tu máquina, sin GitHub Actions. Construye `linux/amd64` y `linux/arm64`, valida ambas y, solo con `--publish`, las sube a GHCR y crea una etiqueta multiarch. Las imágenes publicadas son las mismas que se probaron: no se reconstruyen al publicar.

## Requisitos

- Abrir este repositorio en su Dev Container Linux, con el daemon Docker accesible. No instalar Python en Windows.
- Activar el **almacén de imágenes containerd** de Docker Desktop para conservar SBOM y provenance al cargar/exportar imágenes. El script falla si no puede conservar estas attestations. [Soporte de Docker](https://docs.docker.com/build/metadata/attestations/).
- Builder Buildx con amd64 y arm64; Docker Desktop proporciona emulación. Revisar con `docker buildx inspect default --bootstrap`. Compilar PyICU o ejecutar pruebas ARM bajo QEMU puede tardar bastante; esto no equivale a una prueba en hardware ARM nativo. [Builds multiarch](https://docs.docker.com/build/building/multi-platform/).
- Acceso a los registries y a la base de vulnerabilidades del escáner. Los builds, tests y escaneos son locales; descargar bases/dependencias y publicar requiere Internet.
- La versión solicitada debe coincidir con `pyproject.toml` y con las labels del Dockerfile. Usar una versión nueva por release; los tags existentes pueden reemplazarse al publicar. No se genera `latest`.

El script usa la red del Dev Container con alias `dev`, necesaria para las pruebas de sockets de contenedor. Si el contenedor tiene varias redes, definir `MCP_TEST_NETWORK` con esa red. No crear ni modificar una red de producción.

## Windows: paso a paso con PowerShell

Los comandos `gh ...`, `set -o pipefail` y `uv ...` de las secciones Linux se ejecutan en **Bash dentro del Dev Container**. Para trabajar desde PowerShell en Windows, usar el launcher [scripts/publish-local.ps1](../scripts/publish-local.ps1). Windows solo necesita Docker Desktop y PowerShell; GitHub CLI, Python, las pruebas y los builds se ejecutan en Linux.

### 1. Preparar Docker y el Dev Container

1. Abrir Docker Desktop y esperar a que esté listo, con contenedores Linux y el almacén containerd activado.
2. Abrir este repositorio en VS Code con la extensión **Dev Containers**.
3. Pulsar `Ctrl+Shift+P` y ejecutar **Dev Containers: Rebuild and Reopen in Container**. Esto incorpora GitHub CLI si el contenedor existente se creó antes de añadir esa feature. Esperar a que termine la preparación; no basta con `docker compose up`, que por sí solo no instala las features de VS Code.
4. Mantener el Dev Container en ejecución y abrir una ventana **PowerShell de Windows**, por ejemplo desde Windows Terminal.

### 2. Entrar en la carpeta y comprobar el plan

```powershell
Set-Location E:\GitHub\mealie-mcp-server
.\scripts\publish-local.ps1
```

La acción por defecto es `Plan`: localiza el contenedor que monta este checkout y muestra lo que se construiría y publicaría, sin iniciar sesión, construir ni subir imágenes. Los valores `<tested-...>` y `<verified-...>` son marcadores del plan, no texto que debas copiar.

Si Windows bloquea la ejecución del `.ps1`, se puede permitir **solo en esa ventana** y repetirlo:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\publish-local.ps1
```

Cerrar la ventana retira ese cambio de política. Una política de empresa puede tener prioridad; en ese caso utilizar el terminal Bash del Dev Container o seguir la configuración de tu organización, sin cambiar la política del equipo.

### 3. Iniciar sesión en GHCR una vez

La ruta documentada por GitHub para publicar fuera de Actions utiliza un [PAT classic con `write:packages`](https://github.com/settings/tokens/new?scopes=write:packages&description=mealie-mcp-server%20GHCR). Después de generarlo, autenticar Docker **dentro del Dev Container**:

```powershell
docker exec -it --user vscode mealie-mcp-development-dev-1 docker login ghcr.io --username brunofelixns
```

Introducir el PAT cuando pida `Password`. El PAT es el valor secreto que aparece después de `Generate token`; el nombre `mealie-mcp-server GHCR` solo identifica esa credencial. El token se introduce en el prompt de Docker, sin guardarlo en `.env`. Si se reconstruye el Dev Container y se pierde la sesión, repetir el login. Si el contenedor tiene otro nombre, usar ese nombre en el comando.

`-Action Login` conserva la opción de reutilizar la sesión web de GitHub CLI. Esa sesión OAuth no garantiza que GHCR autorice el push: en el intento registrado devolvió `denied` incluso con la cuenta y `write:packages` correctos. Para la publicación usar la ruta PAT anterior. [Autenticación GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

### 4. Construir, probar y publicar

Con los cambios guardados en commits y el checkout limpio:

```powershell
.\scripts\publish-local.ps1 -Action Publish
```

Este es el comando que **sí publica**. Delega en `scripts/publish_local.py --publish`, que obtiene la versión de `pyproject.toml`: no hay que introducir un token ni escribir la versión en PowerShell. Construye amd64/arm64, ejecuta los gates y solo después sube las imágenes al destino configurado. ARM bajo emulación tarda más. No editar el checkout durante la ejecución; los logs y resultados quedan en `artifacts/local-release/<id>/`.

Si quieres construir y probar antes sin subir nada:

```powershell
.\scripts\publish-local.ps1 -Action Verify
```

`Publish` vuelve a ejecutar las validaciones completas; `Verify` no crea un atajo para publicar después sin comprobarlas.

| Acción | Resultado |
|---|---|
| Sin parámetros o `-Action Plan` | Vista previa del flujo, sin login/build/push |
| `-Action Login` | Login de GitHub y Docker GHCR, sin build/push |
| `-Action Verify` | Construcción y validación local de ambas arquitecturas |
| `-Action Publish` | Validación completa y publicación si todos los gates pasan |

El launcher detecta el contenedor por su montaje del checkout, sin depender de un nombre fijo. Si hay varios, indicar el nombre concreto; para otra cuenta, cambiar el usuario de login:

```powershell
.\scripts\publish-local.ps1 -Action Login -Container mealie-mcp-development-dev-1 -GitHubUser brunofelixns
```

`-GitHubUser` cambia la cuenta de autenticación, no el destino GHCR del proyecto. Un fallo detiene el comando y no reintenta la operación automáticamente. Si falta `gh`, reconstruir el Dev Container como en el paso 1. Si GitHub informa de una credencial heredada mediante `GH_TOKEN`/`GITHUB_TOKEN`, revisar esa configuración del Dev Container antes de intentar otro login; no pegar ni imprimir su valor.

## Revisar el flujo sin ejecutar nada

Desde la raíz del repositorio, en el terminal del Dev Container:

```bash
uv run python scripts/publish_local.py --dry-run
uv run python scripts/publish_local.py --dry-run --publish
```

El segundo comando muestra también las operaciones remotas previstas, sin ejecutarlas. Los valores entre `<...>` son descripciones de IDs/digests que se resolverán durante la ejecución, no comandos listos para copiar. La simulación no conecta con Docker/GHCR, construye imágenes ni ejecuta tests.

## Construir y validar sin publicar

```bash
uv run python scripts/publish_local.py
```

Por defecto usa `ghcr.io/brunofelixns/mealie-mcp-server`, la versión de `pyproject.toml` y el builder `default`. Se pueden indicar explícitamente:

```bash
uv run python scripts/publish_local.py \
  --image ghcr.io/brunofelixns/mealie-mcp-server \
  --builder default
```

El modo local acepta cambios sin commit y los identifica con una revisión `-dirty`. Para publicar se exige un checkout limpio, incluyendo archivos nuevos. Además, calcula una huella de los archivos del checkout y vuelve a comprobarla antes de publicar; no editar código/documentación mientras se valida un release.

El flujo ejecuta, en orden:

1. Preflight Docker/Buildx/plataformas/red y snapshot del código.
2. `uv sync --frozen`, gate de versión y migración, Ruff/formato, mypy y documentos generados.
3. Suite ordinaria con cobertura y checker de compatibilidad. Excluye `tests/containers` porque se ejecuta por separado para cada arquitectura; los E2E live también se ejecutan aparte.
4. Build runtime por arquitectura con `--sbom=true --provenance=mode=max --load`. Verifica versión/revisión/plataforma e ID; exporta cada imagen a OCI y comprueba los payloads SBOM y provenance ligados al runtime correcto.
5. Para cada imagen inmutable: pruebas de contenedor stdio/HTTP, los cuatro recorridos E2E con Mealie desechable y escaneo `--enforce`. Se rechazan secretos y vulnerabilidades HIGH/CRITICAL con corrección disponible; otros avisos permanecen en el informe, según la política existente del repositorio.

Las pruebas del Compose portátil conceden hasta 60 segundos al arranque y 40 segundos a las lecturas MCP en ejecución nativa. Cuando el controlador x86 ejecuta una imagen ARM bajo QEMU, se amplían a 120 y 90 segundos respectivamente; la sonda de prueba puede tardar hasta 10 segundos. Se conservan salud, autenticación y API, con los mismos límites de producción.

Un fallo detiene el flujo y evita cualquier push. El informe diferencia `verified_local` de `published`; una simulación o un build aislado no equivalen a una publicación validada.

## Autenticarse y publicar

### Con GitHub CLI

Como opción adicional, se puede reutilizar la sesión de `gh`. El flujo web autentica GitHub CLI, pero no garantiza que GHCR autorice una publicación; la ruta recomendada para este proyecto es el PAT classic de la sección siguiente. La feature GitHub CLI está incluida en `.devcontainer/devcontainer.json`; reconstruir el Dev Container para añadirla a uno existente. `gh` gestiona un token y Docker lo recibe por entrada estándar.

Desde el terminal Bash del Dev Container:

```bash
gh auth login --hostname github.com --web --git-protocol https --scopes write:packages
gh auth status --hostname github.com
```

Si ya tenías sesión, ampliar sus permisos en lugar de repetir el login:

```bash
gh auth refresh --hostname github.com --scopes write:packages
```

Transferir la credencial directamente a Docker, sin imprimirla ni escribirla en un archivo:

```bash
set -o pipefail
gh auth token --hostname github.com --user brunofelixns \
  | docker login ghcr.io --username brunofelixns --password-stdin
```

El usuario de ambos comandos debe corresponder a la cuenta autenticada que tiene permiso de publicación; para otra cuenta, sustituir `brunofelixns` en ambos. `gh auth status` permite comprobar cuenta y scopes sin mostrar el token. No ejecutar `gh auth token` solo ni activar `set -x`. Si usas varias cuentas, seleccionar la apropiada con `gh auth switch --hostname github.com --user brunofelixns` antes de ampliar permisos. [Login de gh](https://cli.github.com/manual/gh_auth_login) · [Scopes](https://cli.github.com/manual/gh_auth_refresh) · [Token por entrada estándar](https://cli.github.com/manual/gh_auth_token).

`gh` usa el almacén de credenciales del sistema cuando está disponible; en un contenedor sin él puede guardar su token en texto plano en su configuración. Docker también depende de su credential helper. La sesión resulta más cómoda, pero no es automáticamente más segura que un PAT con permisos limitados. No montar estas configuraciones dentro del repositorio. Reconstruir el contenedor puede requerir volver a autenticarse.

### Con un PAT dedicado

Como ruta documentada por GHCR, crear un **PAT GitHub classic** limitado a `write:packages` e iniciar sesión en el mismo Dev Container donde ejecutarás el script:

```bash
docker login ghcr.io --username brunofelixns
```

Introducir el PAT como contraseña cuando Docker lo pida. Un PAT dedicado permite separar permisos y caducidad del login general de `gh`. GHCR documenta PAT classic para este uso, no PAT fine-grained. [Autenticación y publicación GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

Con cualquiera de las opciones, el script reutiliza las credenciales de Docker: no acepta argumentos de token, no los lee ni los guarda en el repositorio o en `.env`. `gh auth login` por sí solo no autentica Docker. Para cerrar las sesiones: `docker logout ghcr.io` y, si corresponde, `gh auth logout --hostname github.com`.

### Publicar después del login

Con el código guardado en commits y el checkout limpio:

```bash
uv run python scripts/publish_local.py --publish
```

`--publish` vuelve a ejecutar todas las validaciones locales. Después etiqueta por ID inmutable y sube:

```text
ghcr.io/brunofelixns/mealie-mcp-server:<version>-amd64
ghcr.io/brunofelixns/mealie-mcp-server:<version>-arm64
ghcr.io/brunofelixns/mealie-mcp-server:<version>
```

Antes de crear la última etiqueta comprueba los digests remotos de ambas variantes. Compone el manifest con referencias `image@sha256:...`, verifica que contiene exactamente ambos runtimes probados y las attestations originales vinculadas a sus digests, y registra su digest final. No cambia la visibilidad del paquete ni crea una release GitHub. GHCR crea paquetes privados por defecto; configurar visibilidad/acceso desde Packages según se necesite. El Dockerfile ya incluye la label de repositorio fuente.

No usar `docker buildx --push` por fuera del script como sustituto de estos gates: ese comando publicaría antes de ejecutar las comprobaciones locales sobre sus imágenes finales.

## Evidencias y recuperación

Los resultados quedan en `artifacts/local-release/<id>/`, fuera de Git:

- `summary.json`: estado, fase fallida, revisión/huella, imágenes y digests, tags intentados/confirmados y digest publicado si hubo éxito.
- Logs numerados por comando: build, checks, tests, E2E, scanner y operaciones GHCR. El script imprime la ruta de cada log antes de iniciar la operación. Las inspecciones registran solo redes o metadata necesaria de imagen, sin variables de entorno; los timeouts conservan también stderr.
- `coverage.json` y `pytest.xml`: suite ordinaria y cobertura.
- `amd64/` y `arm64/`: metadata de build, `runtime.tar` con attestations, JUnit de contenedores, resumen E2E independiente, reporte/SBOM del scanner. Los informes detallados del E2E conservan su carpeta única bajo `artifacts/e2e/`.

Los archivos OCI pueden ocupar varios cientos de MB por variante; el scanner guarda también su archivo exportado. El script conserva imágenes y artefactos para revisión, sin `prune`. Los servicios Mealie/MCP y volúmenes desechables de las pruebas sí se retiran mediante el controlador E2E.

No hay reintentos automáticos de escrituras. Si falla la segunda subida o su verificación, no se intenta crear la etiqueta principal. `pushedTags` contiene operaciones confirmadas; `attemptedTags` incluye también aquellas cuyo resultado puede ser desconocido tras un fallo de red. Inspeccionar esos tags con `docker buildx imagetools inspect` antes de decidir repetir. Si falla después de crear el manifest, la etiqueta principal puede existir: consultar los logs y verificarla por digest; el script no promete rollback remoto.

Con un paquete privado, un error de permisos se resuelve revisando login, scopes, cuenta y permisos del paquete. No sustituir la validación fallida por una confirmación manual ni presentar un push parcial como éxito.

## Desplegar

Tras una publicación correcta, configurar la etiqueta multiarch o el digest en `docker/.env`:

```dotenv
MEALIE_MCP_IMAGE=ghcr.io/brunofelixns/mealie-mcp-server:0.1.0
```

Desde la carpeta `docker` del servidor:

```bash
docker compose pull mealie-mcp
docker compose up --detach --wait mealie-mcp
```

Docker selecciona la arquitectura adecuada. [Despliegue Docker](../docker/README.md) · [Contenedores](containers.md) · [E2E local](testing/local-e2e.md). Los resultados de preparación de este script se registran en el [plan y ledger](superpowers/plans/2026-10-30-local-ghcr.md); preparar el script no significa que se haya publicado una imagen.

## Comprobar el launcher Windows

Desde el **terminal Linux del Dev Container**:

```bash
uv run python tests/windows/runner.py
```

El runner descarga una imagen PowerShell fijada por digest y ejecuta el launcher con Docker simulado en un contenedor sin red ni socket Docker; comprueba acciones, separación de credenciales, selección del checkout y propagación de errores. Elimina únicamente su propio contenedor al terminar. No inicia sesión ni publica. La comprobación real en Windows se hace con `Plan`; las pruebas simuladas no demuestran un login OAuth ni una publicación GHCR reales.

## Publicación 0.1.0 comprobada

El 2026-10-30 se verificó por lectura la etiqueta multiarch `0.1.0` con digest `sha256:9b76115fa5b4796408c779c30f4ff96ceea63ba4db3b8dff716bfa43576b571b`. Contiene exactamente los dos runtimes y sus attestations del run `cf036c87d382`, cuyo commit fuente es `f5e70a6c7241ad0f7ca9e0317547d9239047bc16`. Ese run pasó 983 pruebas ordinarias, 7 de contenedor y 4 E2E por arquitectura, y ambos escaneos antes de la publicación. El paquete es privado y está asociado al repositorio.

El primer push fue denegado; se conservó su informe y se preparó una recuperación temporal con comprobación de fuente, evidencias e imágenes inmutables. La comprobación posterior de GHCR confirma que la etiqueta utilizable existe. Para desplegarla en otro servidor o desde Docker de Windows, iniciar sesión en **ese cliente Docker** si no dispone de credenciales de lectura; la sesión del Dev Container no autentica automáticamente los demás clientes.
