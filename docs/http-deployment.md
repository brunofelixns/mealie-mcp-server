# Acceso remoto por HTTP

El mismo proceso ofrece Streamable HTTP en `/mcp`, con negociación MCP 2026-07-28 y 2025-11-25. Se ejecuta un solo worker. Las herramientas, el prompt y el cliente de Mealie son compartidos por ambos transportes; cada proceso utiliza un transporte.

En el terminal del Dev Container, inyectar las variables de [configuración](configuration.md) y arrancar:

```sh
uv run --frozen mealie-mcp-server --transport http --host 0.0.0.0 --port 8000
```

`MCP_AUTH_TOKEN` o su variante `_FILE` es obligatorio, independiente de `MEALIE_API_KEY`. El cliente envía `Authorization: Bearer <token-personal>`. El verificador compara hashes SHA-256 de longitud fija con compare_digest; no anuncia endpoints OAuth ni permite descubrir credenciales. Un cliente debe admitir un Bearer configurado manualmente. No se afirma compatibilidad con aplicaciones que exigen un flujo OAuth.

`/healthz` devuelve solo `{"status":"ok"}`; `/readyz` da 503 hasta que entra el lifespan y vuelve a 503 al salir. Son endpoints sin autenticación que no consultan Mealie, ni exponen su URL, estado, usuario o secretos. Readiness confirma que el MCP arrancó, no que Mealie sea accesible.

## TLS y proxy

El contenedor sirve HTTP interno. Para producción configurar `MCP_PUBLIC_URL=https://mcp.example.com` y `MCP_REQUIRE_HTTPS=true`, y terminar TLS en un reverse proxy. Publicar el puerto solo en loopback o una red privada compartida con ese proxy. Conservar Host y Authorization; desactivar el buffering de SSE. No se confía en cabeceras forwarded del cliente.

```nginx
location /mcp {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header Authorization $http_authorization;
    proxy_buffering off;
    proxy_read_timeout 120s;
    client_max_body_size 32m;
}
```

FastMCP valida Host y Origin explícitamente. El hostname de MCP_PUBLIC_URL se añade a los permitidos; `MCP_ALLOWED_HOSTS` permite otros nombres concretos. `MCP_ALLOWED_ORIGINS` contiene orígenes de navegador de confianza; se admite además el mismo origen. Este control no habilita CORS: añadir CORS solo si una aplicación de navegador lo necesita y con una lista explícita de orígenes. No usar comodines al exponerlo.

## Tamaño, desconexión y cierre

Se limitan las peticiones a 32 MiB, tanto con Content-Length como con transferencia fragmentada. Esto permite la imagen máxima de 10 MiB después de codificarla en base64. El SDK 2.3.0 aplica por defecto 4 MiB y FastMCP 4.1.4 no expone ese parámetro: el adaptador HTTP configura los atributos públicos del limitador de su instancia durante startup, antes de readiness. Comprueba tipos y distribución de la ruta; un cambio incompatible del framework impide arrancar. No modifica globals ni el servidor privado de FastMCP. Esta integración se debe revisar al actualizar las versiones fijadas.

Una respuesta SSE también puede superar 1 MiB. El cliente oficial permite `streamable_http_client(..., max_sse_event_size=32 * 1024 * 1024)`; ajustar su límite si se consultan recetas grandes. No se añaden un endpoint SSE antiguo, tareas MCP ni reintentos automáticos de escrituras.

Las escrituras verificadas de ingredientes e instrucciones finalizan su comprobación/restauración tras cancelación, con cleanup acotado a 35 segundos. El pool reserva hasta cinco segundos para cerrarse; Uvicorn espera hasta 40 segundos y Compose concede 45 segundos. Un kill forzado o una caída del host puede dejar el resultado remoto sin confirmar: consultar Mealie antes de repetir una escritura. El servidor no incorpora un registro duradero de recuperación.

En HTTP, Uvicorn vuelve a emitir la señal recibida después de cerrar el lifespan: SIGTERM produce salida 143 en Docker (-15 en subprocess). Esa salida es compatible con un cierre limpio; los tests comprueban también el cierre del cliente. En stdio las señales transformadas en EOF salen con código cero.

Las pruebas locales utilizan sockets reales y datos sintéticos. No equivalen a validar un dominio público, un proxy concreto ni un cliente de escritorio concreto.
