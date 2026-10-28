# Configuración del servidor Python

La CLI carga esta configuración antes de arrancar stdio o HTTP. No se lee .env automáticamente: el cliente/proceso debe inyectar variables o Docker debe recibir un env_file explícito.

| Variable | Uso |
|---|---|
| MEALIE_BASE_URL | URL http(s) obligatoria. Admite red privada y subruta; se quitan barras finales. Sin credenciales embebidas, query o fragmento. |
| MEALIE_API_KEY / MEALIE_API_KEY_FILE | Una sola forma obligatoria. Archivo UTF-8 dentro del contenedor; se quita el salto de línea final. |
| MCP_TRANSPORT | stdio por defecto; http activa sus requisitos de autenticación. |
| MCP_HOST / MCP_PORT | 127.0.0.1:8000 por defecto; puerto1..65535. --host y --port prevalecen. |
| MCP_AUTH_TOKEN / MCP_AUTH_TOKEN_FILE | Obligatorio solo en HTTP; independiente de Mealie, mínimo32caracteres ASCII visibles sin espacios. Ambas formas se rechazan. En stdio no se exige ni se lee su archivo. |
| MCP_PUBLIC_URL | Base externa para producción; su host se añade a los permitidos. |
| MCP_REQUIRE_HTTPS | false en desarrollo; true exige MCP_PUBLIC_URL con HTTPS al usar HTTP. El perfil HTTP de producción lo activa. |
| MCP_ALLOWED_HOSTS | Hosts separados por coma; loopback permitido para salud. |
| MCP_ALLOWED_ORIGINS | Orígenes separados por coma; vacía por defecto. No hay CORS abierto. |
| MEALIE_MCP_DEBUG / LOG_LEVEL | Timings opcionales; nivel INFO por defecto. Sin payloads ni secretos. |
| TZ | UTC por defecto; debe existir en tzdata. Se puede usar Europe/Madrid. |

Los secretos reales no se incluyen en docs, Git, imágenes o logs. El operador generará el token HTTP con un generador criptográfico de al menos32bytes aleatorios; validar longitud no demuestra aleatoriedad. No reutilizar MEALIE_API_KEY como MCP_AUTH_TOKEN.

Los paths *_FILE son del contenedor. No hay un parámetro MCP para leer rutas del host. stdio proporciona la credencial Mealie al proceso; HTTP valida además su token propio y nunca lo reenviará a Mealie.

load_settings utiliza solo la captura de entorno suministrada. No se mezcla con variables ajenas del proceso ni se consultan claves del transporte inactivo. Los errores nombran campos sin mostrar valores.

[Ejemplo](../.env.example) · [Diseño](superpowers/specs/2026-10-27-python-migration-design.md).
