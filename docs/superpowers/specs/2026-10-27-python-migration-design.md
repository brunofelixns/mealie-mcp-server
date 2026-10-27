# Diseño de migración completa de Mealie MCP a Python

Fecha: 2026-10-27.
Estado: diseño propuesto para revisión; no implementado.
Revisión independiente: completada el 2026-10-27, sin cuestiones importantes pendientes para planificar. El usuario solicitó el plan antes de implementar; [plan preparado](../plans/2026-10-27-python-migration.md), con ejecución todavía pendiente.
Referencia: timo-reymann/mealie-mcp-server @ d027e1b4a314d781a322f1f91e37840f01464d77.
Inventario: [lectura humana](../../migration/compatibility-inventory.md) y [JSON](../../migration/compatibility-inventory.json).

## 1. Intención y decisiones confirmadas

Migrar íntegramente el servidor existente a Python, conservando sus 78 herramientas, un prompt, instrucciones, flujos compuestos y compatibilidad de datos. El usuario ha elegido FastMCP y los dos transportes: stdio local y HTTP remoto. Todo el trabajo de implementación, comprobación y construcción se realizará en un Dev Container. La entrega incluirá una imagen OCI/Docker de producción que ejecute el MCP.

Para el HTTP remoto se ha elegido uso personal mediante token Bearer. Este token autentica el acceso al MCP; MEALIE_API_KEY sigue siendo una credencial independiente del MCP hacia Mealie. Un despliegue representa una instancia y una cuenta Mealie. Quien posea el token remoto podrá utilizar las operaciones que permite esa cuenta, incluidas escrituras y borrados.

No se ha aprobado todavía la implementación de este documento. Los nombres de archivos, comandos y configuraciones siguientes describen entregables futuros. Al comenzar, la carpeta local estaba vacía y sin .git; en esta fase solo se han creado los documentos solicitados.

## 2. Enfoques considerados y elección

| Enfoque | Ventaja | Coste / ajuste al objetivo |
|---|---|---|
| SDK oficial MCP directamente | Control cercano al protocolo y menor capa de framework. | Más integración para registro, pruebas y operación. Alternativa presentada y no elegida por el usuario. |
| FastMCP y lógica Mealie independiente | Validación, transporte y registro con una API común; aislamiento de la lógica migrada. | Dependencia del framework y sus cambios; se controla con versiones fijadas y pruebas de contrato. Elegido por el usuario. |
| Generar un servidor directamente desde OpenAPI de Mealie | Útil para una exposición REST genérica. | No conserva el catálogo curado ni los algoritmos de ingredientes, cursores, verificación y lotes. Descartado por falta de paridad. |

Se migrará por módulos con el original como referencia temporal. El resultado entregado será completamente Python: no habrá puente al servidor TypeScript, runtime Node, npm/Yarn, scripts JavaScript ni workflows que necesiten ejecutar Node como parte propia del proyecto. Las acciones de GitHub y el editor pueden tener su runtime interno, sin ser dependencias del servidor.

## 3. Objetivos, límites y definición de éxito

Obligatorio:

1. Mantener nombres y semántica pública de las 78 herramientas, el prompt y todas las instrucciones, con las diferencias controladas del inventario.
2. Disponer de un catálogo único y un cliente Mealie compartido por stdio y HTTP; probar ambos mediante JSON-RPC real.
3. Mantener las variables MEALIE_BASE_URL, MEALIE_API_KEY y el diagnóstico opcional MEALIE_MCP_DEBUG.
4. Portar la lógica de todos los 21 módulos lib, los wrappers REST, escenarios de los 42 tests y la generación documental.
5. Entregar entorno reproducible, paquete wheel/sdist, CLI, imagen ejecutable y CI para validarlos.
6. Conservar atribución y licencia MIT; mantener trazabilidad al commit original.
7. Mantener Mealie como fuente de datos. El MCP no incorpora base de datos propia ni decide semánticamente cómo clasificar o interpretar ingredientes.

