# Mealie MCP en Python

Migración completa de las78 herramientas y el prompt weekly-meal-plan a FastMCP. Admite stdio local y Streamable HTTP con token Bearer personal independiente de la API key de Mealie. Desarrollo y verificación en Dev Container; imagen de producción para amd64 y arm64.

La implementación y verificación local están completas (24/24). [Avance](migration/progress.md), [estado JSON](migration/implementation-state.json) y [aceptación](migration/acceptance.md) distinguen lo ejecutado de las limitaciones y de la publicación pendiente.

| Necesidad | Documento |
|---|---|
| Preparar el entorno y ejecutar checks | [Desarrollo](development.md) |
| Variables y credenciales | [Configuración](configuration.md) |
| Conectar clientes stdio/HTTP | [Clientes](clients.md) |
| Proteger el endpoint remoto | [Despliegue HTTP](http-deployment.md) |
| Construir y ejecutar la imagen | [Contenedores](containers.md) |
| Descargar una imagen de GHCR y crear el servicio | [Despliegue Docker](../docker/README.md) |
| Módulos y ciclo de vida | [Arquitectura](architecture.md) |
| CI, release y mantenimiento | [Workflows](workflows.md) |
| Herramientas y esquemas | [Catálogo](tools.md) |
| Endpoints Mealie utilizados | [Cobertura API](api-coverage.md) |
| Contratos originales y trazabilidad | [Inventario](migration/compatibility-inventory.md) |
| Cambios explícitos frente al original | [Diferencias](migration/differences.md) |
| Resultados y límites de la entrega | [Aceptación](migration/acceptance.md) |
| Retirada de herramientas temporales y restos TS | [Limpieza final](migration/cleanup.md) |
| Escaneo y avisos del sistema base | [Seguridad de imagen](migration/evidence/P23-security.md) |

El [diseño aprobado](superpowers/specs/2026-10-27-python-migration-design.md) y el [plan de24 tareas](superpowers/plans/2026-10-27-python-migration.md) conservan las decisiones y criterios originales. El [ledger](migration/execution-log.md) registra su ejecución. Upstream está fijado en d027e1b4a314d781a322f1f91e37840f01464d77; se conserva su [licencia](migration/upstream-LICENSE.txt).
