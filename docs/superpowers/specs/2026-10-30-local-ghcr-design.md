# Publicación local GHCR desde el Dev Container

El usuario solicita un script que construya y publique amd64 y arm64, sin GitHub Actions, documentado en docs. El destino existente es `ghcr.io/brunofelixns/mealie-mcp-server`; la versión debe coincidir con pyproject.toml. Esta tarea prepara y prueba el script; no solicita ejecutar una publicación ahora.

Se elige orquestación Python estándar, coherente con scripts/release_gate.py y scripts/scan_runtime.py, frente a duplicar el proceso en Bash o añadir un runner Actions propio. Reutiliza las validaciones del repositorio y Buildx del daemon local. No añade dependencias ni modifica herramientas MCP.

La ejecución normal valida y construye ambas imágenes localmente. `--dry-run` muestra los comandos sin ejecutarlos; `--publish` habilita las escrituras GHCR después de todas las comprobaciones. Docker gestiona el login externo al script: no recibe ni guarda PATs. Se exige Linux/Dev Container, Docker con almacén containerd, Buildx con ambas plataformas y un checkout limpio para publicar. Un checkout sucio solo permite pruebas locales, identificado como dirty.

Flujo: uv frozen, gate de versión/migración, checks estáticos y pytest con cobertura/compatibilidad; build runtime por plataforma con SBOM y provenance; exportación OCI y validación de ambas attestations; pruebas de contenedor y E2E por imagen; escaneo enforce de ambas. Registrar imagen, arquitectura, revisión, digests, logs y fallos en artifacts/local-release/<id>. Solo después se etiquetan/suben las imágenes ya comprobadas. La etiqueta principal se compone con digests y se verifica remotamente; no se reconstruye durante la publicación ni se mueve latest.

Si falla una comprobación no hay push. Si falla una subida parcial no se avanza la etiqueta principal, se informa qué digests llegaron al registry y no se reintenta automáticamente. Los tags de versión pueden reemplazar tags existentes: usar una versión nueva para cada release. No cambiar visibilidad, credenciales o configuración de producción automáticamente.

Las imágenes locales y sus archivos OCI se conservan para inspección; las pruebas E2E eliminan sus propios recursos. Las pruebas emuladas ARM se identifican como emulación, sin afirmar validación en hardware ARM. El soporte de attestations exige containerd: se falla con una instrucción concreta en vez de descartarlas silenciosamente.

La autenticación sigue fuera del orquestador. A petición posterior del usuario, documentar GitHub CLI con login web y scope `write:packages`, pasando su token directamente a `docker login --password-stdin`. Añadir la feature oficial al Dev Container; conservar PAT classic dedicado como alternativa. No iniciar sesiones ni publicar durante esta tarea. El uso de `gh` simplifica la gestión, pero conserva credenciales y no garantiza un almacén seguro dentro del contenedor.

Decisiones de implementación: mantener migration/python y el Dev Container existentes; Python estándar; default builder=default; informes sin credenciales; no publicar durante la preparación. Son elecciones del implementador dentro del alcance solicitado, sin una nueva ronda de aprobación para trabajo local reversible.