Fuera de alcance: ampliar la cobertura a todos los endpoints de Mealie, un agente LLM propio, nuevas interfaces visuales, multiusuario, OAuth/OIDC, colas persistentes o extensiones Tasks, y despliegue efectivo en una infraestructura aún no elegida. El token Bearer personal no equivale a interoperabilidad OAuth: los clientes que solo admitan un login OAuth requerirán otra fase o un gateway compatible.

La imagen se construirá y probará. Publicarla en un registry y operar un endpoint público son acciones posteriores: el diseño de CI las contempla para el repositorio del usuario, sin asumir permisos sobre el upstream.

## 4. Stack y control de versiones

| Componente | Elección propuesta |
|---|---|
| Runtime | CPython 3.14, versión patch fijada en imágenes y entorno. |
| MCP | FastMCP 4.1.4 y SDK oficial mcp 2.3.0 como referencia verificada a fecha del diseño; resolver y bloquear dependencias compatibles antes del primer código. |
| Modelos | Pydantic 2 y pydantic-settings; schemas estrictos para entrada, modelos de API capaces de conservar campos desconocidos. |
| HTTP hacia Mealie | HTTPX2 AsyncClient, alineado con FastMCP 4; pool y transporte de descargas explícitos. |
| Concurrencia | asyncio con límites explícitos; pruebas que comprueben picos, orden y aislamiento. |
| Tooling | uv, Ruff, mypy, pytest, pytest-asyncio, pytest-cov. |
| Packaging | pyproject.toml y hatchling; src layout; uv.lock versionado. |
| Contenedores | Dockerfile por etapas con target development y target runtime; Docker Compose para HTTP y pruebas. |
| CI | GitHub Actions ejecutando los comandos del Dev Container y smoke tests de la imagen final. |

Las versiones publicadas se comprobaron en GitHub Releases. Las páginas de documentación de FastMCP siguen main y pueden contener funciones posteriores; cualquier API usada deberá verificarse contra 4.1.4 o una actualización deliberada y registrada. uv se fijará a una versión e imagen reales al implementar; este documento no inventa digests ni afirma que ya exista un lock resuelto.

Una única metadata de paquete gobernará la versión anunciada por el MCP, la CLI y la imagen. Se documentará la corrección del desacuerdo original entre paquete 2.1.0 y anuncio 1.0.0; la versión inicial del port se decidirá al configurar el repositorio de destino, antes de publicar.

## 5. Arquitectura propuesta

```text
CLI (--transport stdio|http)
             |
      create_server(settings)
             |
       catálogo FastMCP
     tools + prompt + instructions
             |
      servicios deterministas
             |
       cliente Mealie async
             |
          Mealie REST
```

En HTTP hay autenticación delante del endpoint MCP y rutas mínimas de salud fuera de ese endpoint. Ambos modos registran los mismos nombres, argumentos y lógica. Un proceso usa un transporte; dos procesos pueden usar la misma imagen con comandos distintos.

Estructura futura:

```text
.devcontainer/
  devcontainer.json
  compose.yaml
Dockerfile
compose.production.yaml
compose.integration.yaml
pyproject.toml
uv.lock
.python-version
.env.example
src/mealie_mcp_server/
  __init__.py
  __main__.py
  cli.py
  config.py
  server.py
  auth.py
  health.py
  mealie/
    client.py
    errors.py
    api/
      recipes.py
      mealplans.py
      shopping_lists.py
      categories.py
      tags.py
      foods.py
      units.py
      equipment.py
      users.py
  models/
    inputs/
    results/
  services/
    recipe_ingredients.py
    recipe_instructions.py
    recipe_taxonomy.py
    recipe_equipment.py
    recipe_classification.py
    recipe_ingredient_parsing.py
    recipe_enrichment.py
    recipe_audit.py
    recipe_discovery.py
    candidate_matching.py
    multi_query_lookup.py
    organizer_resolution.py
    ingredient_resolution.py
    taxonomy_resolution.py
    recipe_rating.py
    last_made.py
  support/
    concurrency.py
    recipe_scan.py
    query_filter.py
    safe_download.py
    recipe_image.py
  tools/
    registry.py
    recipes.py
    mealplans.py
    shopping_lists.py
    categories.py
    tags.py
    foods.py
    units.py
    equipment.py
  prompts.py
  resources/server-instructions.md
tests/
  unit/
  contracts/
  integration/
  containers/
  fixtures/compatibility/
scripts/
  generate_docs.py
  check_compatibility.py
docs/
  migration/
  superpowers/specs/
.github/workflows/
  ci.yaml
  release.yaml
```

