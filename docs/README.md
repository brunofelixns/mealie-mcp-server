# Migración de Mealie MCP a Python

Estado a2026-10-28: **implementación en curso (P01..P16 verificadas; P17 activa)**.

## Ruta de lectura

1. [Plan de implementación](superpowers/plans/2026-10-27-python-migration.md):24 tareas ordenadas, dependencias, archivos, interfaces, pruebas y criterios de cierre.
2. [Seguimiento de avance](migration/progress.md) y [estado JSON](migration/implementation-state.json): punto de reanudación y propietario de cada herramienta, módulo y test original.
3. [Diseño de la migración](superpowers/specs/2026-10-27-python-migration-design.md): arquitectura, stdio/HTTP, Bearer, Dev Container e imagen de producción.
4. [Inventario de compatibilidad](migration/compatibility-inventory.md) e [inventario JSON](migration/compatibility-inventory.json):78 herramientas, prompt, esquemas fuente, endpoints y trazabilidad.
5. [Aceptación](migration/acceptance.md): plantilla donde registrar resultados reales y condiciones de entrega.
6. [Diferencias controladas](migration/differences.md): ampliaciones/correcciones explícitas y condicionadas.
7. [Licencia upstream](migration/upstream-LICENSE.txt).

## Decisiones confirmadas

FastMCP, migración completa a Python, stdio local y HTTP remoto, token Bearer personal independiente de la API key de Mealie, trabajo dentro del Dev Container y generación de una imagen de producción.

## Estado de la evidencia

Upstream fijado en d027e1b4a314d781a322f1f91e37840f01464d77. Se revisaron estáticamente los registros y42 archivos de pruebas originales. El diseño pasó una revisión independiente; el plan se revisó contra el diseño y el inventario.

Las comprobaciones auxiliares de estos documentos se ejecutan en el host y se identifican como documentales. P01..P16 aportan evidencia de ejecución:1058tests originales y568Python pasan;71/78 herramientas portadas y verificadas. Ver el seguimiento para los límites y trabajo pendiente.

## Cómo empezar después de revisar el plan

Para retomar, consultar la tarea activa del estado JSON y sus dependencias. Cerrar cada tarea con evidencia antes de avanzar. La implementación secuencial está autorizada; no se publican artefactos ni se despliega un endpoint público.

Los documentos futuros de desarrollo, configuración, clientes y operación se crearán junto a la tarea que los necesite, dentro de docs. No se crean runbooks que aparenten describir una aplicación ya operativa.
