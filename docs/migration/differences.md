# Diferencias controladas respecto al original

Estado: migración completa y verificada localmente; cada evidencia de fase identifica las diferencias probadas.
Referencia: d027e1b4a314d781a322f1f91e37840f01464d77.

| ID | Diferencia prevista | Motivo / decisión | Tarea | Estado |
|---|---|---|---|---|
| D01 | FastMCP/Python y superficie nativa de protocolo | Herramientas y efectos preservados; capacidades, recursos vacíos y sobre de respuesta moderno explícitos en catalog-differences.json | P02..P24 | Catálogo/eras P20 y transportes reales P21/P22/P24 verificados |
| D02 | HTTP Streamable con token Bearer independiente | Uso remoto personal elegido por el usuario, además de stdio | P22 | Verificada: SDK oficial/FastMCP, Bearer y contenedor |
| D03 | Dev Container, paquete Python y runtime OCI Python | Entorno y entrega de producción solicitados | P01/P02/P23 | Verificada: Dev Container, wheel y ambos runtimes |
| D04 | Una versión coherente de paquete/CLI/MCP | El original declara paquete 2.1.0 y servidor 1.0.0; el usuario elige 0.1.0 para publicar el port Python el 2026-10-30 | P02/P20/P21/P23 y publicación local | Versión actual gestionada por Release Please; las evidencias históricas 2.1.0 se conservan |
| D05 | Documentación con78 herramientas y prompt con perPage | Corregir recuentos/argumento que difieren del registro; instrucciones generales preservadas íntegramente | P20/P24 | Prompt P20 y documentos/generador P24 verificados |
| D06 | Salud HTTP y mensajes/logs con redacción de secretos | No copiar cuerpos crudos de errores del proveedor ni excepciones de descarga que puedan contener URLs firmadas; conservar estado/isError | P05/P08/P18/P22 | Errores/redacción P08/P18 y salud HTTP P22/P24 verificados |
| D07 | Texto JSON null válido si un DELETE devuelve204 | Original observado: MCPError-32602 por text undefined; DELETE no se repite | P08..P20 | Verificada en delete_tag.edge204 |
| D08 | structuredContent/outputSchema por herramienta | Solo si conserva el contenido contractual y pasa comparación de clientes | P06/P20 | No se activa: se conserva la salida de texto original |
| D09 | Texto de validación de argumentos identifica campo/regla sin copiar entradas | Validación estricta equivalente con JSON Schema/Pydantic; no exponer entradas ni secretos por mensajes del SDK | P06 | Verificada: tests/contracts/test_strict_inputs.py |
| D10 | `update_shopping_list` y `update_shopping_list_item` leen el registro antes de enviar un PUT completo | Mealie3.29.0 exige identificadores que no son argumentos MCP y aplica valores predeterminados a campos omitidos; conservar identificadores, elementos y campos desconocidos | E2E local | Pruebas unitarias y contratos separados; verificación real registrada en docs/testing/local-e2e.md |
| D11 | `delete_shopping_list_items_bulk` repite el parámetro `ids` por identificador, sin CSV | Mealie3.29.0 valida cada valor de la query como UUID y rechaza el CSV con422; un lote vacío omite la query y es un no-op del proveedor | E2E local | Pruebas unitarias de serialización y contratos separados; verificación real registrada en docs/testing/local-e2e.md |
| D12 | Skills portables y extensión oficial `io.modelcontextprotocol/skills` | Distribuir procedimientos con el servidor y permitir instalación manual | Skills | Contratos, transportes e imagen instalada; detalle y límites al final del documento |
| D13 | 24 herramientas adicionales de recetas y actualización explícita de instrucciones | Petición del usuario: notas, metadatos, comentarios, archivos, importación/exportación, compartir e historial | Recetas 2026-11-03 | Definiciones originales preservadas como prefijo; contratos Python nuevos, límites y guía en recipes.md |
| D14 | Mealie 3.30.0, 60 operaciones MCP nuevas y preservación de datos del proveedor | Petición del usuario tras auditar los pendientes de recetas | Recetas 3.30 | Se conservan las 102 definiciones anteriores; diferencias de persistencia explícitas y pruebas descritas al final |
| D15 | Identidad canónica en lotes, límites JSON Schema y gates de API/JUnit más estrictos | Cuatro mejoras aceptadas tras la revisión previa a PR | Revisión 2026-11-03 | Regresiones y alcance detallados al final; no se alteran las capturas originales |

## Regla para añadir una diferencia