La distribución exacta entre servicios y support queda al implementador, manteniendo el mapa del inventario. No hace falta introducir repositorios de datos, un bus de eventos ni otra capa abstracta sin uso.

### Lifecycle y cliente

create_server construye el registro sin leer secretos en import-time ni efectuar llamadas a Mealie. El lifespan crea/cierra un AsyncClient con base URL fija, Bearer Mealie, pooling y TLS verificado. Servicios y handlers reciben dependencias explícitas, sin caches globales entre configuraciones.

Las llamadas a Mealie aceptan http(s), incluidas direcciones privadas configuradas por el operador, porque Mealie puede estar en la red Docker o en el host. Esto es distinto del descargador de URLs no confiables de imágenes, que conserva su prohibición de destinos privados.

Timeouts iniciales propuestos: conexión 5 s, read/write 30 s y espera de pool 5 s; pool de hasta 20 conexiones. Son decisiones operativas propuestas que se validarán con lotes y tiempos reales. El descargador conserva 30 s como plazo total, incluyendo DNS, redirecciones y cuerpo, y las auditorías conservan su presupuesto de 20 s. No se reintentan escrituras automáticamente.

Una cancelación o desconexión no demuestra que Mealie no haya aplicado una escritura. Una vez enviado un PATCH/PUT que requiere verificación, la fase corta de verificación y recuperación debe poder terminar con un plazo acotado aunque se desconecte el cliente; probar cancelación durante lectura, envío, verificación y rollback. No se promete recuperación durable tras matar el proceso o contenedor.

## 6. Compatibilidad de entradas, respuestas y lógica

- Conservar camelCase público; los aliases Pydantic permiten un código Python idiomático sin renombrar parámetros MCP.
- Configurar extra=forbid en objetos declarados, incluidos anidados. No cerrar mapas arbitrarios que el original deja abiertos.
- Usar presencia de campos/model_fields_set/exclude_unset para distinguir omitido de null. No usar exclude_none indiscriminadamente.
- Evitar coerciones de strings a números/bools que Zod rechazaba; int/bool y UUID requieren pruebas explícitas. Mantener UUID solo donde el original lo exige.
- Conservar los JSON text content actuales y su semántica de isError. La captura del original es la autoridad; comparar también datos semánticos y registrar diferencias de formato.
- Añadir outputSchema/structuredContent solo mediante casos de compatibilidad por herramienta. Evitar que FastMCP envuelva un array/string en una forma pública distinta sin detectar el cambio.
- Los metadatos openai/fileParams se conservan solo en la herramienta file y se prueban mediante tools/list real.
- Mantener el prompt weekly-meal-plan y el archivo de instrucciones completo; corregir per_page a perPage en sus referencias al argumento real.
- Las anotaciones readOnlyHint/destructiveHint/idempotentHint/openWorldHint serán explícitas tras revisar efectos, sin usarlas como controles de seguridad.
- Los cursores v1 originales seguirán siendo válidos; se probará el cruce TS->Python y Python->TS. No cambiar cursor, orden o serialización para hacerlos más idiomáticos.
- Conservar PATCH focalizados, no-ops, referenceId, verificación de asociaciones y restauración best effort. La comprobación expectedUpdatedAt no es una operación atómica en Mealie.
- El original puede producir un texto MCP inválido al serializar undefined tras un 204. Caracterizar cada DELETE. Si se confirma, entregar un texto de éxito válido y documentar esa corrección, sin simular que era una respuesta ya compatible.

