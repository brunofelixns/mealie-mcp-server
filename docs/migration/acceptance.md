# Informe de aceptación de la migración

Estado a2026-10-28: **migración Python completa y verificada localmente;24/24 tareas cerradas**. Publicación y endpoint público no ejecutados. La imagen conserva avisos Debian materiales descritos abajo.

Referencias: [plan](../superpowers/plans/2026-10-27-python-migration.md), [estado](implementation-state.json), [inventario](compatibility-inventory.md), [diferencias](differences.md), [evidencia P24](evidence/P24.md) y [revisión independiente](evidence/final-review.md).

La [limpieza posterior](cleanup.md) retira las herramientas Node temporales y restos de estructura. Los resultados P24 siguientes describen la entrega antes de esa limpieza. Verificación posterior:929 tests pasan,1 deseleccionado, checker78/78 y cobertura95,982974% líneas/87,472284% ramas; detalle y artefactos en el registro de limpieza.

## Identificación de la entrega

| Campo | Valor |
|---|---|
| Upstream | d027e1b4a314d781a322f1f91e37840f01464d77 |
| Commit de código probado e incluido en imágenes | edc067df15930cdbacad8c1449221a11871cf45d; los commits posteriores cierran documentación/evidencia |
| Paquete/CLI/MCP | 2.1.0 |
| Python/FastMCP/mcp/uv | 3.14.10 / 4.1.4 / 2.3.0 / 0.9.9 |
| Runtime amd64 | mealie-mcp-server:local; manifest sha256:f48bc0d57dffefd8de6b5e1155e4efe529ba61258aa39366e4c355d7a7a78d68 |
| Runtime arm64 | mealie-mcp-server:local-arm64; manifest sha256:f7817876a52a218818c8c4de9ac6f86939de126ba106869b1a656e0353b1b917 |
| Plataforma | amd64 nativa; arm64 emulada en Docker Desktop x86_64, sin prueba en hardware ARM |
| Mealie real de integración | v3.29.0@sha256:78eb28b8776d0bad40c5e605c72b3f4f5976793e491558c7dcbdfc04c835d4bc |
| Entorno | Dev Container Linux, usuario vscode; host Windows usado como editor/launcher Docker |
| CI/registry/dominio | Configuración preparada y validada localmente; sin run GitHub, publicación ni despliegue público |

[Hashes OCI, config, SBOM/provenance y scan por plataforma](evidence/runtime-images.json). Los tags locales pueden moverse al reconstruir; los manifests anteriores identifican esta prueba. Los archivos OCI locales están en artifacts/P24-runtime-amd64.tar y artifacts/P24-runtime-arm64.tar.

## Resultados medidos

- **929 tests Python pasan,3 deseleccionados,365,64s** en la suite ordinaria. Los3 son las2 auditorías opcionales de referencia y1 integración live, ejecutada aparte. La referencia original pasó1058 tests en P03.
- **Cobertura:**3608/3759 líneas =95,982974%;789/902 ramas =87,472284%. El checker aplica umbrales independientes90/85 y verifica el JUnit real.
- **78/78 herramientas:**78 positivos y78 rechazos ejecutados;246 casos capturados de familias,21 módulos lib y42 archivos originales trazados.77 herramientas tienen positivo upstream capturado; set_recipe_image_from_file tiene positivo Python con downloader inyectado, expresamente identificado.
- Ruff/formato en221 archivos y mypy estricto en82 fuentes pasan. Generación documental --check, wheel/sdist y validación Compose pasan. Los enlaces locales del Markdown se resuelven en el check de entrega.
- **Imagen final:**5 pruebas amd64 pasan en55,03s;5 arm64 en137,70s. Incluyen stdio sin TTY, HTTP/Bearer y salud, catálogo/prompt, carga10MiB mediante archivo de secretos, red Docker, usuario/permisos/herramientas ausentes y shutdown.
- **Mealie real:** test directo1/1 en7,67s y runner Compose limpio1/1 en6,40s;31 llamadas sobre28 herramientas. Verifica persistencia de ingredientes/instrucciones/referencias, guardas de snapshot, imagen, rating/favorito, fechas, plan y compra. Proyecto/volumen exclusivos eliminados al terminar; producción no modificada.
- **Revisión de toda la rama con contexto nuevo:**0 Critical,0 Important y0 Minor accionables confirmados. No ejecutó otra suite ni modificó el checkout; sus límites y las resoluciones del implementador están registrados.

## A. Referencia y paridad

- [x] Suite original ejecutada en runner/commit fijados; resultado documentado.
- [x] Catálogo78/78, firmas/defaults/annotations/_meta y errores comparados con capturas.
- [x] Prompt1/1 e instrucciones completas comprobados; única corrección textual per_page→perPage del prompt declarada.
- [x] Cada herramienta tiene positivo y rechazo/error por MCP; efectos y ausencia de llamadas en inputs inválidos comprobados.
- [x]21 módulos lib y comportamientos de42 archivos originales trazados.
- [x] C01..C16 cubiertos: omisión/null/0/false/[], cursores, orden/concurrencia, fases y rollback.
- [x] Diferencias explícitas con motivo y evidencia, sin normalización que oculte regresiones.

