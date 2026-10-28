# Diferencias controladas respecto al original

Estado: ejecución en curso; cada evidencia de fase identifica las diferencias verificadas.
Referencia: d027e1b4a314d781a322f1f91e37840f01464d77.

| ID | Diferencia prevista | Motivo / decisión | Tarea | Estado |
|---|---|---|---|---|
| D01 | FastMCP/Python y superficie nativa de protocolo | Herramientas y efectos preservados; capacidades, recursos vacíos y sobre de respuesta moderno explícitos en catalog-differences.json | P02..P24 | Catálogo/eras verificados en P20; transportes finales pendientes |
| D02 | HTTP Streamable con token Bearer independiente | Uso remoto personal elegido por el usuario, además de stdio | P22 | Planificada |
| D03 | Dev Container, paquete Python y runtime OCI Python | Entorno y entrega de producción solicitados | P01/P02/P23 | Planificada |
| D04 | Una versión coherente de paquete/CLI/MCP | El original declara paquete2.1.0 y servidor1.0.0 | P02/P20/P21/P23 | Paquete y MCP 2.1.0 verificados; CLI/imagen pendientes |
| D05 | Documentación con78 herramientas y prompt con perPage | Corregir recuentos/argumento que difieren del registro; instrucciones generales preservadas íntegramente | P20/P24 | Prompt corregido y verificado en P20; documentos finales pendientes |
| D06 | Salud HTTP y mensajes/logs con redacción de secretos | No copiar cuerpos crudos de errores del proveedor ni excepciones de descarga que puedan contener URLs firmadas; conservar estado/isError | P05/P08/P18/P22 | Errores Mealie verificados desde P08 y transporte de descarga en P18; salud pendiente |
| D07 | Texto JSON null válido si un DELETE devuelve204 | Original observado: MCPError-32602 por text undefined; DELETE no se repite | P08..P20 | Verificada en delete_tag.edge204 |
| D08 | structuredContent/outputSchema por herramienta | Solo si conserva el contenido contractual y pasa comparación de clientes | P06/P20 | No se activa: se conserva la salida de texto original |
| D09 | Texto de validación de argumentos identifica campo/regla sin copiar entradas | Validación estricta equivalente con JSON Schema/Pydantic; no exponer entradas ni secretos por mensajes del SDK | P06 | Verificada: tests/contracts/test_strict_inputs.py |

## Regla para añadir una diferencia

Registrar herramienta/entrada, salida o efecto original observado, cambio propuesto, motivo, compatibilidad afectada y prueba que lo demuestra. Diferenciar corrección de defecto, cambio de transporte/metadata y cambio de negocio. No normalizar ni borrar una diferencia en el comparador para ocultarla.

No se aceptan como cambios implícitos: renombrar argumentos a snake_case, convertir null en omitido, imponer max25 al lote de taxonomía, ordenar patch_mealplan según input global, eliminar campos desconocidos de Mealie, quitar verificación/rollback, desactivar DNS fijado o delegar en un LLM del servidor.

Los casos con diferencias guardan expected_result del original y expected_python_result separado, con documented_difference obligatorio. El comparador solo admite D06/D07 expresos; no borra estados, errores ni llamadas para hacer pasar pruebas.
