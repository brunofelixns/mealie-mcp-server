# Avance de la migración

Fecha de preparación: 2026-10-27. Estado: **implementación en curso**.

Plan: [24 tareas detalladas](../superpowers/plans/2026-10-27-python-migration.md).
Fuente de estado: [implementation-state.json](implementation-state.json).
Diseño: [especificación](../superpowers/specs/2026-10-27-python-migration-design.md).
Cierre: [informe de aceptación](acceptance.md).
Diferencias: [registro](differences.md).

## Situación actual

- Documentados: inventario de78 herramientas, un prompt, diseño y plan.
- Implementación:9/24 tareas verificadas; P10 en curso;27 herramientas portadas y verificadas.
- Pruebas ejecutadas:1058originales y220Python pasan; sin Mealie de producción.
- Dev Container creado/abierto: verificado en P01.
- Imagen de producción construida: pendiente.
- Publicación y endpoint remoto: pendientes; se decidirá destino después de las pruebas locales.
- Método de ejecución: secuencial nativo, autorizado al comenzar.

## Orden de ejecución

La tabla es la vista inicial del JSON. Durante la ejecución se actualizan ambos en el mismo cambio documental; los checkboxes de pasos del plan expresan trabajo, no sustituyen evidencias.

| Tarea | Resultado | Dependencias | Estado inicial |
|---|---|---|---|
| [P01](../superpowers/plans/2026-10-27-python-migration.md#p01) | Arrancar el Dev Container sin depender de un lock inexistente | — | Verificada |
| [P02](../superpowers/plans/2026-10-27-python-migration.md#p02) | Fijar paquete, dependencias y checks Python | P01 | Verificada |
| [P03](../superpowers/plans/2026-10-27-python-migration.md#p03) | Capturar la referencia original y el corpus de compatibilidad | P02 | Verificada |
| [P04](../superpowers/plans/2026-10-27-python-migration.md#p04) | Configurar entorno, secretos y presencia de campos | P03 | Verificada |
| [P05](../superpowers/plans/2026-10-27-python-migration.md#p05) | Implementar el cliente Mealie y las utilidades HTTP | P04 | Verificada |
| [P06](../superpowers/plans/2026-10-27-python-migration.md#p06) | Crear la factory MCP y el adaptador de contratos | P05 | Verificada |
| [P07](../superpowers/plans/2026-10-27-python-migration.md#p07) | Portar candidatos y consultas agrupadas | P06 | Verificada |
| [P08](../superpowers/plans/2026-10-27-python-migration.md#p08) | Migrar categorías y etiquetas | P07 | Verificada |
| [P09](../superpowers/plans/2026-10-27-python-migration.md#p09) | Migrar alimentos y unidades | P08 | Verificada |
| [P10](../superpowers/plans/2026-10-27-python-migration.md#p10) | Migrar el catálogo de utensilios | P09 | En curso |
| [P11](../superpowers/plans/2026-10-27-python-migration.md#p11) | Migrar listas de compra e items | P10 | Pendiente |
| [P12](../superpowers/plans/2026-10-27-python-migration.md#p12) | Migrar el núcleo de recetas | P11 | Pendiente |
| [P13](../superpowers/plans/2026-10-27-python-migration.md#p13) | Migrar taxonomía y utensilios de recetas, incluido patch_recipe | P12 | Pendiente |
| [P14](../superpowers/plans/2026-10-27-python-migration.md#p14) | Migrar planes de comidas y operaciones por fases | P13 | Pendiente |
| [P15](../superpowers/plans/2026-10-27-python-migration.md#p15) | Migrar búsqueda por ingredientes, cursores y colas de auditoría | P14 | Pendiente |
| [P16](../superpowers/plans/2026-10-27-python-migration.md#p16) | Migrar escrituras de ingredientes y recuperación | P15 | Pendiente |
| [P17](../superpowers/plans/2026-10-27-python-migration.md#p17) | Migrar instrucciones con guardas de snapshot | P16 | Pendiente |
| [P18](../superpowers/plans/2026-10-27-python-migration.md#p18) | Migrar imágenes y el descargador con DNS fijado | P17 | Pendiente |
| [P19](../superpowers/plans/2026-10-27-python-migration.md#p19) | Migrar valoraciones, favoritos y fechas | P18 | Pendiente |
| [P20](../superpowers/plans/2026-10-27-python-migration.md#p20) | Cerrar catálogo, prompt e instrucciones | P19 | Pendiente |
| [P21](../superpowers/plans/2026-10-27-python-migration.md#p21) | Completar CLI y stdio real | P20 | Pendiente |
| [P22](../superpowers/plans/2026-10-27-python-migration.md#p22) | Completar HTTP con Bearer personal y salud | P21 | Pendiente |
| [P23](../superpowers/plans/2026-10-27-python-migration.md#p23) | Construir y verificar la imagen de producción | P22 | Pendiente |
| [P24](../superpowers/plans/2026-10-27-python-migration.md#p24) | Cerrar integración, documentación, retirada TS y aceptación | P23 | Pendiente |

## Regla de avance

1. Solo una tarea activa en la ejecución secuencial. Empezar en P01; antes de la siguiente, comprobar dependencias y revisión de fase.
2. Estados del JSON: not_started, in_progress, blocked o verified. Solo verified cuenta como cerrada y exige evidencia de salida y referencia al código probado.
3. Registrar comando exacto, entorno/contenedor, versión/commit, resultado real y ubicación del log o artefacto. Un fichero escrito o un test añadido no es prueba de que funcione.
4. Marcar blocked solo para una condición concreta: explicar qué falta, qué se pudo completar y cómo reanudar. Nunca convertir bloqueado o parcial en verificado.
5. Portar los escenarios originales y añadir casos críticos ausentes; documentar una diferencia antes de cambiar el baseline.
6. Tras verificar el código, hacer commit; registrar su SHA en la evidencia. Si el registro se añade después, puede ir en un commit documental separado. No incluir credenciales ni datos de producción en logs/fixtures.
7. Revisar el cierre de F1, F2, F3, F4 y F5 con la tabla de fases del plan. No repetir automáticamente toda la suite después de cambios solo documentales.
8. Para retomar, leer este archivo, el JSON, el diseño y la primera tarea no cerrada con dependencias satisfechas. Conservar los resultados anteriores cuando el código relevante no haya cambiado.

## Qué significa migración completa

Las78 herramientas tienen paridad y pruebas; prompt/instrucciones preservados; ambos transportes y protocolos probados; Dev Container reproducible; wheel e imagen final ejecutables; integración desechable y documentación actualizada; retirada de runtime/scripts propios Node/TS; informe de aceptación con resultados. Un endpoint publicado no se considera probado por haber pasado tests locales.
