# Diferencias controladas respecto al original

Estado: migración completa y verificada localmente; cada evidencia de fase identifica las diferencias probadas.
Referencia: d027e1b4a314d781a322f1f91e37840f01464d77.

| ID | Diferencia prevista | Motivo / decisión | Tarea | Estado |
|---|---|---|---|---|
| D01 | FastMCP/Python y superficie nativa de protocolo | Herramientas y efectos preservados; capacidades, recursos vacíos y sobre de respuesta moderno explícitos en catalog-differences.json | P02..P24 | Catálogo/eras P20 y transportes reales P21/P22/P24 verificados |
| D02 | HTTP Streamable con token Bearer independiente | Uso remoto personal elegido por el usuario, además de stdio | P22 | Verificada: SDK oficial/FastMCP, Bearer y contenedor |
| D03 | Dev Container, paquete Python y runtime OCI Python | Entorno y entrega de producción solicitados | P01/P02/P23 | Verificada: Dev Container, wheel y ambos runtimes |
| D04 | Una versión coherente de paquete/CLI/MCP | El original declara paquete 2.1.0 y servidor 1.0.0; el usuario elige 0.1.0 para publicar el port Python el 2026-10-30 | P02/P20/P21/P23 y publicación local | Metadata actual 0.1.0; las evidencias históricas 2.1.0 se conservan |
| D05 | Documentación con78 herramientas y prompt con perPage | Corregir recuentos/argumento que difieren del registro; instrucciones generales preservadas íntegramente | P20/P24 | Prompt P20 y documentos/generador P24 verificados |
| D06 | Salud HTTP y mensajes/logs con redacción de secretos | No copiar cuerpos crudos de errores del proveedor ni excepciones de descarga que puedan contener URLs firmadas; conservar estado/isError | P05/P08/P18/P22 | Errores/redacción P08/P18 y salud HTTP P22/P24 verificados |
| D07 | Texto JSON null válido si un DELETE devuelve204 | Original observado: MCPError-32602 por text undefined; DELETE no se repite | P08..P20 | Verificada en delete_tag.edge204 |
| D08 | structuredContent/outputSchema por herramienta | Solo si conserva el contenido contractual y pasa comparación de clientes | P06/P20 | No se activa: se conserva la salida de texto original |
| D09 | Texto de validación de argumentos identifica campo/regla sin copiar entradas | Validación estricta equivalente con JSON Schema/Pydantic; no exponer entradas ni secretos por mensajes del SDK | P06 | Verificada: tests/contracts/test_strict_inputs.py |
| D10 | `update_shopping_list` y `update_shopping_list_item` leen el registro antes de enviar un PUT completo | Mealie3.29.0 exige identificadores que no son argumentos MCP y aplica valores predeterminados a campos omitidos; conservar identificadores, elementos y campos desconocidos | E2E local | Pruebas unitarias y contratos separados; verificación real registrada en docs/testing/local-e2e.md |
| D11 | `delete_shopping_list_items_bulk` repite el parámetro `ids` por identificador, sin CSV | Mealie3.29.0 valida cada valor de la query como UUID y rechaza el CSV con422; un lote vacío omite la query y es un no-op del proveedor | E2E local | Pruebas unitarias de serialización y contratos separados; verificación real registrada en docs/testing/local-e2e.md |
| D12 | Skills portables y extensión oficial `io.modelcontextprotocol/skills` | Distribuir procedimientos con el servidor y permitir instalación manual | Skills | Contratos, transportes e imagen instalada; detalle y límites al final del documento |

## Regla para añadir una diferencia

La versión del port Python es **0.1.0**, por decisión explícita del usuario el 2026-10-30. Se alinea `pyproject.toml`, lock, label OCI, ejemplos de despliegue y entrada de release. Las capturas de `tests/fixtures/compatibility`, incluidas las descripciones originales de diferencias, no se reescriben. Las pruebas verifican la identidad contra la versión del proyecto y la metadata instalada; al comparar el sobre moderno del prompt solo se sustituye el campo de versión contemplado por D04. Todos los demás campos, capacidades, catálogo y mensajes mantienen su comparación estricta con las capturas.

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