La capa de resultados de API preservará los campos que no modifica; un modelo tipado incompleto nunca debe borrar información al volver a guardar una receta o un organizador.

## 7. Transportes y CLI

CLI futura: `mealie-mcp-server --transport stdio` por defecto y `mealie-mcp-server --transport http --host 0.0.0.0 --port 8000` para red. `python -m mealie_mcp_server` será equivalente. --help y --version no necesitarán credenciales; el arranque operativo sí.

### stdio

- stdout exclusivamente para JSON-RPC MCP; logs, timings y errores de configuración a stderr. Sin banners ni códigos ANSI mezclados con el protocolo.
- El cliente inicia el proceso y suministra MEALIE_BASE_URL/MEALIE_API_KEY por entorno o secretos en archivos.
- EOF o señal termina el servidor y cierra el pool; status de salida no cero para configuración inválida.
- En Docker usar stdin conectado y sin pseudo-TTY: docker run --rm -i; nunca -t para el transporte.
- El token MCP HTTP no se exige en este modo. Una configuración de HTTP guardada no convierte stdio en un transporte autenticado.

### HTTP

- Streamable HTTP en /mcp, conservando compatibilidad de protocolo delegada al SDK.
- CPython/ASGI sirve el endpoint con un worker inicialmente; sin sticky sessions como requisito del modo moderno. El modo de compatibilidad con clientes antiguos se verifica aparte antes de escalar.
- Negociar la revisión moderna 2026-07-28 y los clientes de la era anterior que soporta el SDK. La suite debe exigir como mínimo casos modernos y 2025-11-25.
- Tratar la desconexión, cancelación y errores parciales como contratos observables. No implementar otro servidor /sse legacy por iniciativa propia.
- Un proxy de producción deberá admitir respuestas JSON y streaming SSE de una petición, sin buffering ni compresión que rompan el flujo; plazos del proxy coherentes con el servidor.
- Propuesta de límite de cuerpo 32 MiB para permitir una imagen base64 de 10 MiB con su overhead. Se comprobará en ASGI y se documentará el mismo mínimo para el proxy. Probar también resultados grandes con el cliente, cuyo límite de evento SSE puede ser distinto.
- Health: GET /healthz comprueba vida del proceso; GET /readyz comprueba lifespan/configuración inicializados. Respuestas mínimas sin datos sensibles; ninguna ruta hace llamadas a Mealie. No presentar readiness como garantía de que el proveedor esté disponible.
- Las rutas de salud quedan fuera del middleware Bearer del MCP y están accesibles en la red privada del contenedor. El proxy público expone /mcp y no necesita publicar las rutas de salud.

## 8. Autenticación HTTP y secretos

Configuración propuesta:

| Variable | Uso y valor por defecto |
|---|---|
| MEALIE_BASE_URL | Obligatoria al operar; URL http(s) configurada por el operador; admite red privada. |
| MEALIE_API_KEY o MEALIE_API_KEY_FILE | Una de las dos; credencial saliente hacia Mealie. Si se dan ambas, error de configuración para evitar ambigüedad. |
| MEALIE_MCP_DEBUG | Opcional; conservar diagnóstico de timings sin payloads/secrets. |
| MCP_TRANSPORT | stdio por defecto; CLI tiene prioridad. |
| MCP_HOST / MCP_PORT | CLI tiene prioridad; localhost/8000 para uso directo. Compose HTTP fija 0.0.0.0 dentro del contenedor. |
| MCP_AUTH_TOKEN o MCP_AUTH_TOKEN_FILE | Token aleatorio independiente, requerido al arrancar HTTP. Ambas formas simultáneas se rechazan. Sin token no se inicia HTTP. |
| MCP_PUBLIC_URL | Origen/base externa, obligatorio en el perfil de producción; con HTTPS para ese perfil. |
| MCP_ALLOWED_HOSTS | Hosts permitidos explícitos; derivar el externo de MCP_PUBLIC_URL y permitir localhost para salud local. Nunca confiar en Host reenviado sin validación. |
| MCP_ALLOWED_ORIGINS | Lista explícita para clientes browser; vacía por defecto. Si llega Origin no permitido, rechazar. Los clientes nativos sin Origin siguen admitidos. |
| LOG_LEVEL | INFO por defecto; logs estructurados a stderr. |
| TZ | UTC si no se proporciona; ejemplos de este usuario con Europe/Madrid. Misma semántica local en desarrollo y producción. |

