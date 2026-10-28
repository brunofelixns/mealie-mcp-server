# Revisión independiente final

Fecha:2026-10-28. Rango inmutable revisado: d027e1b4a314d781a322f1f91e37840f01464d77..edc067df15930cdbacad8c1449221a11871cf45d. Revisor con contexto nuevo, revisión de solo lectura, sin delegación adicional ni cambios de archivos/índice/HEAD/contenedores. Se aplica la única revisión de rama prevista por el método secuencial.

**Resultado:** ningún hallazgo Critical, Important o Minor accionable confirmado. Apto para completar el cierre documental y las comprobaciones finales de entrega. El revisor contrastó código con upstream en flujos relevantes, Docker/CI/release, contratos y diff; no ejecutó suites adicionales. Los resultados de tests proceden de los informes del implementador.

| Foco del plan | Evaluación independiente |
|---|---|
| Bootstrap | development no depende del lock; evidencia separa apertura P01 y frozen P02 |
| Namespace/red | subruta preservada, segmentos codificados, redirects fuera de origen rechazados antes de reenviar credenciales |
| Cancelación tras escritura | cleanup acotado, sin replay; tests de desconexión TCP y EOF/SIGTERM stdio |
| Payloads grandes | límite SDK por instancia;10MiB, fragmentación y SSE grande en ambas eras |
| Identidad/tiempo | caché por cliente, TZ explícita, dos instancias y corpus UTC/Madrid/DST |

Fortalezas observadas: catálogo único78, registro explícito/aliases, comparación de efectos y respuestas upstream; separación de transporte, servicios y cliente; mutaciones verificadas con rollback; descargas DNS fijado y credenciales independientes; runtime Linux sin Node, endurecimiento y publicación manual condicionada.

## Alcances que el revisor dejó a juicio del implementador

1. Exposición pública concreta: no hay dominio/proxy/destino y quedan CVEs Debian. Resolución: entrega local, sin certificar exposición pública; requiere validación propia. Coste si se ignora: desplegar avisos conocidos sin evaluar el entorno.
2. Certificación externa MCP: runner sin Bearer/escenarios modernos. Resolución: no se afirma certificación; se conserva fallo401 y la evidencia SDK separada. Coste: compatibilidad con clientes concretos sin probar todavía.
3. Actions/publicación real: solo configuración inspeccionada. Resolución: no se atribuyen resultados remotos a checks locales. Coste: diferencias de runner/permisos/registry al ejecutar CI por primera vez.
4. Smoke/scan arm64 en curso y docs posteriores al SHA: resolución a cargo del implementador mediante resultados y hashes verificables; no se solicita otra revisión. Coste: la prueba ARM usa emulación, sin afirmar hardware nativo.
5. Recuperación durable tras SIGKILL/caída del host y atomicidad ante edición concurrente: límites explícitos del diseño y upstream. Resolución: no se añade persistencia ni se promete CAS transaccional sin soporte Mealie. Coste: una caída dura interrumpe la recuperación; ediciones concurrentes pueden competir entre lectura y PATCH.

No quedan minors diferidos ni fixes de revisión. Los cierres documentales y resultados posteriores se registran en [P24](P24.md), [aceptación](../acceptance.md) y [runtime-images.json](runtime-images.json).
