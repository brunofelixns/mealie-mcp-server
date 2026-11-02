# Desplegar la imagen publicada en GHCR

Esta carpeta permite instalar el MCP con una imagen de GHCR. Solo hay que completar cuatro valores en `.env` y arrancar el servicio.

| Archivo | Para qué sirve |
|---|---|
| `compose.yaml` | Servicio HTTP remoto con Bearer |
| `compose.stdio.yaml` | Proceso stdio que arranca tu cliente MCP |
| `.env.example` | Plantilla de configuración |

Cada Compose contiene un único servicio, sin anchors ni perfiles. Las opciones de protección ya están configuradas; no hace falta editarlas.

## Preparar la configuración

Copiar `compose.yaml` y `.env.example` al servidor Docker, por ejemplo a `/srv/mealie-mcp`. Para stdio, copiar además `compose.stdio.yaml`. En el repositorio solo se versiona `.env.example`; el `.env` local está excluido de Git y del contexto de build.

Desde esta carpeta, si todavía no existe .env:

```sh
cp .env.example .env
chmod 600 .env
```

En PowerShell, usar `Copy-Item .env.example .env` y limitar el acceso al archivo con los permisos del sistema.

Completar estos cuatro valores en `.env`:

| Variable | Valor que debe configurar el operador |
|---|---|
| MEALIE_BASE_URL | URL de la instancia Mealie accesible desde el contenedor. |
| MEALIE_API_KEY | API key de ese Mealie. |
| MCP_AUTH_TOKEN | Token personal aleatorio independiente para los clientes HTTP. |
| MCP_PUBLIC_URL | URL HTTPS que tendrá el MCP detrás del proxy, terminada en /mcp. |

La imagen predeterminada es `ghcr.io/brunofelixns/mealie-mcp-server:latest`. `MEALIE_MCP_IMAGE` y `TZ` son opcionales. Si el `.env` ya existe, editarlo sin volver a copiar la plantilla sobre él.

Para generar el token HTTP en un servidor con OpenSSL: `openssl rand -hex 32`. Guardar el resultado en MCP_AUTH_TOKEN. Si un valor contiene `$`, escribirlo entre comillas simples en .env para evitar interpolación.

La [CI](../docs/ci.md) publica amd64 y arm64 tras fusionar la PR de Release Please
y pasar los checks del tag liberado. `latest` sigue la última versión publicada;
para fijar un despliegue usar `X.Y.Z`, `sha-<SHA completo>` o su digest.
Si se utiliza otro fork, cambiar el namespace
de `MEALIE_MCP_IMAGE`. El tag histórico `0.1.0` se conserva sin sobrescribirlo.

HTTP carga `.env` con `env_file`; debe estar junto a `compose.yaml`. También se pueden añadir allí las opciones avanzadas de la [configuración](../docs/configuration.md), por ejemplo `LOG_LEVEL`, `MCP_ALLOWED_ORIGINS`, `MCP_PUBLISHED_PORT` o `COMPOSE_PROJECT_NAME`. Para usar otro archivo de variables HTTP, cambiar la ruta `env_file`; `--env-file` controla la interpolación de Compose. [Semántica de Docker](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/).

Las credenciales son variables del contenedor, visibles para administradores Docker; proteger `.env` y el acceso al daemon. La variante con secretos de archivo se documenta en [contenedores](../docs/containers.md).

## Descargar y arrancar HTTP

Con .env configurado y la versión ya publicada:

```sh
docker compose config --quiet
docker compose pull mealie-mcp
docker compose up --detach --wait --wait-timeout 60 mealie-mcp
docker compose ps
```

La imagen multiarch selecciona amd64 o arm64 automáticamente. Para un paquete GHCR público no hace falta login. Si es privado, ejecutar antes `docker login ghcr.io --username TU_USUARIO` y proporcionar un token GitHub classic con read:packages cuando lo pida. No guardar ese token en el .env del MCP. [Autenticación de GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

El contenedor sirve HTTP interno en8000. Por defecto solo se publica127.0.0.1:8000: el proxy HTTPS del mismo host debe dirigir /mcp a ese puerto, conservar Host/Authorization, permitir32MiB y desactivar buffering SSE. El cliente se conecta a MCP_PUBLIC_URL y envía `Authorization: Bearer <MCP_AUTH_TOKEN>`. El hostname de esa URL se permite automáticamente. Configurar MCP_ALLOWED_ORIGINS si un cliente de navegador lo necesita. [Ejemplo de proxy y detalles](../docs/http-deployment.md).

Comprobar salud sin enviar credenciales:

```sh
curl --fail http://127.0.0.1:8000/readyz
docker compose logs --tail 100 mealie-mcp
```

La respuesta de salud no consulta Mealie. Cambiar el puerto del curl si se modifica MCP_PUBLISHED_PORT. La aplicación rechaza un Bearer vacío, corto o igual a la API key de Mealie. El servicio ejecuta como10001:10001, con raíz de solo lectura, /tmp temporal, sin capabilities y45s de parada. No se monta código fuente ni el socket Docker.

## Acceso a Mealie y red

localhost dentro del contenedor apunta al propio MCP. Usar la URL publicada de Mealie o una dirección alcanzable desde Docker. Docker Desktop ofrece host.docker.internal para el host; en Docker Engine Linux puede necesitar el mapeo host-gateway.

Si Mealie o el proxy ya están en una red Docker compartida, se puede añadir al final de compose.yaml:

```yaml
networks:
  default:
    external: true
    name: mi_red_mealie
```

La red debe existir. En ella se puede usar MEALIE_BASE_URL=http://mealie:9000 y el proxy puede conectar a mealie-mcp:8000. Crear nombres/proyectos distintos si hay varias instancias. [Redes Compose](https://docs.docker.com/compose/how-tos/networking/).

## stdio local

Solo requiere `MEALIE_BASE_URL` y `MEALIE_API_KEY`; `MCP_AUTH_TOKEN` puede estar vacío. El cliente MCP debe mantener stdin abierto.

```sh
docker compose -f compose.stdio.yaml pull stdio
docker compose -f compose.stdio.yaml run --rm --no-deps -T stdio
```

Usar ese comando desde el cliente MCP con esta carpeta como directorio de trabajo, o indicar paths absolutos con `--env-file` y `-f`. No añadir TTY. Este servicio no publica puertos ni configura healthcheck y recibe explícitamente solo las variables Mealie, zona horaria y logs. El Bearer HTTP no se transmite al proceso stdio.

Si utilizabas el comando anterior con `--profile stdio`, sustituirlo por `-f compose.stdio.yaml`. El archivo HTTP ya no incluye ese servicio.

## Actualizar o detener

Cambiar MEALIE_MCP_IMAGE a una versión publicada y repetir:

```sh
docker compose pull mealie-mcp
docker compose up --detach --wait --wait-timeout 60 mealie-mcp
```

Para detenerlo: `docker compose down`. No se guarda estado de aplicación en volúmenes; las recetas permanecen en Mealie. El Compose de esta carpeta solo descarga imágenes y no contiene build. Para construir desde el repositorio se mantiene [compose.production.yaml](../compose.production.yaml).

[Variables del servidor](../docs/configuration.md) · [Resultados y límites de seguridad de la imagen](../docs/migration/acceptance.md).