El TokenVerifier de FastMCP se adaptará para validar el token personal: secreto de al menos 32 bytes aleatorios generado por el operador, comparación de digest en tiempo constante, rechazo de tokens vacíos/malformados, respuesta 401 sin contenido interno y sin reenviar el token del cliente a Mealie. Una identidad fija representa al operador; no hay permisos multiusuario ni emisión de tokens. No usar clases de autenticación documentadas exclusivamente para pruebas como implementación de producción.

No inventar endpoints de OAuth ni anunciar discovery OAuth. El cliente remoto debe poder enviar Authorization: Bearer. Este modo se documentará como autenticación personal, no como cumplimiento del flujo OAuth completo.

La conexión pública tendrá TLS terminado por un reverse proxy/gateway gestionado por el operador. Compose publica HTTP en 127.0.0.1:8000, o comparte una red privada con el proxy; el contenedor del MCP no gestiona certificados. Confiar en cabeceras de proxy solo desde proxies explícitos.

Los ejemplos no contienen credenciales reales. .env, archivos de secrets y configuraciones locales quedan excluidos de Git, contexto Docker y artefactos. Tokens, Authorization, URLs temporales de descarga con firmas, cuerpos de receta y cuerpos crudos de errores del proveedor no se registran. Los mensajes MCP preservan tipo/estado de error y contexto útil con redacción de datos sensibles; toda diferencia respecto al original tendrá prueba y entrada en el registro de cambios.

La descarga file tiene un transporte dedicado: DNS resuelto por salto, IP validada fijada a la conexión, Host/SNI/certificado originales, límite 10 MiB, máximo 3 redirects y plazo total 30 s. Una simple prevalidación DNS seguida de AsyncClient.get con una segunda resolución no satisface el contrato. Aislar este adaptador, verificar contra la API pública del backend HTTP elegida y probar DNS rebinding, mezcla público/privado, IPv4/IPv6 y fallback entre IP públicas.

No crear un permiso para leer rutas del host. `set_recipe_image_from_file` recibe download_url y file_id del host MCP. Dentro de Docker, localhost es el contenedor; una URL temporal debe ser accesible desde él y seguir siendo pública conforme al contrato original. El camino `set_recipe_image_from_url` lo descarga Mealie y conserva sus propias limitaciones de red.

## 9. Dev Container obligatorio

El entorno de desarrollo se construirá desde el target development del mismo Dockerfile de proyecto. Incluye Python 3.14, uv, Git, shell y herramientas de calidad; usuario no root; .venv en volumen Linux separado para evitar contaminación Windows/Linux. El workspace se monta para edición; Python utiliza la virtualenv del contenedor.

.devcontainer/devcontainer.json declarará el Compose de desarrollo, servicio dev, workspaceFolder, usuario remoto, extensiones Python/Ruff y puerto 8000 marcado privado. Un postCreateCommand ejecutará `uv sync --frozen --group dev` una vez exista el lock. La actualización de dependencias será explícita; abrir el entorno no modificará el lock.

Docker Desktop con contenedores Linux es un requisito del host Windows. Para construir y probar la imagen desde el Dev Container se utilizará Docker CLI con acceso al daemon del host mediante docker-outside-of-docker: sin daemon anidado ni contenedor privileged. Este acceso se limita al entorno de desarrollo y CI; no se monta el socket en producción.

