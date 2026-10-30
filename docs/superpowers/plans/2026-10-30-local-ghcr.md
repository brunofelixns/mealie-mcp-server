# Plan de publicación local GHCR

> Ejecución secuencial con superpowers:executing-plans; TDD y una revisión final con contexto nuevo. El usuario ya solicita preparar el script dentro de la propuesta Buildx local aprobada.

**Objetivo:** construir, validar y publicar amd64/arm64 desde el Dev Container sin Actions.
**Arquitectura:** orquestador Python estándar, helpers Docker/OCI y reutilización de checks existentes. Publicación opt-in sobre digests verificados, con informe por ejecución.
**Spec:** [diseño](../specs/2026-10-30-local-ghcr-design.md).

## Archivos e interfaces

- scripts/publish_local.py: CLI, preflight, checks, imágenes, gates, publicación y reportes.
- scripts/release_images.py: ejecutar comandos con logs, inspección OCI/digests, validar manifest multiarch.
- tests/unit/test_local_publish.py: parámetros/guardas, fallos antes de push, publicación parcial, imágenes exactas y attestations.
- tests/e2e/runner.py: destino opcional `--summary` para que cada arquitectura tenga su propio informe sin depender del alias global de última ejecución.
- docs/publishing-local.md: requisitos, GitHub CLI/PAT y login Docker, comandos y recuperación.
- .devcontainer/devcontainer.json: feature oficial GitHub CLI; requiere reconstrucción para instalarla en un contenedor existente.
- docs/README.md, docs/containers.md, docs/workflows.md, docker/README.md, README.md: enlaces e instrucciones que permitan usar la publicación local.

## Preflight de interfaces

| Productor → consumidor | Contrato | Resolución |
|---|---|---|
| Buildx → pruebas/escáner/push | ID inmutable y plataforma | Inspeccionar arquitectura/labels y exportar OCI; publicar ese ID |
| OCI → gate | runtime + SBOM + provenance | Validar descriptor y payloads, sin extraer archivos del tar |
| E2E → release | resumen exacto por plataforma | Añadir --summary; exigir estado correcto e ID de imagen esperado |
| Docker push → manifest | digests por arquitectura | Validar digest remoto y plataformas; componer con image@digest |

## Tareas

- [x] 1. RED/GREEN: pruebas de argumentos, OCI completo/incompleto, checks que bloquean publicación y subidas parciales. Implementar helpers y CLI sin dependencias nuevas.
- [x] 2. Verificación Docker local: dry-run real; construir ambas arquitecturas, probar runtime stdio/HTTP, attestations, E2E y escaneo. Distinguir cualquier bloqueo del proveedor/DB de un fallo del script. No ejecutar push GHCR.
- [x] 3. Documentación, checks apropiados, revisión única y correcciones importantes; preparar la entrega del código en la rama ya autorizada.

## Focos de revisión

1. Credenciales, build args y errores no deben exponer tokens.
2. Ningún --dry-run/default/fallo puede publicar; todos los gates preceden al primer push.
3. El manifest debe referenciar bytes probados, con ambas plataformas y attestations.
4. Una publicación parcial se informa y no mueve la etiqueta principal ni reintenta escrituras.
5. Cambios del checkout durante validación deben bloquear publish; registros parciales no equivalen a validación completa.

## Ledger

Base:0125d5bd6864ce01600f056288e98155d75f3cd0. Checkout limpio al empezar. Dev Container existente estaba detenido y se arrancó; Docker tiene containerd y Buildx anuncia amd64/arm64. La memoria histórica describe instrucciones GHCR, no evidencia de una imagen efectivamente publicada.

### Implementación y revisión

- RED inicial por ausencia de los módulos; GREEN de 27 pruebas nuevas y 18 comprobaciones existentes relacionadas.
- Revisión independiente única: dos hallazgos importantes (la inspección podía registrar variables de entorno; la validación remota no exigía conservar las attestations) y uno menor (stderr ausente en timeouts). Se añadieron seis regresiones, observadas fallando antes de corregirlos. Ahora pasan las 33 pruebas nuevas y las 18 relacionadas: 51 en total.
- Las inspecciones usan campos permitidos, el manifest exige los digests originales de attestations y su enlace al runtime, y los timeouts conservan ambos canales de diagnóstico. Se volvieron a leer los OCI reales de ambas arquitecturas con el helper corregido, sin ejecutar operaciones remotas.
- Ruff, formato, mypy (82 archivos) y documentación generada comprobados dentro del Dev Container.
- Autenticación: guía `gh auth login/refresh` con `write:packages` y canal directo a `docker login --password-stdin`; PAT classic dedicado alternativo. No se inicia una sesión, se imprime un token ni se prueba una subida real durante esta tarea.

### Validación Docker inicial

