# Pruebas E2E locales con Mealie y MCP en Docker

La suite invoca las162 herramientas públicas mediante clientes del SDK MCP oficial y la imagen runtime instalada, contra Mealie real. Cubre stdio y Streamable HTTP con Bearer, en las eras MCP2026-07-28 y2025-11-25. No importa el servidor Python dentro del cliente de pruebas.

## Ejecutar

Requisitos: Docker Desktop con contenedores Linux y el repositorio abierto en su Dev Container. Este ya incluye Python, uv, Docker CLI y Compose. El daemon debe poder identificar y conectar el propio Dev Container mediante su hostname. No es necesario instalar Python en Windows ni proporcionar una URL/API key personal.

Desde el terminal del Dev Container:

```bash
uv sync --frozen --group dev
uv run python -m tests.e2e.runner
```

El primer comando del controlador construye el target `runtime` y lo etiqueta `mealie-mcp-server:e2e`. Si la imagen del código actual ya está construida:

```bash
uv run python -m tests.e2e.runner --image mealie-mcp-server:local --no-build
```

`--no-build` prueba exactamente la imagen indicada; reconstruirla después de modificar código de producto. El controlador resuelve su ID inmutable y exige ese mismo ID para HTTP y stdio. Las descargas iniciales de imágenes/dependencias necesitan acceso a sus registries; las llamadas de prueba usan solamente servicios locales.

No lanzar `compose.integration.yaml up` directamente ni exportar credenciales personales. El controlador configura sus variables, genera los secretos, valida la pertenencia de los servicios y prepara el informe. La suite ordinaria excluye el marcador `live`; ejecutar el archivo E2E sin el controlador lo omite, pero el gate del controlador considera incompleta cualquier ejecución sin sus cuatro informes válidos.

## Entorno desechable

Cada ejecución crea un proyecto `mealie-mcp-e2e-<12 hex>` con:

- Mealie3.30.0 fijado por digest, SQLite y datos sintéticos en un volumen exclusivo.
- Un servidor local de PNG y HTML schema.org Recipe. Solo esta instancia Mealie configura `HTTP_ALLOW_LIST=assets`, para probar importación de imagen y receta con su mecanismo oficial.
- MCP HTTP como usuario10001, raíz de solo lectura, sin capacidades adicionales, sin socket Docker ni código montado. Recibe la API key y el Bearer mediante archivos de un volumen de solo lectura.
- MCP stdio lanzado con `docker compose run --rm -T`, desde la misma imagen, sin configurar autenticación HTTP.
- Una red `internal:true`, sin puertos publicados. El Dev Container se conecta temporalmente como cliente/controlador y se desconecta en la limpieza.

El bootstrap inicia sesión con la cuenta inicial de esa instancia desechable, crea una API key propia y genera un Bearer aleatorio distinto. El cliente HTTP comprueba401 sin token, con uno incorrecto y al intentar usar la API key Mealie como Bearer MCP. Después utiliza el Bearer correcto. Los informes no incluyen las credenciales; sus archivos temporales y su volumen se eliminan al terminar.

## Qué se comprueba

Antes del bootstrap se guarda el OpenAPI real y se auditan rutas y el contrato
estructural seleccionado de Mealie 3.30.0. Si falla, no se ejecutan los escenarios
de mutación y se limpian los recursos propios. El contrato versionado no se
regenera automáticamente desde el proveedor; ver [guía 3.30](../mealie-3.30.md).

| Recorrido | Herramientas | Operaciones positivas | Rechazo SSRF esperado | IA sin proveedor | Rechazos de argumentos |
|---|---:|---:|---:|---:|---:|
| stdio · MCP2026-07-28 |162|159|1|2|162|
| stdio · MCP2025-11-25 |162|159|1|2|162|
| HTTP Bearer · MCP2026-07-28 |162|159|1|2|162|
| HTTP Bearer · MCP2025-11-25 |162|159|1|2|162|
| Total requerido |648|636|4|8|648|

Cada combinación exige el catálogo exacto, el prompt `weekly-meal-plan`, la versión negociada y comprobaciones por herramienta. Los campos desconocidos deben rechazarse sin devolver su valor. Una llamada intentada, un error inesperado del proveedor o un nombre repetido no completan la cobertura.

Los escenarios crean y recuperan categorías, etiquetas, alimentos, unidades y equipamiento; comprueban búsquedas y matching; crean/consultan/duplican recetas; modifican escalares, ingredientes e instrucciones con referencias, taxonomía y equipamiento individual y por lotes; consultan las tres colas; actualizan imágenes, valoración/favorito y última preparación; crean/modifican planes; y ejecutan CRUD, lotes y asociaciones de listas de compra. Finalmente fusionan alimentos y eliminan sus registros.

Las mutaciones se contrastan con lecturas HTTP independientes a Mealie. Se comprueba que todos los IDs creados desaparezcan después de los borrados. La [matriz histórica de las78 herramientas](local-e2e-tool-matrix.md) conserva las comprobaciones originales. `recipe_extensions_flow.py` añade 24 operaciones: notas y metadatos, comentarios, compartir, historial con imagen, adjuntos, importación URL/JSON/ZIP y exportación binaria. El manifiesto JSON de cada recorrido conserva cada resultado y [tools.md](../tools.md) sus argumentos públicos.