El entorno estará operativo sin una cuenta Mealie ni una clave real: los checks unitarios y de contrato usan un fake Mealie controlado. El perfil de integración levanta Mealie desechable, sus dependencias y volúmenes aislados, con imagen fijada y credenciales de fixtures. Ningún servicio arranca contra una URL real por defecto.

Mealie ejecutado en Docker se resuelve por nombre de servicio; Mealie en el host se configura con host.docker.internal en Docker Desktop. No heredar localhost del host sin documentar el cambio de namespace. Secrets de desarrollo se inyectan desde un archivo local ignorado o archivos montados, sin quedar en Docker build args ni layers.

Captura del original: un contenedor de referencia desechable con Node, fijado al commit y lock original, genera snapshots sobre el mismo fake Mealie. Se invoca desde el Dev Container a través de Docker; Node no se instala en el Dev Container Python ni queda como dependencia de producción. Tras cerrar la paridad, los snapshots y su procedencia se conservan y el runner TypeScript deja de ser necesario para el CI ordinario.

Flujo previsto, ejecutado en terminal del Dev Container:

```bash
uv sync --frozen --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run python scripts/generate_docs.py --check
uv build
docker build --target runtime -t mealie-mcp-server:local .
docker compose -f compose.integration.yaml up --abort-on-container-exit --exit-code-from tests
```

Son comandos de diseño: los archivos/lock y el servidor todavía no existen en este entregable. Durante implementación los checks obligatorios se ejecutarán en el contenedor; cualquier verificación auxiliar hecha en el host se identificará como tal.

## 10. Imagen de producción y despliegue

Un Dockerfile contiene stages base, builder, development y runtime. builder genera wheel/entorno de runtime a partir de uv.lock y sin dependencias dev. runtime usa Python slim compatible, CA certificates y datos de zonas horarias; copia solo runtime/paquete y archivos de licencia. Las imágenes y uv se fijan por versión y digest verificados al implementar; se actualizan deliberadamente.

El target runtime:

- No contiene workspace, Node/npm/Yarn, compiladores, tests, .git, herramientas dev ni secretos.
- Incluye el documento de instrucciones como package data y metadatos de versión/licencia.
- Ejecuta como usuario no root con UID/GID documentados. Admite filesystem raíz de solo lectura y tmpfs limitado para /tmp.
- Tiene ENTRYPOINT exec con la CLI Python y CMD por defecto --transport stdio para conservar el modo original.
- Recibe SIGTERM/SIGINT y cierra el cliente; Compose usa init: true y stop_grace_period de 45 s para verificación/limpieza acotadas.
- No tiene un HEALTHCHECK HTTP global que falle en stdio: el perfil HTTP define su propia sonda.
- Etiqueta versión, commit de este port y commit upstream en labels OCI; produce amd64 y arm64 cuando sus smoke tests pasan.

compose.production.yaml contendrá un servicio HTTP con la misma imagen y command --transport http --host 0.0.0.0 --port 8000. Montará secrets *_FILE, publicará solo 127.0.0.1:8000 por defecto, establecerá restart: unless-stopped, read_only, tmpfs /tmp, cap_drop: ALL y no-new-privileges. La sonda HTTP consultará /readyz desde Python dentro del contenedor, sin depender de curl ni de Mealie. El servicio stdio no se deja corriendo con restart: el cliente lo crea bajo demanda.

Uso futuro de la misma imagen:

```bash
# Local, proceso iniciado por el cliente MCP: stdin abierto, sin TTY.
docker run --rm -i --env-file .env.local mealie-mcp-server:local --transport stdio

# Servicio HTTP persistente, con secrets/configuración de producción.
docker compose -f compose.production.yaml up -d
```

El segundo ejemplo requiere completar los secretos y la URL/proxy de destino. Las rutas de archivos en configuraciones de clientes se documentarán para Windows y Linux. El README mostrará también ejecución de paquete por uvx una vez se publique un paquete con nombre disponible.