## B. Calidad

- [x] Ruff, formato y mypy pasan.
- [x] Suite Python y umbrales separados de líneas/ramas pasan con reportes reales.
- [x] Corrupción/restauración, DNS fijado, identidad, fechas y cancelación tienen pruebas específicas.
- [x] Generación documental detecta drift y pasa en la entrega.
- [x] Revisión independiente de la rama completa y resoluciones documentadas.

## C. Transportes y clientes

- [x] stdio por subprocess e imagen sin TTY; stdout solo JSON-RPC.
- [x] /mcp HTTP real con Bearer independiente;401 para token ausente/incorrecto.
- [x] Credencial personal no se reenvía como API key Mealie; Host/Origin y límites comprobados.
- [x] Catálogo y efectos equivalentes en ambos transportes.
- [x] Eras2026-07-28 y2025-11-25 probadas mediante SDK oficial y FastMCP; no se afirma compatibilidad universal de aplicaciones.
- [x] EOF/señales, desconexión, cancelación y payloads grandes probados. Drenaje3s+cleanup35s+pool5s dentro de45s Docker.
- [x] /healthz y /readyz mínimos, sin llamadas Mealie ni datos privados.
- [x] Runner externo intentado y límite concreto documentado: **no hay certificación externa**. npm conformance0.1.16 falla initialize sin Bearer y carece de escenarios2026-07-28.

## D. Entorno y suministro

- [x] Dev Container inicial y reapertura frozen verificados; lock estable.
- [x] Python/tests/builds ejecutados dentro del entorno acordado.
- [x] Wheel instalado fuera del source tree y recursos empaquetados comprobados.
- [x] Runtime final sin source mounts, Node, uv, pip, compiladores ni herramientas de tests.
- [x] UID/GID10001, raíz de solo lectura, tmpfs, capacidades eliminadas y señales comprobados.
- [x] Misma imagen admite stdio y HTTP; healthcheck solo en perfil HTTP.
- [x] Ambas plataformas construidas y probadas, emulación declarada.
- [x] SBOM/provenance y correspondencia entre hashes OCI/imagen escaneada verificados.
- [x] Sin secretos detectados: scan de484 archivos rastreados/artefactos de texto y scan separado de layers de ambas imágenes. Esto describe el alcance de escaneo, no una garantía universal sobre historia Git o entorno externo.
- [x] Integración de lectura/escritura Mealie desechable completada y recursos propios limpiados.

## E. Entrega

- [x] README, API_COVERAGE, WORKFLOWS, ARCHITECTURE, CONTRIBUTING y docs actualizados.
- [x] CI/release Python, clientes, Renovate y coverage coherentes; ejecución remota pendiente.
- [x] Producto TypeScript/JS y workflows anteriores retirados. Tras la limpieza final se retira también el runner Node opcional; se conserva su baseline declarativo y el historial Git.
- [x] Licencia/procedencia y baseline declarativo conservados.
- [x] Estado24/24 y límites explícitos; release_gate local pasa sin publicar.
- [x] Imágenes locales disponibles y guía de uso completa.
- [x] Publicación y endpoint públicos identificados como pendientes de destino/autorización y evidencia propia.

## Límites de seguridad y operación

Cada arquitectura conserva **242 avisos Debian:2 CRITICAL y59 HIGH**, sin FixedVersion disponible en el canal analizado; **0 avisos Python y0 secretos**. El gate rechaza secretos y HIGH/CRITICAL corregibles, sin ocultar los demás mediante ignore/VEX. Trivy0.76.1 por digest y DB2026-10-28. Hay163 componentes CycloneDX por arquitectura. Consultar [análisis y fuentes Debian](evidence/P23-security.md) y [resultados finales](evidence/runtime-images.json). **La entrega no certifica una imagen libre de vulnerabilidades ni una exposición pública segura.**

No se han probado clientes de escritorio concretos, OAuth, hardware ARM nativo, una infraestructura TLS pública ni ejecuciones de GitHub Actions. El modo elegido es Bearer personal. Las garantías de cleanup son acotadas al proceso: SIGKILL/caída del host interrumpe la recuperación; la lectura seguida de PATCH no aporta atomicidad transaccional frente a otros escritores Mealie.

## Dictamen

La migración solicitada está implementada y reproducida localmente: producto Python completo, ambos transportes, Dev Container y contenedor de producción de ambas arquitecturas. Los límites anteriores acompañan la entrega. Publicar o desplegar requiere su propio destino y validación; no se ejecutó ninguna de esas acciones.
