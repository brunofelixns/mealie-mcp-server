# Informe de aceptación de la migración

Estado: **informe en construcción; aceptación final pendiente**. Actualizado el2026-10-28.
P01..P20 verificadas:78/78herramientas,801tests Python y1058originales pasan. Ver evidence/P01.md..P20.md. La aceptación final sigue pendiente.

Referencias: [plan](../superpowers/plans/2026-10-27-python-migration.md), [estado](implementation-state.json), [inventario](compatibility-inventory.md), [diferencias](differences.md).

## Identificación de la entrega

| Campo | Valor |
|---|---|
| Commit upstream | d027e1b4a314d781a322f1f91e37840f01464d77 |
| Commit del port probado | Pendiente |
| Versión del paquete | 2.1.0 |
| Versiones resueltas Python/FastMCP/mcp/uv | 3.14.10 / 4.1.4 / 2.3.0 / 0.9.9 verificadas en Dev Container |
| Digest de imagen runtime amd64 | Pendiente |
| Digest de imagen runtime arm64 | Pendiente |
| Plataforma nativa o emulada | Pendiente por arquitectura |
| Versión/digest Mealie de integración | Pendiente, fijar sin latest |
| Build/run CI y artefactos | Pendientes |
| Fecha y entorno Dev Container | Pendientes |
| Registry y dominio público | Sin configurar, fuera de la validación local |

## Evidencia por tarea

Se añade una entrada al cerrar cada tarea, conservando el resultado original aunque una ejecución posterior lo corrija.

Formato de entrada:

- ID de tarea y escenario.
- Commit de implementación y archivos afectados.
- Comando exacto, ejecutado desde el Dev Container o contenedor auxiliar de bootstrap.
- Imagen, plataforma y versiones relevantes; indicar emulación.
- Código de salida, número de casos y resumen del resultado observado.
- Log/artefacto con ruta o enlace; redacción de secretos aplicada.
- Diferencias respecto a baseline, limitaciones y siguiente paso si falla.
- Revisión del diff y confirmación de que dependencias/casos críticos de esa tarea están satisfechos.

No rellenar campos como passed/verde o inventar números de tests al preparar la plantilla.

## A. Referencia y paridad

- [ ] Suite original ejecutada en runner fijado; éxito/fallos documentados.
- [ ] Catálogo78/78, firmas/defaults/annotations/_meta reales capturados.
- [ ] Prompt1/1 e instrucciones completas comprobados.
- [ ] Cada herramienta tiene caso positivo y de rechazo/error por MCP.
- [ ] Todos los21 módulos lib y escenarios de los42 archivos de tests originales trazados.
- [ ] C01..C16 cubiertos, incluidas omisión/null, cursores cruzados, fases y rollback.
- [ ] Diferencias admitidas con motivo y prueba; ningún cambio oculto para hacer pasar snapshots.

## B. Calidad y alcance real

- [ ] Ruff y formato pasan.
- [ ] mypy pasa.
- [ ] Suite Python ejecutada; número real de casos y fallos registrado.
- [ ] Líneas >=90% y ramas >=85% medidas separadamente en código propio.
- [ ] Tests críticos de corrupción/restauración, DNS fijado, identidad y cancelación pasan aunque el porcentaje ya sea suficiente.
- [ ] Generación documental --check detecta drift y pasa con la documentación final.
- [ ] Revisión completa de los cambios, no solo de archivos ejecutados por tests.

## C. Transporte y clientes

- [ ] stdio real por subprocess y docker run -i, sin TTY/banners en stdout.
- [ ] HTTP real en /mcp con Bearer propio y401 al token ausente/incorrecto.
- [ ] Token del cliente no se reenvía como API key Mealie.
- [ ] Catálogo y efectos equivalentes entre stdio y HTTP.
- [ ] MCP moderno2026-07-28 y2025-11-25 probados con cliente SDK oficial y FastMCP.
- [ ] Host/Origin, cancelación, EOF, shutdown y payloads grandes verificados.
- [ ] /healthz y /readyz no llaman a Mealie ni filtran datos.
- [ ] Suite de conformidad ejecutada o limitación concreta documentada; no presentarla como paridad de negocio.
- [ ] Clientes concretos, si se han probado, identificados por aplicación/versión. No presumir compatibilidad universal con OAuth o fileParams.

## D. Entorno, paquete e imagen

- [ ] Dev Container limpio abre y reinstala frozen sin cambios al lock.
- [ ] Checks ejecutados dentro del entorno acordado.
- [ ] Wheel instalado fuera del source tree con instrucciones empaquetadas.
- [ ] Runtime final probado sin source mounts ni dependencias dev/Node.
- [ ] Usuario no root, raíz de solo lectura, tmpfs y señales comprobados.
- [ ] Misma imagen funciona por stdio y HTTP; healthcheck solo para HTTP.
- [ ] Imagen amd64 y arm64 con smoke por plataforma; emulación declarada.
- [ ] SBOM/provenance y escaneo de dependencias/imagen registrados.
- [ ] No hay secretos en Git, build context, layers, fixtures o artefactos.
- [ ] Integración real de lectura/escritura en Mealie desechable completa; producción no modificada.

## E. Entrega

- [ ] README, API_COVERAGE, WORKFLOWS, ARCHITECTURE, CONTRIBUTING y ejemplos actualizados.
- [ ] Configuración Python de CI/release, clientes, actualización de dependencias y coverage consistente.
- [ ] Código TypeScript/scripts JS propios y runner de referencia retirados del producto y CI ordinario.
- [ ] Licencia/procedencia y baseline declarativo conservados.
- [ ] Estado24/24 verificado y limitaciones explícitas.
- [ ] Imagen local de producción disponible y guía de uso completa.
- [ ] Publicación/endpoint, si se realizan posteriormente, tienen evidencia propia.

## Dictamen

**Pendiente.** El inventario, el diseño y el plan son documentación preparada. No constituyen una migración implementada ni un contenedor generado.
