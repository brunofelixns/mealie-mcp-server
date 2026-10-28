# Ledger E2E — plan: docs/superpowers/plans/2026-10-28-local-e2e-all-tools.md

Usuario autoriza78 herramientas por ambos transportes contra Mealie/MCP en Docker. Base de trabajo:2a54606a0f9f4f939f1ea3feeaa114ee6cf3b82b. Estado: implementación, revisión, cuatro recorridos E2E y regresión final verificados; integración en la rama autorizada migration/python.

## Preflight

| Productor → consumidor | Contrato | Resolución |
|---|---|---|
| Compose → controlador | Nombre/etiquetas de proyecto, red y volúmenes | IDs únicos y comprobación de pertenencia antes de operaciones destructivas |
| Bootstrap → runtimes/clientes | Archivos de credenciales y URLs internas | API key local + Bearer aleatorio distinto, sin secretos en artifacts |
| Catálogo → escenarios → gate |78 nombres exactos,4 recorridos | Rechazar omissions/duplicados/resultados inesperados |
| Servidor de assets → herramientas de imagen | PNG local real | URL pasa por Mealie; download_url privado recibe rechazo SSRF explícito |

## Decisiones

Ruling: mantener el Dev Container como controlador y conectar/desconectar solo su interfaz de red de pruebas — ya dispone del CLI Docker y evita otro contenedor con socket — coste: el comando debe ejecutarse dentro de un Dev Container accesible al daemon.

Ruling: comprobar el rechazo SSRF local de set_recipe_image_from_file — la producción bloquea direcciones privadas y no se introduce un bypass — coste: su descarga positiva desde URL pública sigue cubierta por pruebas controladas previas, no por el E2E local.

Ruling: permitir únicamente `assets` mediante `HTTP_ALLOW_LIST` de Mealie — su transporte seguro rechaza la red privada por defecto, confirmado en el código de la imagen fijada — coste: esta excepción pertenece solo al proveedor desechable y no al runtime MCP ni al despliegue de producción.

Ruling: corregir PUT completos y queries de borrado como D10/D11 — el Mealie real y su OpenAPI demuestran422 para las llamadas originales — coste: dos GET adicionales y una serialización de query distinta, explícitos en contratos separados sin cambiar capturas.

Ruling: borrar la entrada de plan con menor ID del lote — SQLite puede reutilizar el ID máximo borrado al anexar en la misma llamada — coste: el escenario evita confundir reutilización de identidad con borrado fallido y sigue verificando las tres fases.

## Ejecución

- El test anterior ejecutaba31 llamadas/28 herramientas con cliente en memoria; sustituido, conservando la evidencia histórica P24.
- Gate TDD: `artifacts/e2e-evidence-red.log` confirma ausencia inicial del módulo; `e2e-evidence-green.log` confirma10 tests pasando para informes completos/incompletos, duplicados, errores, eras/imagen y secretos.
- Stack inicial `mealie-mcp-e2e-badf8e8e5065`: bootstrap real correcto y gate rechazando la antigua prueba omitida; cleanupPassed=true. Ningún skip se presenta como cobertura.
- Recorridos de depuración: `6bedc6e63b1e` detecta una forma de respuesta mal asumida en el nuevo test; `68ceed363093` confirma400 del proveedor por su protección SSRF; `8053c51cc93f` revela que los contadores del plan están dentro de `summary`; `253059dd37d1` detecta reutilización de ID del plan y422 real en borrado CSV. Todos retiran sus recursos y registran cleanupPassed=true.
- D10 RED:2 pruebas fallan con422 sin identificadores; GREEN tras GET+merge+PUT. D11 RED:2 fallan y1 pasa para query repetida/vacía; GREEN tras pares de query por ID. Pruebas adicionales confirman que GET fallido/inválido no escribe y que PUT fallido no se repite. `artifacts/e2e-shopping-green.log`:54 pruebas unitarias/de contrato pasan en40,41s.

## E2E observado a2026-10-28

Comando: `uv run python -m tests.e2e.runner`, ejecutado dentro del Dev Container. Proyecto: `mealie-mcp-e2e-c4c069bd8464`. Resultado: **4 tests pasan en112,31s**, gate completo y cleanupPassed=true.

Tras la [revisión independiente](local-e2e-review.md), se refuerza la aserción de imagen con PNG inicial azul/fixture rojo y bytes WebP diferentes; la limpieza intenta todas sus fases aunque fallen diagnósticos. RED de limpieza:3 casos fallan antes del cambio; GREEN:13 tests de limpieza/evidencia pasan en1,80s. Una repetición intermedia (`2f87590fb93a`) detectó una aserción equivocada del nuevo test de fusión: MCP devuelve el alimento destino, aunque el endpoint Mealie devuelva SuccessResponse. Se corrige únicamente la aserción MCP, manteniendo las comprobaciones independientes de persistencia.