CI construirá y verificará la imagen en PR. En release, los mismos artefactos aprobados se etiquetarán con versión y SHA y podrán publicarse en el registry del repositorio del usuario con permisos mínimos. Crear SBOM y provenance, comprobar ausencia de secretos/runtime Node y realizar un escaneo de dependencias/imagen; política propuesta: bloquear hallazgos críticos/altos corregibles sin excepción registrada.

El manifiesto multiarch solo se publica si cada arquitectura tiene build y smoke válido; si CI usa emulación se registrará como evidencia emulada. Nada de esto implica que el registry o el endpoint público ya estén creados.

## 11. Pruebas y criterios de aceptación

### A. Fuente de referencia

- Guardar commit, hashes de blobs, lock y licencia del original.
- Ejecutar la suite TypeScript en el runner de referencia y guardar resultado real. Si falla, aislar fallo de entorno/original; no modificar el baseline silenciosamente.
- Capturar tools/list, prompt, instrucciones, inputs inválidos y respuestas usando un fake Mealie idéntico para ambos servidores.
- Para todos los 78 registros, obtener JSON Schema real, defaults, annotations y _meta; el inventario estático no se presenta como esa captura.

### B. Paridad por herramienta y lógica compartida

- 78/78 nombres y firma pública equivalente; prompt 1/1 e instrucciones completas.
- Al menos un caso positivo y uno de rechazo/error por herramienta, más los casos profundos de cada módulo original.
- Comparar solicitudes REST (método/ruta/query/body/multipart), respuestas públicas, efectos y errores parciales. Formato textual y semántica JSON se distinguen.
- Probar objetos anidados estrictos, omisión/null, no-ops, referencias, cursores cruzados y los comportamientos peculiares enumerados en C01..C16.
- Ejercitar rollback que funciona y rollback que falla, duplicados que bloquean lotes, creación serializada y orden por fase de patch_mealplan.
- Reproducir las pruebas de DNS/descarga y 10 MiB/30 s/3 redirecciones, incluidas respuestas fragmentadas.
- Cobertura propuesta: mínimo 90% de líneas y 85% de ramas sobre código propio, con todos los casos críticos anteriores obligatorios aunque el porcentaje pase.

### C. MCP y transporte

- Probar con cliente SDK oficial además del cliente FastMCP para reducir fallos compartidos entre servidor y cliente.
- stdio real por subprocess dentro del Dev Container y por docker run -i: handshake/descubrimiento según versión, catálogo, prompt, llamada de lectura/escritura y EOF.
- HTTP real con red Docker: catálogo idéntico, petición válida, 401 para token ausente/incorrecto, Origin/Host, modern y 2025-11-25, cancelación y cierre.
- Separar conformidad de protocolo de paridad de negocio. Ejecutar el conjunto de conformidad compatible con la versión elegida mediante un runner externo si requiere Node; ese runner no entra en el runtime.
- Los clientes concretos del usuario se verificarán cuando se identifiquen; no afirmar que todas las aplicaciones remotas aceptan Bearer o fileParams.

### D. Contenedores, operación y documentación

- Abrir un Dev Container limpio, instalar lock sin cambios y ejecutar todos los checks allí.
- Construir runtime desde cero y probar stdio/HTTP con esa imagen; no sustituirlo por tests sobre el source mount.
- Verificar arranque sin token HTTP falla; stdio con API key válida no necesita token MCP.
- Probar señales, shutdown, salud sin llamadas Mealie, filesystem de solo lectura, usuario no root y ausencia de secretos/código Node.
- Ejecutar escenarios de lectura/escritura contra Mealie desechable con versión de imagen fijada; registrar esa versión y límites de compatibilidad. Elegirla tras comprobar la versión oficial disponible al implementar, sin usar latest.
- Regenerar y comprobar README, API_COVERAGE, WORKFLOWS, ARCHITECTURE, CONTRIBUTING, ejemplos de clientes, variables, Docker y release.
- Probar instalación del wheel fuera del árbol fuente y presencia de server-instructions.md.
- Guardar comandos, versiones, transportes, plataformas y resultados en un informe de aceptación. Pruebas locales no se presentarán como verificación de un endpoint público.

