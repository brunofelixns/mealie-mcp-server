# Main protegida y Release Please oficial

El usuario requiere PRs obligatorias en main y una PR de publicación acumulativa.
Ha elegido Release Please **oficial**, autorizando Node solo para esa herramienta
en CI. El producto, Dev Container y tests/builds permanecen en Python.

Release Please mantiene el manifest, versión, CHANGELOG, lock propio, etiquetas OCI
y catálogos README. Se conserva el historial. Un helper Python sin escrituras calcula
`--release-as` para respetar major breaking / minor feat-fix / patch otros, con los
tipos Conventional Commit configurados. El CLI oficial admite ese override en modo
manifest; la acción oficial se dedica a crear las Releases tras fusionar sus PRs.

El código funcional ya está en main cuando se actualiza la propuesta. El usuario
decide cuándo fusionarla. Main exige PR, checks nativos al día, historial lineal y
conversaciones resueltas, incluso para admins, sin force/borrado ni bypass del bot.
Se exigen cero revisiones adicionales para permitir mantenimiento individual.

Al fusionar una propuesta, Release Please crea el tag y Release y despacha CI sobre
ese tag exacto. CI comprueba revisión, versión y Release, prueba amd64 y arm64 nativos
y publica las imágenes probadas sin reconstrucción. El publicador solo tiene lectura
Git y escritura GHCR. Serialización y tags inmutables evitan sobrescrituras o reducir
latest. El dispatch del tag elimina la necesidad de un PAT permanente para publicar.

Con GITHUB_TOKEN, GitHub requiere autorizar los workflows de la PR de release mediante
**Approve workflows to run** cuando lo solicite; el token temporal no puede autorizar
sus propios workflows. Despachar CI sobre su rama prueba el código pero no sustituye
los checks de PR exigidos por esta protección. El resumen enlaza la propuesta y explica
ese paso. Automatizar también esa autorización necesita una credencial dedicada adicional.

La PR de release queda abierta, sin auto-merge. Una Release cuyo dispatch falló se
recupera despachando CI explícitamente sobre su tag, no volviendo a ejecutar Release
Please. La última comprobación operativa debe verificar protección, PR de configuración
y propuesta generada por Release Please con sus checks verdes.
