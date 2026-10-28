# Recuperación del entorno Docker

El28de octubre, al reanudar P10, el pipe dockerDesktopLinuxEngine no estaba disponible. El log local del backend indicaba que no podía acceder/eliminar el endpoint temporal Docker/run/dockerInference; Get-Acl devolvía error1920. El directorio run contenía solamente dockerInference y userAnalyticsOtlpHttp.sock, ambos objetos de0bytes con atributo ReparsePoint.

El error coincide con [un reporte de sockets AF_UNIX en el repositorio de Docker](https://github.com/docker/desktop-feedback/issues/527). Esto es una coincidencia diagnóstica; no se ha demostrado aquí la causa del kernel descrita por ese reporte.

La parada normal de Docker Desktop no terminó antes de su timeout. Se cerraron solo los procesos de frontend/backend de Docker identificados por ruta de instalación. Tras verificar las rutas absolutas y que run era un directorio normal, se renombró exclusivamente esa carpeta a run.recovery-20261028-0840 dentro del mismo Docker de AppData/Local. Se conserva como respaldo.

docker desktop start terminó con éxito y docker start mealie-mcp-development-dev-1 reanudó el contenedor de este repositorio. No se borraron imágenes, volúmenes ni discos WSL y no se ejecutó reset/prune/unregister. El código y los commits de P01..P09 se conservaron.

La aplicación continúa ejecutándose y probándose en el Dev Container. Las pruebas de P10 se registran por separado en su evidencia de fase; recuperar Docker no las sustituye.
