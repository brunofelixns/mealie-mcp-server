# Diferencias controladas respecto al original

Estado: ejecución en curso; cada evidencia de fase identifica las diferencias verificadas.
Referencia: d027e1b4a314d781a322f1f91e37840f01464d77.

| ID | Diferencia prevista | Motivo / decisión | Tarea | Estado |
|---|---|---|---|---|
| D01 | FastMCP/Python en lugar de SDK/TypeScript original | Migración completa solicitada, preservando superficie y efectos | P02..P24 | Planificada |
| D02 | HTTP Streamable con token Bearer independiente | Uso remoto personal elegido por el usuario, además de stdio | P22 | Planificada |
| D03 | Dev Container, paquete Python y runtime OCI Python | Entorno y entrega de producción solicitados | P01/P02/P23 | Planificada |
| D04 | Una versión coherente de paquete/CLI/MCP | El original declara paquete2.1.0 y servidor1.0.0 | P02/P20 | Propuesta documentada |
| D05 | Documentación e instrucciones con78 herramientas y perPage | Corregir recuentos/argumento que difieren del registro | P20/P24 | Propuesta documentada |
| D06 | Salud HTTP y mensajes/logs con redacción de secretos | Operación del nuevo transporte sin exponer credenciales | P05/P22 | Propuesta documentada |
| D07 | Texto de éxito válido si un DELETE devuelve204 | Posible defecto al serializar undefined en original; requiere caracterización | P03/P06/P08..P20 | Condicional, no confirmado |
| D08 | structuredContent/outputSchema por herramienta | Solo si conserva el contenido contractual y pasa comparación de clientes | P06/P20 | Opcional y condicionado |
| D09 | Texto de validación de argumentos identifica campo/regla sin copiar entradas | Validación estricta equivalente con JSON Schema/Pydantic; no exponer entradas ni secretos por mensajes del SDK | P06 | Verificada: tests/contracts/test_strict_inputs.py |

## Regla para añadir una diferencia

Registrar herramienta/entrada, salida o efecto original observado, cambio propuesto, motivo, compatibilidad afectada y prueba que lo demuestra. Diferenciar corrección de defecto, cambio de transporte/metadata y cambio de negocio. No normalizar ni borrar una diferencia en el comparador para ocultarla.

No se aceptan como cambios implícitos: renombrar argumentos a snake_case, convertir null en omitido, imponer max25 al lote de taxonomía, ordenar patch_mealplan según input global, eliminar campos desconocidos de Mealie, quitar verificación/rollback, desactivar DNS fijado o delegar en un LLM del servidor.