La versión inicial del port Python fue **0.1.0**, por decisión explícita del usuario el 2026-10-30. Release Please mantiene la versión actual de `pyproject.toml`, lock, label OCI, ejemplos de despliegue y entrada de release. Las capturas de `tests/fixtures/compatibility`, incluidas las descripciones originales de diferencias, no se reescriben. Las pruebas verifican la identidad contra la versión del proyecto y la metadata instalada; al comparar el sobre moderno del prompt solo se sustituye el campo de versión contemplado por D04. Todos los demás campos, capacidades, catálogo y mensajes mantienen su comparación estricta con las capturas.

Registrar herramienta/entrada, salida o efecto original observado, cambio propuesto, motivo, compatibilidad afectada y prueba que lo demuestra. Diferenciar corrección de defecto, cambio de transporte/metadata y cambio de negocio. No normalizar ni borrar una diferencia en el comparador para ocultarla.

No se aceptan como cambios implícitos: renombrar argumentos a snake_case, convertir null en omitido, imponer max25 al lote de taxonomía, ordenar patch_mealplan según input global, eliminar campos desconocidos de Mealie, quitar verificación/rollback, desactivar DNS fijado o delegar en un LLM del servidor.

Los casos con diferencias guardan expected_result del original y expected_python_result separado, con documented_difference obligatorio. El comparador solo admite D06/D07 para salidas y expected_python_requests para D10 (dos actualizaciones de compra) o D11 (borrado de elementos en lote); no borra estados, errores ni llamadas para hacer pasar pruebas.

## D10: actualización de compra con PUT completo

El original envía únicamente los campos solicitados en el PUT. El OpenAPI de la instancia real Mealie3.29.0 exige `groupId`, `userId` e `id` para una lista y `shoppingListId` para un elemento; el PUT parcial original produce422. Python hace un GET del mismo registro, conserva sus campos y superpone solo los argumentos de actualización antes de un único PUT. Mantiene omisión, cadena vacía,0 y false, los argumentos públicos y la respuesta del proveedor. Si el GET falla o devuelve una forma inválida, no escribe; nunca reintenta una escritura fallida. Las capturas originales permanecen intactas y los contratos prueban por separado las llamadas Python. Como todo read-modify-write sin una precondición ofrecida por el proveedor, existe una ventana de concurrencia entre GET y PUT.

## D11: identificadores repetidos en el borrado de compra

El original concatena `itemIds` con comas en una única query `ids`. La API real espera un array de UUID, serializado como `?ids=uuid1&ids=uuid2`, y devuelve422 para el CSV. Python conserva el orden y el valor de cada identificador con pares de query repetidos; mantiene el único DELETE y su respuesta sin reintentos. Para `itemIds=[]` no envía `ids`: el servicio Mealie3.29.0 no borra elementos cuando la lista es vacía/None. Se conservan los fixtures originales, incluidas las formas CSV y vacía, con expectativas Python explícitas y separadas. El caso de un solo identificador y su diferencia D07 para204 no cambian.

## D12: skills distribuidos por MCP y como archivos portables

Petición explícita del usuario del 2026-11-01. Se añade la extensión oficial
`io.modelcontextprotocol/skills` a las capacidades modernas, con `skills/list`,
`skills/get` y lectura de `skill://mealie/SKILL.md` y referencias mediante recursos.
La operación opcional de directorios no se anuncia. `resources/list`, antes vacío,
incluye ahora los archivos del skill y el recurso auxiliar `_manifest` de FastMCP.
En la era legacy se añaden únicamente esos recursos; las operaciones de extensión
se reservan al protocolo moderno. Las lecturas no producen llamadas a Mealie.

Se usa la implementación nativa experimental de FastMCP 4.1.4. La transformación
que conserva el orden de herramientas se aplica al proveedor local en lugar de
todo el servidor, porque la extensión rechaza transformaciones globales; los
contratos siguen comparando las78 herramientas y su orden con el baseline.
El prompt semanal y las instrucciones originales se conservan byte por byte.

`skills/mealie/` es la fuente única, instalable manualmente y empaquetada en
wheel/sdist/runtime. La activación y las decisiones del usuario pertenecen al
cliente. Los fixtures originales no se modifican: el test de capacidades aplica
explícitamente esta adición sobre la expectativa histórica y verifica el conjunto
exacto de recursos. `test_skills.py` en contratos, integración y contenedores
comprueba descubrimiento, lookup directo, hashes, bytes, errores, autenticación
y uso sin checkout montado. Ver [guía de uso](../skills.md).

## D13: operaciones adicionales de recetas

Petición explícita del usuario del 2026-11-03. Se añaden 24 herramientas al final
del catálogo sin cambiar nombres, esquemas, descripciones ni orden de las 78
originales. Las capturas de `tests/fixtures/compatibility` permanecen intactas.
Los contratos comparan exactamente ese prefijo y comprueban aparte las nuevas
operaciones. El inventario y los propietarios incorporan evidencia Python MCP,
incluida ejecución JUnit positiva y rechazo de argumentos por herramienta.

