# Versiones mediante PR de release y main protegida

El usuario pide versionado automático y concreta que main solo admita PRs y que
una propuesta de release acumule los cambios. La propuesta queda abierta hasta
que el usuario decida fusionarla. No se introducen Node ni publicaciones locales.

Se conserva el preparador Python de versiones. Major para `!` / breaking footer,
minor para feat/fix y patch para el resto. Actualiza pyproject, lock propio, OCI,
README bilingüe y el ancla de cambios. La historia first-parent del ancla reconoce
el merge real de una release, incluyendo squash, y evita un incremento recursivo.

Los checks nativos de ambas arquitecturas son obligatorios en las PRs. Tras un
merge normal a main, un job serializado prepara y actualiza `codex/release-main`
con force-with-lease, mantiene una única PR y despacha sus checks explícitamente.
El bot nunca aprueba ni fusiona la propuesta. No se usan skip directives, para
que fusionarla sí ejecute el CI del commit definitivo.

Solo un push asociado a una PR de release fusionada del repositorio propio puede
publicar, después de ambos checks. Se suben las imágenes probadas sin reconstruir,
el tag Git del merge, X.Y.Z, latest y GitHub Release. Solo se escriben tags en Git;
main no recibe pushes de ningún job. Las publicaciones se serializan, los tags
no se sobrescriben y una repetición antigua no reduce latest.

Main exige PR, checks Verify amd64 / Verify arm64 estrictos, historial lineal y
conversaciones resueltas, incluso para administradores. Se exige cero aprobaciones
de otra persona para permitir mantenimiento individual, sin eliminar la PR. No
hay bypass del bot, force push ni borrado. El ajuste agrupado de GitHub para crear
y aprobar PRs se habilita para crear propuestas; el CI no utiliza aprobación.

Se descartó el commit automático directo a main por la aclaración del usuario.
Release Please ofrece el patrón solicitado, pero introducir su runtime Node
contradice AGENTS.md; se reutiliza el preparador Python con Git/gh y jq. Los
baselines de compatibilidad permanecen intactos.