**Repetición final del código de pruebas:** `uv run python -m tests.e2e.runner --no-build`, proyecto `mealie-mcp-e2e-b74df741fa7c`: **4/4 pasan en70,23s**, mismo ID runtime, gate completo, cleanupPassed=true. Evidencia final en `artifacts/e2e/mealie-mcp-e2e-b74df741fa7c/`; la tabla siguiente mantiene los mismos totales. Esta repetición incluye ambas correcciones de revisión.

| Campo | Valor observado |
|---|---|
| Mealie | v3.29.0, digest fijado en compose.integration.yaml |
| Runtime | sha256:bb8daf0ca81e08654a5453041b8fe592333863d632e1b923be4de961f513945a |
| Arquitectura | amd64, Docker Desktop Linux; esta ampliación no se ha ejecutado localmente en ARM |
| Revisión de imagen | 2a54606a0f9f4f939f1ea3feeaa114ee6cf3b82b-dirty: fuente con D10/D11 aún sin commit al construir |
| Transportes/protocolo | stdio y HTTP ×2026-07-28/2025-11-25, misma imagen en los cuatro |
| Cobertura por recorrido |78 nombres exactos:77 positivos +1 rechazo SSRF esperado;78 rechazos de argumentos |
| Totales |312 recorridos de herramienta:308 positivos +4 rechazos SSRF;312 rechazos de argumentos adicionales |
| Llamadas válidas/de seguridad |83 por recorrido,332 en total; algunas herramientas se repiten para preparar/limpiar |
| Invocaciones tools/call totales |644:332 llamadas de escenario +312 rechazos de argumentos |
| Autenticación HTTP |401 sin token, con token incorrecto y con API key Mealie; Bearer MCP correcto permite completar el recorrido |
| Datos | Lecturas independientes verifican persistencia; todos los IDs creados ausentes tras limpieza del escenario |
| Aislamiento/limpieza | Red interna sin puertos; contenedores/volúmenes/red del proyecto retirados; Dev Container desconectado |
| Evidencia local | artifacts/e2e/mealie-mcp-e2e-c4c069bd8464/{summary.json,case-*.json,pytest.xml,pytest.log,services.log,cleanup.log} |

El fichero de imagen por URL se importa y se recupera como WebP real. El de descarga por archivo conserva expresamente su resultado `security_rejection`, no un éxito de descarga. Las capturas originales no se modificaron. CI queda configurado para ejecutar estos mismos cuatro recorridos en sus dos plataformas; un resultado local no acredita un run remoto.

## Cierre de regresión

La primera suite ordinaria, ejecutada mientras se construían/probaban contenedores, terminó con950 tests correctos y1 timeout durante initialize de una prueba stdio (límite20s); no se cambió ese límite ni el producto. La prueba aislada pasó1/1 en12,13s. La repetición completa sobre los archivos finales, sin builds/E2E simultáneos, termina con **957 tests correctos y4 deseleccionados en676,26s**. Los cuatro excluidos son los recorridos live ejecutados por separado y verificados4/4. Evidencia: `artifacts/e2e-regression-final.log`, `artifacts/pytest.xml`.

Ruff y formato (238 archivos), mypy estricto (82 fuentes), generación documental y build wheel/sdist pasan. El checker confirma78 positivos/78 negativos en el JUnit ordinario,246 casos capturados,21 bibliotecas y42 archivos upstream. Cobertura independiente: **3613/3764 líneas =95,988310%**, **791/904 ramas =87,5%**, por encima de90/85. Los fixtures originales no cambian. Evidencia: `artifacts/e2e-final-checks.log`, `artifacts/coverage.json`, `artifacts/coverage.xml`, `artifacts/e2e-package-build.log`.

Los artifacts E2E históricos se examinaron sin imprimir coincidencias:79 archivos,0 valores JWT encontrados en ese punto de la ejecución. También se verifican los11 archivos del recorrido final sin valores JWT. La ausencia de credenciales en informes se comprueba además en el guard de escritura con valores reales conocidos durante cada run. La matriz de78 filas coincide con las aserciones de los cuatro informes finales y se resolvieron164 enlaces locales Markdown.

Ruling de integración: conservar y subir a `origin/migration/python`, según autorización previa del usuario — ya existe destino y decisión de integración — coste: ningún merge, PR ni publicación de imagen añadidos a esta tarea. El checkout se conserva; los servicios E2E, sus volúmenes y redes ya no existen.