Los flows `advanced_330`, `collections_330`, `media_330` y `jobs_330` añaden la
comprobación de filtros y sugerencias, sustituciones, temporizadores, parser,
recetarios, acciones, planificación avanzada, descargas e importación SSE/lotes.
El destino de la acción es el servidor local: se comprueba su recepción efectiva,
además de la aceptación asíncrona. Las dos herramientas IA comprueban que Mealie
declara su proveedor desactivado, devuelve el error esperado y no crea recetas ni
repite la escritura. Ese rechazo se contabiliza aparte; los positivos multipart
y SSE con IA están cubiertos mediante respuestas controladas en contratos.

**Límite de la prueba por archivo:** `set_recipe_image_from_file` descarga dentro del MCP y rechaza direcciones privadas por diseño. En esta red local se comprueba ese rechazo concreto y que la imagen anterior no cambie. Su descarga positiva desde una URL pública sigue cubierta por pruebas controladas de descarga/transporte de la suite Python; no se presenta como descarga positiva E2E local. No se introduce un bypass ni se desactiva la protección. `set_recipe_image_from_url` descarga dentro de Mealie y sí realiza una importación positiva desde el servidor local permitido.

La suite verifica un escenario completo y un rechazo de argumentos por herramienta y combinación; no pretende agotar todas las combinaciones de parámetros. Los casos de borde, cancelación, recuperación, contratos originales y límites de payload siguen en la suite ordinaria.

## Informes y fallos

Cada ejecución escribe en `artifacts/e2e/<proyecto>/`:

| Archivo | Evidencia |
|---|---|
| `summary.json` | Resultado, fase de fallo si procede, imagen/plataforma/revisión, gate y limpieza |
| `openapi.json` / `api-audit.json` | OpenAPI del proveedor y auditoría de rutas/contrato previa al bootstrap |
| `case-<transporte>-<protocolo>.json` | Herramientas, aserciones, rechazos de entrada, cobertura y última llamada |
| `pytest.xml` / `pytest.log` | Casos ejecutados y diagnósticos de pytest |
| `build.log` / `build.json` | Build cuando no se utiliza `--no-build` |
| `mealie-start.log` / `mcp-start.log` | Preparación de servicios |
| `services.log` / `cleanup.log` | Logs de servicios y retirada de recursos propios |

`artifacts/e2e-summary.json` apunta a la última ejecución. El comando solo devuelve0 si pasan pytest, los cuatro informes, el gate exacto de herramientas y la limpieza. El código de salida no se basa únicamente en el resumen de pytest: cuatro tests omitidos también producen un fallo de cobertura. Los artifacts están excluidos de Git; CI los conserva14 días en cada plataforma.

Con `--summary <ruta>` se escribe el resumen en ese destino en lugar del archivo
global. La [CI](../ci.md) ejecuta esta integración por arquitectura sobre la imagen
ya construida y conserva el resumen y la evidencia de limpieza.

La limpieza se ejecuta también ante fallos: desconecta el controlador y hace `down --volumes` exclusivamente sobre el proyecto de esa ejecución. Capturar logs, desconectar, retirar servicios y verificar recursos son pasos independientes: un error de diagnóstico no impide intentar los siguientes. `cleanupErrors` identifica las fases que fallaron; cualquiera de ellas impide un resultado global correcto. Verifica que no queden contenedores, volúmenes ni su red. No utiliza `prune`, no borra redes compartidas y no toca `docker/compose.yaml` de producción.

Si se mata el proceso o se detiene Docker antes del `finally`, consultar el proyecto exacto en el informe. Dentro del Dev Container, comprobar etiquetas y retirar únicamente ese proyecto; sustituir el valor del ejemplo por el ID real:

```bash
project=mealie-mcp-e2e-0123456789ab
docker ps --all --filter "label=com.docker.compose.project=$project"
docker volume ls --filter "label=com.docker.compose.project=$project"
docker network inspect "${project}_default"
# Comprobar que las etiquetas corresponden a esta ejecución antes de continuar.
docker network disconnect "${project}_default" "$HOSTNAME"
MCP_E2E_IMAGE=mealie-mcp-server:e2e \
MCP_E2E_HTTP_HOST="$project-mcp-http-1" \
MCP_E2E_MEALIE_HOST="$project-mealie-1" \
docker compose --env-file /dev/null --project-name "$project" \
  --file compose.integration.yaml --profile stdio down --remove-orphans --volumes
```

No hace falta desconectar una interfaz que ya no existe. La limpieza no retira imágenes compartidas ni cachés de build.

## Resultado observado

La ejecución y sus medidas históricas se registran en [local-e2e-progress.md](local-e2e-progress.md). La evidencia P24 corresponde al test anterior de31 llamadas/28 herramientas y se conserva como historial. El gate actual exige el catálogo completo por combinación. Los resultados locales no demuestran un despliegue remoto, un cliente público concreto ni un job de GitHub Actions completado.

Las pruebas reales motivaron [D10/D11](../migration/differences.md): las actualizaciones de compra obtienen primero el registro y envían un PUT completo, conservando identificadores/campos desconocidos; el borrado en lote repite la query `ids` para cada identificador. Ninguna escritura se reintenta. La [revisión independiente](local-e2e-review.md) registra sus hallazgos y correcciones.