### E. Diferencias explícitas

El registro de diferencias incluirá: nuevo HTTP/Bearer/salud, metadatos coherentes, documentación perPage/recuentos, redacción de secretos, posible corrección de 204 y ampliaciones estructuradas aprobadas por pruebas. Un cambio en efectos de negocio no se acepta como una diferencia de SDK.

## 12. Secuencia de migración y retirada de TypeScript

Esta secuencia organiza el diseño; el checklist de implementación detallado se escribirá tras aprobarlo.

1. Preparar repositorio de destino, Dev Container, lock inicial y runner original temporal; capturar baseline.
2. Portar configuración, lifecycle, REST/queries/errores y contratos de schemas.
3. Portar organizadores, alimentos, unidades, listas y planes; verificar cada familia.
4. Portar recetas, búsquedas, colas, algoritmos de auditoría, ingredientes/instrucciones, imágenes y ratings.
5. Integrar prompt/instrucciones, catálogo, versión, stdio y HTTP/Bearer; mantener los checks de contrato en cada módulo.
6. Cerrar Docker runtime, CI, artefactos, documentación y matriz de aceptación.
7. Retirar implementación TS, package/Yarn/tsconfig/Vitest/ESLint/Husky y generador JS si se incorporaron temporalmente; actualizar opencode, Renovate, Sonar/coverage y workflows. Conservar baseline declarativo, procedencia, licencia e historia.
8. Verificar clon/checkout limpio dentro del Dev Container y ejecutar paquete/imagen finales; preparar entrega y publicación cuando haya destino.

La primera entrega funcional parcial no se etiquetará como migración completa. El punto de cambio de consumidores será después de A..E y del smoke del contenedor de producción. Se conservará identificada la última imagen original como recuperación operativa; no se promete revertir datos que ya haya escrito Mealie.

## 13. Decisiones propuestas y configuración pendiente

Acordado por el usuario: FastMCP, paridad completa, stdio + HTTP, trabajo en Dev Container, imagen de producción y autenticación personal Bearer.

Propuesto por el agente y revisable al aprobar el diseño: Python 3.14; un proceso/transporte; CLI stdio por defecto; /mcp:8000; secrets separados; runtime no root; salud local; UTC por defecto con ejemplos Europe/Madrid; límites iniciales de pool/timeouts; targets Docker comunes; criterios de cobertura y cambios controlados descritos.

Queda al implementador: organización fina de funciones, pin patch/digests tras resolver dependencias, adaptador de DNS fijado con API pública probada, fixtures y framework concreto de fake Mealie, y optimizaciones que no cambien el contrato.

Se necesitará antes de publicar/desplegar: repositorio/registry de destino, nombre disponible de paquete, dominio/HTTPS/proxy y ubicación de la instancia Mealie. No bloquean construir y probar el port localmente con fixtures. Los secretos reales se configurarán por un canal local seguro; no se pedirán en el chat.

## 14. Fuentes

- [Código upstream fijado](https://github.com/timo-reymann/mealie-mcp-server/tree/d027e1b4a314d781a322f1f91e37840f01464d77).
- [FastMCP 4.1.4 publicado](https://github.com/PrefectHQ/fastmcp/releases/tag/v4.1.4).
- [SDK Python MCP 2.3.0 publicado](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0).
- [Dependencias FastMCP 4.1.4](https://github.com/PrefectHQ/fastmcp/blob/v4.1.4/fastmcp_slim/pyproject.toml).
- [Cambios MCP 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/changelog).
- [Transportes MCP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports).
- [Autorización MCP](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization).
- [Ejecución FastMCP](https://gofastmcp.com/deployment/running-server).
- [Verificación de tokens en FastMCP](https://gofastmcp.com/servers/auth/token-verification).
- [Referencia Dev Containers](https://containers.dev/implementors/json_reference/).
- [uv](https://docs.astral.sh/uv/).
