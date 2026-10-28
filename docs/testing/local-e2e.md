# Pruebas E2E locales con Mealie y MCP en Docker

La suite invoca las78 herramientas públicas mediante clientes del SDK MCP oficial y la imagen runtime instalada, contra Mealie real. Cubre stdio y Streamable HTTP con Bearer, en las eras MCP2026-07-28 y2025-11-25. No importa el servidor Python dentro del cliente de pruebas.

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

- Mealie3.29.0 fijado por digest, SQLite y datos sintéticos en un volumen exclusivo.
- Un servidor de PNG estáticos local. Solo esta instancia Mealie configura `HTTP_ALLOW_LIST=assets`, para permitir obtener esa imagen privada con su mecanismo oficial.
- MCP HTTP como usuario10001, raíz de solo lectura, sin capacidades adicionales, sin socket Docker ni código montado. Recibe la API key y el Bearer mediante archivos de un volumen de solo lectura.
- MCP stdio lanzado con `docker compose run --rm -T`, desde la misma imagen, sin configurar autenticación HTTP.
- Una red `internal:true`, sin puertos publicados. El Dev Container se conecta temporalmente como cliente/controlador y se desconecta en la limpieza.

El bootstrap inicia sesión con la cuenta inicial de esa instancia desechable, crea una API key propia y genera un Bearer aleatorio distinto. El cliente HTTP comprueba401 sin token, con uno incorrecto y al intentar usar la API key Mealie como Bearer MCP. Después utiliza el Bearer correcto. Los informes no incluyen las credenciales; sus archivos temporales y su volumen se eliminan al terminar.

## Qué se comprueba

| Recorrido | Herramientas | Operaciones positivas | Rechazo SSRF esperado | Rechazos de argumentos |
|---|---:|---:|---:|---:|
| stdio · MCP2026-07-28 |78|77|1|78|
| stdio · MCP2025-11-25 |78|77|1|78|
| HTTP Bearer · MCP2026-07-28 |78|77|1|78|
| HTTP Bearer · MCP2025-11-25 |78|77|1|78|
| Total requerido |312|308|4|312|

Cada combinación exige el catálogo exacto, el prompt `weekly-meal-plan`, la versión negociada y comprobaciones por herramienta. Los campos desconocidos deben rechazarse sin devolver su valor. Una llamada intentada, un error inesperado del proveedor o un nombre repetido no completan la cobertura.

Los escenarios crean y recuperan categorías, etiquetas, alimentos, unidades y equipamiento; comprueban búsquedas y matching; crean/consultan/duplican recetas; modifican escalares, ingredientes e instrucciones con referencias, taxonomía y equipamiento individual y por lotes; consultan las tres colas; actualizan imágenes, valoración/favorito y última preparación; crean/modifican planes; y ejecutan CRUD, lotes y asociaciones de listas de compra. Finalmente fusionan alimentos y eliminan sus registros.

Las mutaciones se contrastan con lecturas HTTP independientes a Mealie. Se comprueba que todos los IDs creados desaparezcan después de los borrados. La [matriz de las78 herramientas](local-e2e-tool-matrix.md) enumera sus comprobaciones; el manifiesto JSON de cada recorrido conserva su resultado y [tools.md](../tools.md) contiene sus argumentos públicos.

**Límite de la prueba por archivo:** `set_recipe_image_from_file` descarga dentro del MCP y rechaza direcciones privadas por diseño. En esta red local se comprueba ese rechazo concreto y que la imagen anterior no cambie. Su descarga positiva desde una URL pública sigue cubierta por pruebas controladas de descarga/transporte de la suite Python; no se presenta como descarga positiva E2E local. No se introduce un bypass ni se desactiva la protección. `set_recipe_image_from_url` descarga dentro de Mealie y sí realiza una importación positiva desde el servidor local permitido.

La suite verifica un escenario completo y un rechazo de argumentos por herramienta y combinación; no pretende agotar todas las combinaciones de parámetros. Los casos de borde, cancelación, recuperación, contratos originales y límites de payload siguen en la suite ordinaria.

## Informes y fallos

Cada ejecución escribe en `artifacts/e2e/<proyecto>/`:

| Archivo | Evidencia |
|---|---|
| `summary.json` | Resultado, fase de fallo si procede, imagen/plataforma/revisión, gate y limpieza |
| `case-<transporte>-<protocolo>.json` | Herramientas, aserciones, rechazos de entrada, cobertura y última llamada |
| `pytest.xml` / `pytest.log` | Casos ejecutados y diagnósticos de pytest |
| `build.log` / `build.json` | Build cuando no se utiliza `--no-build` |
| `mealie-start.log` / `mcp-start.log` | Preparación de servicios |
| `services.log` / `cleanup.log` | Logs de servicios y retirada de recursos propios |

`artifacts/e2e-summary.json` apunta a la última ejecución. El comando solo devuelve0 si pasan pytest, los cuatro informes, el gate exacto de herramientas y la limpieza. El código de salida no se basa únicamente en el resumen de pytest: cuatro tests omitidos también producen un fallo de cobertura. Los artifacts están excluidos de Git; CI los conserva14 días en cada plataforma.

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

La ejecución y sus medidas se registran en [local-e2e-progress.md](local-e2e-progress.md). La evidencia histórica P24 corresponde al test anterior de31 llamadas/28 herramientas y se conserva como historial. El nuevo gate exige las78 herramientas por combinación. Los resultados locales no demuestran un despliegue remoto, un cliente público concreto ni un job de GitHub Actions completado.

Las pruebas reales motivaron [D10/D11](../migration/differences.md): las actualizaciones de compra obtienen primero el registro y envían un PUT completo, conservando identificadores/campos desconocidos; el borrado en lote repite la query `ids` para cada identificador. Ninguna escritura se reintenta. La [revisión independiente](local-e2e-review.md) registra sus hallazgos y correcciones.
