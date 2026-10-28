# Clientes MCP

El servidor ofrece el mismo catálogo de 78 herramientas y el prompt weekly-meal-plan por stdio y Streamable HTTP. La negociación automática usa 2026-07-28; clientes anteriores pueden negociar 2025-11-25. Las diferencias declaradas están en [el registro de compatibilidad](migration/differences.md).

## Desarrollo local por stdio

Desde el terminal del Dev Container, inyectar MEALIE_BASE_URL y MEALIE_API_KEY (o MEALIE_API_KEY_FILE) y configurar el cliente:

```json
{
  "mcpServers": {
    "mealie": {
      "command": "uv",
      "args": ["run", "--frozen", "mealie-mcp-server", "--transport", "stdio"],
      "env": {
        "MEALIE_BASE_URL": "http://mealie:9000",
        "MEALIE_API_KEY_FILE": "/run/secrets/mealie_api_key"
      }
    }
  }
}
```

El directorio de trabajo del cliente debe ser el repositorio dentro del Dev Container. `python -m mealie_mcp_server` y `mealie-mcp-server` son equivalentes. `--help` y `--version` no requieren credenciales. Los argumentos CLI prevalecen sobre las variables correspondientes; no se carga .env automáticamente.

En Windows y Linux se ejecuta la aplicación en el contenedor Linux. Para conectar un cliente del host con el Dev Container ya abierto, usar `docker` como command y estos args (sustituir el nombre por el de su contenedor):

```json
["exec", "-i", "--user", "vscode", "--workdir", "/workspaces/mealie-mcp-server", "--env", "MEALIE_BASE_URL", "--env", "MEALIE_API_KEY", "mealie-mcp-development-dev-1", "uv", "run", "--frozen", "mealie-mcp-server", "--transport", "stdio"]
```

Las variables deben existir en el entorno del cliente. No añadir `-t`: un TTY altera el canal. stdout contiene solo JSON-RPC; logs y diagnósticos van a stderr. El contenedor tiene su propia red: localhost dentro de él no apunta al host; usar el nombre del servicio en una red compartida o host.docker.internal para un Mealie del host.

El token HTTP no se exige ni se lee en stdio. EOF, SIGTERM y SIGINT cierran el cliente HTTP de Mealie. Un puente POSIX de entrada acotado transforma las señales en EOF porque la lectura de stdin del SDK 2.3.0 usa un hilo no cancelable; no modifica APIs privadas del SDK. La ejecución nativa de Windows no está validada: utilizar el contenedor Linux.

La imagen de producción y la conexión HTTP se documentan en las siguientes fases de implementación.