Las instrucciones generales cambian únicamente los párrafos de importación,
metadatos y URL fuente, y añaden orientación sobre las operaciones nuevas. La
expectativa adicional `tests/fixtures/recipe-extensions/instruction-changes.json`
declara esas sustituciones sobre el texto histórico sin modificarlo. El prompt
semanal y el resto de instrucciones mantienen su contenido.

Notas y metadatos comprueban snapshot y respuesta, conservando campos omitidos,
referencias y orden, sin reintentos automáticos. Los snapshots no son CAS del
proveedor. Importación/archivos, comentarios, compartir e historial utilizan
endpoints verificados en Mealie 3.29.0; sus límites y efectos se explican en la
[guía de recetas](../recipes.md). Los contadores documentales y de transporte
dependen del catálogo; el checker exige que el baseline siga siendo exactamente
el mismo y no permite sustituirlo por las nuevas pruebas.

## D14: cobertura de recetas y Mealie 3.30.0

Se fija la integración real a Mealie 3.30.0 por digest. El catálogo añade 60
herramientas sin modificar las 102 definiciones anteriores ni las capturas
históricas de 78. La [guía de adaptación](../mealie-3.30.md) documenta búsqueda,
sustituciones, medios, temporizadores, parser, trabajos/importación IA, recetarios,
acciones y planificación avanzada. Se añade orientación de agentes con una
expectativa independiente en `tests/fixtures/mealie330/instructions-addendum.md`.

La API ya contenía sustituciones que el contrato antiguo no permitía representar.
Las escrituras de alimentos/ingredientes conservan ahora esas relaciones y los
campos de proveedor no representados, mientras los campos conocidos mantienen
su semántica anterior de reemplazo y delta. Cuatro escenarios históricos de
ingredientes esperaban el descarte de `providerExtra`; un overlay D14 explícito,
acotado y solo aditivo adapta sus solicitudes Python esperadas en memoria. Sus
IDs y reglas están en `tests/fixtures/mealie330/ingredient-preservation.json`;
`tests/support/mealie330_compatibility.py` no ignora campos ni modifica capturas.
Las pruebas de regresión comparan todos los demás campos y efectos, incluida la
restauración y cancelación. Conservar estos datos es un cambio deliberado de
persistencia, no una relajación general de compatibilidad.

La instancia desechable no configura proveedor IA: los dos imports IA tienen
positivos HTTP/SSE controlados y rechazos de configuración comprobados en Mealie
real, contados por separado. No se presenta ese rechazo como una importación IA
positiva. No se modifican permisos o datos de una instancia de producción.
La [evidencia de 3.30](../testing/mealie-3.30-evidence.md) conserva versiones,
resultados, revisión independiente y límites de la validación local.

## D15: correcciones de revisión antes de PR

`update_recipe_metadata_batch` resuelve primero cada destino por GET al ID
canónico. Un slug y un UUID de la misma receta rechazan el lote antes de cualquier
PATCH. Se añade una lectura acotada por destino y se mantiene otra lectura fresca
por ID para el snapshot; no se convierten estas lecturas en un CAS del proveedor.
Los fallos de resolución se devuelven ordenados como `failed`, sin escritura;
otros destinos distintos pueden continuar. Los resultados inciertos posteriores
a una mutación conservan su semántica y ninguna escritura se reintenta.

Se corrigen once esquemas de las 60 herramientas añadidas en D14: los límites
publicados como extensiones `ge`/`le` pasan a `minimum`/`maximum`. El runtime ya
aplicaba esos límites; se conserva la distinción de booleanos y números, y la
aceptación de floats integrales JSON. Se mantienen sin cambios las 102
definiciones anteriores y todas las capturas originales. Las pruebas nuevas
comparan modelo, esquema publicado y rechazo MCP sin HTTP.

La auditoría del OpenAPI se ejecuta antes del bootstrap E2E y, por tanto, en la
CI que invoca ese controlador. El contrato separado de 3.30 conserva procedencia
y un subconjunto estructural revisado de peticiones/respuestas. No se actualiza
desde el proveedor durante las pruebas ni sustituye el baseline histórico. Se
aceptan cambios estructurales compatibles y se rechazan los incompatibles o las
formas fuera del comparador; defaults y validadores de negocio siguen requiriendo
pruebas de comportamiento.

El checker de compatibilidad rechaza JUnit con cualquier fallo/error, contadores
de fallo o casos duplicados ambiguos. La evidencia se vincula al módulo y función
de contrato, para impedir que otro test con igual nombre aporte un falso positivo.
Se conserva el requisito de positivos y rechazos ejecutados por herramienta.