Ejecución `8b201d6d7a21`, sin `--publish`, sobre el checkout dirty. Se conserva su resultado original fallido, sin sustituirlo por un éxito posterior:

| Comprobación | Resultado observado |
|---|---|
| Suite ordinaria | 977 passed, 4 live deselected; contenedores excluidos para probarlos por arquitectura |
| Compatibilidad | 78/78 herramientas, 246 casos; líneas 95,99%, ramas 87,50% |
| Build amd64 y arm64 | Ambas imágenes construidas y exportadas con SBOM/provenance reales |
| Contenedores amd64 | 7/7 |
| E2E amd64 | 4/4 combinaciones, 78 herramientas y 78 rechazos por combinación; limpieza confirmada |
| Escaneo amd64 | Gate enforce correcto; 0 secretos y 0 HIGH/CRITICAL corregibles. Conserva 2 CRITICAL y 59 HIGH sin corrección disponible en ese escaneo |
| Contenedores arm64 | 6/7; fallo del plazo de salud del Compose portátil |
| Escrituras GHCR | Ninguna: `attemptedTags=[]`, `pushedTags=[]` |

IDs locales inmutables: amd64 `sha256:5cb9d5f5f97f7c18a0a0e7d55bba9395acb363279a497da224433944646a59ec`, arm64 `sha256:6ff51760800423d6ccbd2f19def3b08cace9f9368fc3c5509060bffd972444de`. Los archivos detallados permanecen en `artifacts/local-release/8b201d6d7a21/`; son evidencia local, no imágenes publicadas.

El diagnóstico ARM midió `/readyz` correcto a los 33,27 segundos bajo QEMU. La prueba aceleraba la sonda y agotaba los reintentos antes de ese arranque. Se ajustó solo su override: gracia de 60s, intervalo 2s y sonda de hasta 10s; el wait total sigue limitado a 60s. La repetición pasó el arranque y reveló un segundo límite, el timeout HTTP implícito de 5s. Se alineó el cliente y la sesión MCP a 40s, como en las pruebas existentes del runtime. No se alteraron las aserciones ni el Compose de producción.

Docker Desktop se detuvo entre ejecuciones; se arrancó y se retiró exclusivamente el contenedor de prueba interrumpido, identificado por su proyecto Compose. El contenedor de desarrollo se reutiliza; los servicios ajenos no se modifican.

### Verificación posterior a las correcciones

| Comprobación | Resultado observado |
|---|---|
| Regresión del Compose HTTP ARM | 1/1, 42,29s; los otros seis tests ARM ya pasaban en la ejecución previa |
| Compose portátil amd64 tras ajustar tiempos | 2/2, 19,46s |
| E2E ARM sobre el mismo ID inmutable | 4/4, 201,57s; 312 caminos de herramientas y 312 rechazos de entrada; limpieza confirmada |
| Descarga por archivo en E2E | Rechazo SSRF esperado por combinación; 77 llamadas positivas y una comprobación de seguridad, no 78 descargas/operaciones positivas |
| Escaneo ARM con `--enforce` | 163 componentes, 0 secretos y 0 HIGH/CRITICAL corregibles; conserva 243 avisos, incluidos 2 CRITICAL y 59 HIGH sin corrección disponible |
| Docs y configuración | Generador y checker correctos, 90 enlaces locales resueltos, JSON del Dev Container válido |
| CLI | `--dry-run --publish` real: sin construir ni publicar; paths de fallo/publicación probados con runner simulado |

La nueva feature `gh` requiere reconstruir el Dev Container. Se valida la configuración, sin afirmar que se haya instalado en el contenedor existente ni probado un login real.

No se repite la suite ordinaria completa de 977 casos tras los seis tests de regresión y los ajustes exclusivos de pruebas. Se ejecutan los 51 casos de publicación/evidencia/limpieza y las pruebas Docker afectadas; no hay cambios al código MCP, dependencias, Dockerfile de producción ni fixtures originales. Tampoco se presenta la ejecución inicial del orquestador, que permanece fallida, como una ejecución completa posterior correcta. Ambas arquitecturas sí tienen build, OCI, contenedores, E2E y escaneo comprobados localmente mediante las ejecuciones descritas. ARM usa QEMU, no hardware nativo.

Autenticación y publicación remota quedan sin ejecutar: no hay login, push GHCR, manifest remoto ni prueba de descarga pública nuevos. El proceso de publicación se verifica con simulación y pruebas de fallos; su validación real requiere la sesión Docker del usuario y ejecutar `--publish` sobre un checkout limpio.

Checks finales: Ruff y formato correctos (244 archivos), mypy correcto (82 archivos), generador de documentos correcto, gate de release con 24 tareas verificado y las 51 pruebas focalizadas correctas (3,32s). Se comprueba además que no quedan recursos del proyecto E2E ARM. Destino de entrega del código: rama `migration/python` de `origin`; las imágenes no forman parte de esa subida Git.
